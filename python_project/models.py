import os
import time
import warnings
from typing import Optional, Any, List
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from config import settings
from agent.async_manager import async_agent_manager, LLM_REQUEST_TIMEOUT, ErrorType

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
    Reads model dynamically from runtime argument or environment variable (DEFAULT_MODEL).
    Never hardcodes any model string.
    """
    target_model = (model_name or os.getenv("DEFAULT_MODEL") or settings.default_model or "").strip()
    if not target_model:
        raise ValueError("No model specified in request or DEFAULT_MODEL environment variable.")

    # 1. OpenAI Models (e.g. gpt-4o, gpt-4o-mini, o1, o3)
    if target_model.startswith("gpt-") or "openai" in target_model.lower():
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

    # 2. Anthropic Claude Models (e.g. claude-3-5-sonnet, claude-3-haiku)
    if target_model.startswith("claude-") or "anthropic" in target_model.lower():
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

    # 3. Google Gemini Models (e.g. gemini-1.5-pro, gemini-2.0-flash)
    if (target_model.startswith("gemini-") or "google" in target_model.lower()) and not "/" in target_model:
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

    # 4. NVIDIA AI NIM Hosted Models (all / any model hosted on NVIDIA NIM)
    api_key = settings.nvidia_api_key or os.getenv("NVIDIA_API_KEY", "")
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
            
            if is_timeout:
                error_category = ErrorType.NIM_TIMEOUT
            elif "429" in err_str or "rate limit" in err_str:
                error_category = ErrorType.NIM_RATE_LIMIT
            elif "503" in err_str or "502" in err_str or "500" in err_str or "server error" in err_str:
                error_category = ErrorType.NIM_SERVER_ERROR
            elif "connection" in err_str or "connect" in err_str:
                error_category = ErrorType.NIM_CONNECTION_ERROR
            else:
                error_category = ErrorType.UNKNOWN_ERROR

            is_retryable = is_timeout or error_category in (ErrorType.NIM_RATE_LIMIT, ErrorType.NIM_SERVER_ERROR, ErrorType.NIM_CONNECTION_ERROR)

            if is_timeout:
                async_agent_manager.log_timing(run_id, "llm_request_timeout", elapsed_ms, iteration=iteration)
                async_agent_manager.log_diagnostic(
                    run_id=run_id,
                    component="NVIDIA NIM API",
                    timeout_type=error_category.value,
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
                    timeout_type=error_category.value,
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

