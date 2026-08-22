"""FastAPI Microservice with Dynamic Tool Calling, RAG, and Browser AI Agent Platform."""
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Security, Depends, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
import os

from config import settings
from memory.manager import memory_manager
from documents import convert_upload
from tools.executor import execute_tool_calling_flow
from browser.service import browser_service
from browser.schema import BrowserMode, BrowserStatus, TabInfo, PageSnapshot, ActionResult

INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "clever-internal-agent-secret-key-prod-2026")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade LangChain Microservice with Browser AI Agent, Tool Calling, and RAG",
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
    userId: Optional[int] = Field(default=1, description="Authenticated user ID for multi-user isolation")

class ChatResponse(BaseModel):
    reply: str
    chain_used: str
    model_used: str
    thread_id: str
    memory_turns: int
    toolResults: Optional[List[ToolResult]] = None
    provider: Optional[str] = "LangChain AI Agent"
    timestamp: str

# Browser Request / Response Schemas
class BrowserConnectRequest(BaseModel):
    mode: Optional[BrowserMode] = Field(default=BrowserMode.EXISTING_CDP)
    cdp_url: Optional[str] = Field(default="http://127.0.0.1:9222")
    user_data_dir: Optional[str] = None
    userId: Optional[int] = Field(default=1)

class BrowserTabSelectRequest(BaseModel):
    tab_id: str
    userId: Optional[int] = Field(default=1)

class BrowserTabOpenRequest(BaseModel):
    url: str = Field(default="about:blank")
    userId: Optional[int] = Field(default=1)

class BrowserTabCloseRequest(BaseModel):
    tab_id: str
    userId: Optional[int] = Field(default=1)

class BrowserSnapshotRequest(BaseModel):
    tab_id: Optional[str] = None
    userId: Optional[int] = Field(default=1)

class BrowserActionRequest(BaseModel):
    action: str = Field(..., description="Action name: click, type, navigate, scroll, press_key, screenshot, go_back, go_forward")
    selector: Optional[str] = None
    text_input: Optional[str] = None
    url: Optional[str] = None
    element_id: Optional[int] = None
    key: Optional[str] = None
    direction: Optional[str] = "down"
    pixels: Optional[int] = 500
    tab_id: Optional[str] = None
    confirmed: Optional[bool] = False
    userId: Optional[int] = Field(default=1)

class BrowserConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool
    userId: Optional[int] = Field(default=1)

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
    target = file or upload or document
    if not target:
        raise HTTPException(status_code=400, detail="Missing upload file in request body.")
    return await convert_upload(target)

# ==========================================
# BROWSER AGENT REST API ROUTES
# ==========================================

@app.post("/api/v1/browser/connect")
def browser_connect(req: BrowserConnectRequest):
    """Connect to user's existing Chrome/Edge browser via CDP or managed session."""
    user_id = req.userId or 1
    success, message, status = browser_service.connect(
        user_id=user_id, mode=req.mode or BrowserMode.EXISTING_CDP, cdp_url=req.cdp_url or "http://127.0.0.1:9222"
    )
    return {
        "success": success,
        "message": message,
        "status": status.model_dump()
    }

@app.post("/api/v1/browser/disconnect")
def browser_disconnect(req: Optional[BrowserConnectRequest] = None):
    """Disconnect from browser without closing user's running browser process."""
    user_id = req.userId if req else 1
    success, message = browser_service.disconnect(user_id=user_id)
    return {"success": success, "message": message}

@app.get("/api/v1/browser/status")
def browser_get_status(userId: Optional[int] = 1):
    """Get connectivity, browser type, and open tabs count."""
    status = browser_service.get_status(user_id=userId or 1)
    return status.model_dump()

@app.get("/api/v1/browser/tabs")
def browser_list_tabs(userId: Optional[int] = 1):
    """List open tabs with titles, URLs, and active status."""
    tabs = browser_service.list_tabs(user_id=userId or 1)
    return {"tabs": [t.model_dump() for t in tabs]}

@app.post("/api/v1/browser/tabs/select")
def browser_select_tab(req: BrowserTabSelectRequest):
    """Switch active focused tab in browser."""
    success, message, tab = browser_service.select_tab(user_id=req.userId or 1, tab_id=req.tab_id)
    return {
        "success": success,
        "message": message,
        "tab": tab.model_dump() if tab else None
    }

@app.post("/api/v1/browser/tabs/open")
def browser_open_tab(req: BrowserTabOpenRequest):
    """Open new tab and navigate to URL."""
    success, message, tab = browser_service.open_new_tab(user_id=req.userId or 1, url=req.url)
    return {
        "success": success,
        "message": message,
        "tab": tab.model_dump() if tab else None
    }

@app.post("/api/v1/browser/tabs/close")
def browser_close_tab(req: BrowserTabCloseRequest):
    """Close tab by ID."""
    success, message = browser_service.close_tab(user_id=req.userId or 1, tab_id=req.tab_id)
    return {"success": success, "message": message}

@app.post("/api/v1/browser/snapshot")
def browser_snapshot(req: BrowserSnapshotRequest):
    """Capture structured accessibility snapshot of active or target tab."""
    res = browser_service.snapshot(user_id=req.userId or 1, tab_id=req.tab_id)
    return res.model_dump()

