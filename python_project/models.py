import os
import warnings
from typing import Optional
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from config import settings

warnings.filterwarnings("ignore", category=UserWarning, module="langchain_nvidia_ai_endpoints")

def get_chat_model(model_name: Optional[str] = None, temperature: float = 1.0, max_tokens: int = 4096):
    """
    Dynamic Multi-Model Factory Function.
    Supports ChatNVIDIA (Nemotron, Llama), OpenAI, Anthropic, and Google Gemini models at runtime.
    """
    target_model = model_name or settings.default_model

    # 1. NVIDIA AI Models
    if target_model.startswith("meta/") or target_model.startswith("nvidia/") or target_model.startswith("mistralai/") or "nvidia" in target_model or "nemotron" in target_model:
        api_key = settings.nvidia_api_key
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is not set in configuration")
        
        model_kwargs = {}
        if "nemotron" in target_model:
            model_kwargs["reasoning_budget"] = 2048
            model_kwargs["chat_template_kwargs"] = {"enable_thinking": True}

        return ChatNVIDIA(
            model=target_model,
            api_key=api_key,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            timeout=180,
            model_kwargs=model_kwargs
        )

    # 2. OpenAI Models (gpt-4o, gpt-4o-mini)
    if target_model.startswith("gpt-") or "openai" in target_model:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=target_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except ImportError:
            print("⚠️ langchain-openai not installed, falling back to ChatNVIDIA")

    # 3. Anthropic Claude Models (claude-3-5-sonnet)
    if target_model.startswith("claude-") or "anthropic" in target_model:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=target_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except ImportError:
            print("⚠️ langchain-anthropic not installed, falling back to ChatNVIDIA")

    # 4. Google Gemini Models (gemini-1.5-pro)
    if target_model.startswith("gemini-") or "google" in target_model:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=target_model,
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        except ImportError:
            print("⚠️ langchain-google-genai not installed, falling back to ChatNVIDIA")

    # Default Fallback: ChatNVIDIA with default model
    return ChatNVIDIA(
        model=settings.default_model,
        api_key=settings.nvidia_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180,
    )
