import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    app_name: str = "Clever AI LangChain Service"
    app_version: str = "2.0.0"
    environment: str = os.getenv("NODE_ENV", "production")
    internal_service_key: str = os.getenv("INTERNAL_SERVICE_KEY", "clever-internal-agent-secret-key-prod-2026")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    default_model: str = os.getenv("DEFAULT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    langsmith_endpoint: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "first agent")
    port: int = int(os.getenv("PORT", "8001"))
    host: str = os.getenv("HOST", "0.0.0.0")

settings = Settings()
