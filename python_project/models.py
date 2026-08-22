import os
import time
import warnings
from typing import Optional, Any, List
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from config import settings
from agent.async_manager import async_agent_manager, LLM_REQUEST_TIMEOUT

warnings.filterwarnings("ignore", category=UserWarning, module="langchain_nvidia_ai_endpoints")

class LLMTimeoutError(Exception):
    """Raised when an LLM invocation exceeds its component timeout."""
    pass

class LLMCancelledError(Exception):
    """Raised when an LLM invocation is cancelled."""
    pass

def get_chat_model(model_name: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 4096, timeout: float = LLM_REQUEST_TIMEOUT):
    """
    Dynamic Multi-Model Factory Function.
    Supports ChatNVIDIA (Nemotron, Llama), OpenAI, Anthropic, and Google Gemini models at runtime.
    Configured with explicit component-specific LLM_REQUEST_TIMEOUT.
    """
    target_model = model_name or settings.default_model

    # 1. NVIDIA AI Models
    if target_model.startswith("meta/") or target_model.startswith("nvidia/") or target_model.startswith("mistralai/") or "nvidia" in target_model or "nemotron" in target_model:
        api_key = settings.nvidia_api_key
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is not set in configuration")

        return ChatNVIDIA(
            model=target_model,
            api_key=api_key,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            timeout=int(timeout)
        )

    # 2. OpenAI Models (gpt-4o, gpt-4o-mini)
    if target_model.startswith("gpt-") or "openai" in target_model:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=target_model,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout
            )
        except ImportError:
            pass

    # 3. Anthropic Claude Models (claude-3-5-sonnet)
    if target_model.startswith("claude-") or "anthropic" in target_model:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=target_model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
        except ImportError:
            pass

    # 4. Google Gemini Models (gemini-1.5-pro)
    if target_model.startswith("gemini-") or "google" in target_model:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=target_model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                timeout=timeout
            )
        except ImportError:
            pass

    # Default Fallback: ChatNVIDIA with default model
    return ChatNVIDIA(
        model=settings.default_model,
        api_key=settings.nvidia_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=int(timeout)
    )

def invoke_llm_with_diagnostics(
    llm: Any,
    messages: List[Any],
    run_id: str,
    iteration: int = 1,
    max_retries: int = 1
) -> Any:
    """
    Executes LLM inference with structured timing logs, timeout diagnostics, cancellation checks,
    and bounded retries (max 1 retry for transient network drops/rate limits).
    """
    if async_agent_manager.is_cancelled(run_id):
        raise LLMCancelledError("Run was cancelled before LLM invocation.")

    configured_timeout_ms = int(LLM_REQUEST_TIMEOUT * 1000)
    start_time = time.time()
    async_agent_manager.log_timing(run_id, "llm_request_started", 0, iteration=iteration)

    for attempt in range(max_retries + 1):
        if async_agent_manager.is_cancelled(run_id):
            raise LLMCancelledError("Run was cancelled during LLM invocation.")

        attempt_start = time.time()
        try:
            response = llm.invoke(messages)
            elapsed_ms = int((time.time() - attempt_start) * 1000)
            async_agent_manager.log_timing(run_id, "llm_request_completed", elapsed_ms, iteration=iteration)
            return response

        except Exception as exc:
            elapsed_ms = int((time.time() - attempt_start) * 1000)
            err_str = str(exc).lower()
            is_timeout = "timeout" in err_str or "timed out" in err_str or "abort" in err_str or elapsed_ms >= (configured_timeout_ms - 2000)
            is_retryable = is_timeout or "429" in err_str or "503" in err_str or "connection" in err_str

            if is_timeout:
                async_agent_manager.log_timing(run_id, "llm_request_timeout", elapsed_ms, iteration=iteration)
                async_agent_manager.log_diagnostic(
                    run_id=run_id,
                    component="NVIDIA NIM API",
                    timeout_type="request_timeout",
                    configured_timeout_ms=configured_timeout_ms,
                    elapsed_ms=elapsed_ms,
                    operation="chat_completion",
                    upstream="api.nvidia.com",
                    retry_count=attempt
                )
            else:
                async_agent_manager.log_diagnostic(
                    run_id=run_id,
                    component="LLM Client",
                    timeout_type="execution_error",
                    configured_timeout_ms=configured_timeout_ms,
                    elapsed_ms=elapsed_ms,
                    operation="chat_completion",
                    upstream="api.nvidia.com",
                    retry_count=attempt
                )

            # Bounded retry: only retry once if retryable
            if is_retryable and attempt < max_retries:
                time.sleep(1.0)
                continue

            if is_timeout:
                raise LLMTimeoutError(f"LLM request timed out after {elapsed_ms}ms (Configured: {configured_timeout_ms}ms)")
            raise exc

