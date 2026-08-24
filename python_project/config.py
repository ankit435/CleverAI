import os
import secrets
import warnings
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Known insecure placeholder values that must never reach production.
_INSECURE_KEY_PLACEHOLDERS = {
    "clever-internal-agent-secret-key-prod-2026",
    "change-me",
    "",
}

class Settings(BaseModel):
    app_name: str = "Clever AI LangChain Service"
    app_version: str = "2.0.0"
    environment: str = os.getenv("NODE_ENV", "development")
    # Intentionally no hardcoded fallback — empty triggers warning + random key below.
    internal_service_key: str = os.getenv("INTERNAL_SERVICE_KEY", "")
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    default_model: str = os.getenv("DEFAULT_MODEL", "").strip()
    browser_mode: str = os.getenv("BROWSER_MODE", "existing_cdp")
    browser_cdp_url: str = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    langsmith_endpoint: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "first agent")
    port: int = int(os.getenv("PORT", "8001"))
    host: str = os.getenv("HOST", "0.0.0.0")


_raw_settings = Settings()

if _raw_settings.internal_service_key in _INSECURE_KEY_PLACEHOLDERS:
    warnings.warn(
        "INTERNAL_SERVICE_KEY is not set or uses an insecure default. "
        "A random per-process key has been generated. "
        "Set INTERNAL_SERVICE_KEY in your .env file before deploying.",
        RuntimeWarning,
        stacklevel=2,
    )
    settings = Settings(**{**_raw_settings.model_dump(), "internal_service_key": secrets.token_hex(32)})
else:
    settings = _raw_settings