@app.post("/api/v1/browser/action")
def browser_execute_action(req: BrowserActionRequest):
    """Execute semantic browser action with Human Confirmation Security Gate."""
    res = browser_service.execute_action(
        user_id=req.userId or 1,
        action=req.action,
        selector=req.selector,
        text_input=req.text_input,
        url=req.url,
        element_id=req.element_id,
        key=req.key,
        direction=req.direction or "down",
        pixels=req.pixels or 500,
        tab_id=req.tab_id,
        confirmed=req.confirmed or False
    )
    return res.model_dump()

@app.post("/api/v1/browser/confirm")
def browser_resolve_confirmation(req: BrowserConfirmRequest):
    """Approve or reject a pending dangerous action."""
    res = browser_service.resolve_confirmation(
        user_id=req.userId or 1,
        confirmation_id=req.confirmation_id,
        approved=req.approved
    )
    return res.model_dump()

from fastapi.responses import StreamingResponse
from agent.async_manager import async_agent_manager, AgentRunState, AgentRunRecord
import json
import asyncio

class AsyncChatStartResponse(BaseModel):
    run_id: str
    status: AgentRunState
    thread_id: str
    message: str = "Agent execution scheduled"

class RunStatusResponse(BaseModel):
    run_id: str
    user_id: int
    thread_id: str
    prompt: str
    status: AgentRunState
    current_action: Optional[str] = None
    iteration: int = 0
    started_at: float
    completed_at: Optional[float] = None
    execution_time_ms: int = 0
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    reply: Optional[str] = None
    error: Optional[str] = None
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list)

# ==========================================
# ASYNCHRONOUS AGENT RUN LIFECYCLE ENDPOINTS
# ==========================================

@app.post("/api/v1/chat/async", response_model=AsyncChatStartResponse)
async def chat_async_endpoint(req: ChatRequest):
    """
    Initiate a long-running Autonomous Agent run asynchronously.
    Returns immediately with run_id and status=QUEUED.
    """
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    thread_id = req.threadId or f"thread_{str(time.time()).replace('.', '')}"
    target_model = (req.model or os.getenv("DEFAULT_MODEL") or settings.default_model or "").strip()
    active_plugins = req.activePlugins or []
    document_context = req.documentContext or []
    user_id = req.userId or 1

    run_record = async_agent_manager.create_run(
        user_id=user_id,
        thread_id=thread_id,
        prompt=user_msg,
        model=target_model
    )

    # Spawn background agent execution
    def _run_bg():
        execute_tool_calling_flow(
            user_prompt=user_msg,
            active_plugin_ids=active_plugins,
            model_name=target_model,
            document_context=document_context,
            history=req.history,
            user_id=user_id,
            run_id=run_record.run_id,
            thread_id=thread_id
        )

    asyncio.get_event_loop().run_in_executor(None, _run_bg)

    return AsyncChatStartResponse(
        run_id=run_record.run_id,
        status=AgentRunState.QUEUED,
        thread_id=thread_id,
        message="Autonomous agent run started successfully."
    )

@app.get("/api/v1/chat/runs/{run_id}", response_model=RunStatusResponse)
def get_run_status(run_id: str):
    """Query live execution status, tool outputs, timing, and response for an agent run."""
    record = async_agent_manager.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    return RunStatusResponse(
        run_id=record.run_id,
        user_id=record.user_id,
        thread_id=record.thread_id,
        prompt=record.prompt,
        status=record.status,
        current_action=record.current_action,
        iteration=record.iteration,
        started_at=record.started_at,
        completed_at=record.completed_at,
        execution_time_ms=record.execution_time_ms,
        tool_results=record.tool_results,
        reply=record.final_response,
        error=record.error,
        diagnostics=[d.model_dump() for d in record.diagnostics]
    )

@app.get("/api/v1/chat/runs/{run_id}/events")
async def get_run_events_stream(run_id: str):
    """Server-Sent Events (SSE) stream for live real-time agent execution tracking."""
    record = async_agent_manager.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    async def event_generator():
        async for event in async_agent_manager.stream_events(run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/v1/chat/runs/{run_id}/cancel")
def cancel_agent_run(run_id: str):
    """Cancel an active long-running agent run."""
    success = async_agent_manager.cancel_run(run_id)
    if not success:
        raise HTTPException(status_code=400, detail="Run could not be cancelled or has already completed.")
    return {"success": True, "message": f"Run '{run_id}' cancelled successfully."}

# ==========================================
# SYNCHRONOUS CHAT ENDPOINT (With Error Codes)
# ==========================================

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    chain_name = req.chain_name or "default_chat"
    thread_id = req.threadId or "default-session"
    target_model = (req.model or os.getenv("DEFAULT_MODEL") or settings.default_model or "").strip()
    active_plugins = req.activePlugins or []
    document_context = req.documentContext or []
    user_id = req.userId or 1

    run_record = async_agent_manager.create_run(
        user_id=user_id,
        thread_id=thread_id,
        prompt=user_msg,
        model=target_model
    )

    reply_text, tool_results_data, provider_name = execute_tool_calling_flow(
        user_prompt=user_msg,
        active_plugin_ids=active_plugins,
        model_name=target_model,
        document_context=document_context,
        history=req.history,
        user_id=user_id,
        run_id=run_record.run_id,
        thread_id=thread_id
    )

    # Check for actual timeout / cancellation / failure state
    record = async_agent_manager.get_run(run_record.run_id)
    if record:
        if record.status == AgentRunState.TIMEOUT:
            raise HTTPException(
                status_code=504,
                detail=f"Agent execution timed out: {record.error or 'LLM/Browser timeout'}"
            )
        elif record.status == AgentRunState.CANCELLED:
            raise HTTPException(
                status_code=499,
                detail="Agent execution was cancelled by client."
            )

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
