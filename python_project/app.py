import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Security, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from config import settings
from memory.manager import memory_manager
from documents import convert_upload
from tools.executor import execute_tool_calling_flow

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade LangChain Microservice with Dynamic Tool Calling and RAG",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="x-internal-service-key", auto_error=False)

def verify_internal_key(header_val: str = Security(api_key_header)):
    if header_val != settings.internal_service_key:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal service authentication key")
    return header_val

class ToolResult(BaseModel):
    toolId: str
    toolName: str
    status: str
    executionTimeMs: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str = Field(..., description="User query or prompt message")
    chain_name: Optional[str] = Field("default_chat", description="Chain name to execute")
    model: Optional[str] = Field(None, description="Model identifier override")
    threadId: Optional[str] = Field(None, description="Conversation thread identifier for memory")
    activePlugins: Optional[List[str]] = Field(default_factory=list, description="Active plugin IDs enabled by user")
    documentContext: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Extracted document chunks for grounding")
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Conversation history from PostgreSQL")

class ChatResponse(BaseModel):
    reply: str
    chain_used: str
    model_used: str
    thread_id: str
    memory_turns: int
    toolResults: Optional[List[ToolResult]] = None
    provider: Optional[str] = "LangChain AI Agent"
    timestamp: str

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "default_model": settings.default_model
    }

@app.get("/api/v1/models")
def list_available_models():
    return {
        "models": [
            {"id": "nvidia/nemotron-3.5-lightning-30b-a3b", "name": "NVIDIA Nemotron 3.5 Lightning 30B", "provider": "NVIDIA NIM", "badge": "Primary"},
            {"id": "meta/llama-3.1-70b-instruct", "name": "Meta Llama 3.1 70B Instruct", "provider": "NVIDIA NIM", "badge": "Fast"},
            {"id": "gpt-4o", "name": "OpenAI GPT-4o", "provider": "OpenAI", "badge": "Pro"},
            {"id": "claude-3-5-sonnet", "name": "Anthropic Claude 3.5 Sonnet", "provider": "Anthropic", "badge": "Pro"},
            {"id": "gemini-1.5-pro", "name": "Google Gemini 1.5 Pro", "provider": "Google", "badge": "Pro"},
            {"id": "local-ollama", "name": "Local Ollama Llama 3", "provider": "Local Host", "badge": "Offline"}
        ]
    }

@app.post('/api/v1/documents/convert')
async def convert_document(
    file: Optional[UploadFile] = File(None),
    upload: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(None)
):
    """Convert an uploaded document to retrieval-ready Markdown via Microsoft MarkItDown."""
    target = file or upload or document
    if not target:
        raise HTTPException(status_code=400, detail="Missing upload file in request body.")
    return await convert_upload(target)

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    chain_name = req.chain_name or "default_chat"
    thread_id = req.threadId or "default-session"
    target_model = req.model or settings.default_model
    active_plugins = req.activePlugins or []
    document_context = req.documentContext or []

    # Execute dynamic Tool Calling Agent
    reply_text, tool_results_data, provider_name = execute_tool_calling_flow(
        user_prompt=user_msg,
        active_plugin_ids=active_plugins,
        model_name=target_model,
        document_context=document_context,
        history=req.history
    )

    # Convert to Pydantic ToolResult models
    tool_results: Optional[List[ToolResult]] = None
    if tool_results_data:
        tool_results = [
            ToolResult(
                toolId=t.get("toolId", "tool"),
                toolName=t.get("toolName", "Tool"),
                status=t.get("status", "success"),
                executionTimeMs=t.get("executionTimeMs", 50),
                data=t.get("data")
            )
            for t in tool_results_data
        ]

    # Track conversation turns
    if thread_id:
        memory_manager.add_user_message(thread_id, user_msg)
        memory_manager.add_ai_message(thread_id, reply_text)

    history_count = len(memory_manager.get_history(thread_id))

    return ChatResponse(
        reply=str(reply_text),
        chain_used=chain_name,
        model_used=target_model,
        thread_id=thread_id,
        memory_turns=history_count,
        toolResults=tool_results,
        provider=provider_name,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
