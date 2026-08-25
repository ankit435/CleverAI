"""FastAPI Microservice with Dynamic Tool Calling, RAG, and Browser AI Agent Platform."""
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Security, Depends, UploadFile, File, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
import os

from config import settings
from memory.manager import memory_manager
from documents import convert_upload
from tools.executor import execute_tool_calling_flow
from browser.service import browser_service
from browser.schema import BrowserMode, BrowserStatus, TabInfo, ActionResult

# Use the validated key from settings (never a hardcoded fallback).
INTERNAL_SERVICE_KEY = settings.internal_service_key

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade LangChain Microservice with Browser AI Agent, Tool Calling, and RAG",
)

# CORS: use explicit origin allowlist from ALLOWED_ORIGINS env var.
# Wildcards + credentials simultaneously is a browser security violation.
_allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "x-internal-service-key", "X-Request-ID"],
)

# Security headers on every response.
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

api_key_header = APIKeyHeader(name="x-internal-service-key", auto_error=False)

def verify_internal_key(header_val: str = Security(api_key_header)):
    if header_val != settings.internal_service_key:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal service authentication key")
    return header_val

# ---------------------------------------------------------------------------
# Browser idle-session reaper: a single shared Stagehand browser now persists
# per user across turns/conversations (each conversation gets its own tab), so
# it must be actively reaped after real inactivity instead of being closed
# after every turn — otherwise browsers would leak for logged-in-but-idle users.
# ---------------------------------------------------------------------------
import asyncio as _asyncio

_BROWSER_REAP_INTERVAL_SECONDS = float(os.getenv("BROWSER_REAP_INTERVAL_SECONDS", "60.0"))

async def _browser_idle_reaper_loop():
    loop = _asyncio.get_event_loop()
    while True:
        try:
            await _asyncio.sleep(_BROWSER_REAP_INTERVAL_SECONDS)
            # reap_idle_sessions() blocks on the Stagehand async-worker thread —
            # run it off the main event loop so it never stalls request handling.
            await loop.run_in_executor(None, browser_service.reap_idle_sessions)
        except Exception:
            pass  # Best-effort background maintenance — never crash the process.

@app.on_event("startup")
async def _start_browser_idle_reaper():
    _asyncio.create_task(_browser_idle_reaper_loop())

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
    runId: Optional[str] = Field(None, description="Caller-supplied run_id (Node's AgentRun.id) so async/SSE tracking shares one identifier end-to-end")
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

class BrowserNavigateRequest(BaseModel):
    url: str
    userId: Optional[int] = Field(default=1)
    threadId: Optional[str] = Field(default=None, description="Conversation id — keeps this navigation on that conversation's own tab")

class BrowserActRequest(BaseModel):
    instruction: str = Field(..., description="Plain natural-language action, e.g. 'click the Sign In button'")
    confirmed: Optional[bool] = False
    userId: Optional[int] = Field(default=1)
    threadId: Optional[str] = Field(default=None, description="Conversation id — keeps this action on that conversation's own tab")

class BrowserObserveRequest(BaseModel):
    instruction: Optional[str] = None
    userId: Optional[int] = Field(default=1)
    threadId: Optional[str] = Field(default=None)

class BrowserExtractRequest(BaseModel):
    instruction: str = Field(..., description="What information to extract from the current page")
    userId: Optional[int] = Field(default=1)
    threadId: Optional[str] = Field(default=None)

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
    user_id = req.userId
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
    status = browser_service.get_status(user_id=userId)
    return status.model_dump()

@app.get("/api/v1/browser/tabs")
def browser_list_tabs(userId: Optional[int] = 1):
    """List open tabs with titles, URLs, and active status."""
    tabs = browser_service.list_tabs(user_id=userId)
    return {"tabs": [t.model_dump() for t in tabs]}

@app.post("/api/v1/browser/tabs/select")
def browser_select_tab(req: BrowserTabSelectRequest):
    """Switch active focused tab in browser."""
    success, message, tab = browser_service.select_tab(user_id=req.userId, tab_id=req.tab_id)
    return {
        "success": success,
        "message": message,
        "tab": tab.model_dump() if tab else None
    }

@app.post("/api/v1/browser/tabs/open")
def browser_open_tab(req: BrowserTabOpenRequest):
    """Open new tab and navigate to URL."""
    success, message, tab = browser_service.open_new_tab(user_id=req.userId, url=req.url)
    return {
        "success": success,
        "message": message,
        "tab": tab.model_dump() if tab else None
    }

@app.post("/api/v1/browser/tabs/close")
def browser_close_tab(req: BrowserTabCloseRequest):
    """Close tab by ID."""
    success, message = browser_service.close_tab(user_id=req.userId, tab_id=req.tab_id)
    return {"success": success, "message": message}

@app.post("/api/v1/browser/navigate")
def browser_navigate_route(req: BrowserNavigateRequest):
    """Navigate the browser to a URL (Stagehand-managed)."""
    res = browser_service.navigate(user_id=req.userId, url=req.url, thread_id=req.threadId)
    return res.model_dump()

@app.post("/api/v1/browser/act")
def browser_act_route(req: BrowserActRequest):
    """Perform a natural-language action on the current page, with Human Confirmation Security Gate."""
    res = browser_service.act(user_id=req.userId, instruction=req.instruction, confirmed=req.confirmed, thread_id=req.threadId)
    return res.model_dump()

@app.post("/api/v1/browser/observe")
def browser_observe_route(req: BrowserObserveRequest):
    """Discover actionable elements on the current page."""
    res = browser_service.observe(user_id=req.userId, instruction=req.instruction, thread_id=req.threadId)
    return res.model_dump()

@app.post("/api/v1/browser/extract")
def browser_extract_route(req: BrowserExtractRequest):
    """Extract structured/free-text data from the current page."""
    res = browser_service.extract(user_id=req.userId, instruction=req.instruction, thread_id=req.threadId)
    return res.model_dump()

@app.post("/api/v1/browser/confirm")
def browser_resolve_confirmation(req: BrowserConfirmRequest):
    """Approve or reject a pending dangerous action."""
    res = browser_service.resolve_confirmation(
        user_id=req.userId,
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
    verified_count: Optional[int] = None
    requested_count: Optional[int] = None

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
    user_id = req.userId

    run_record = async_agent_manager.create_run(
        user_id=user_id,
        thread_id=thread_id,
        prompt=user_msg,
        model=target_model,
        run_id=req.runId
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

    # get_event_loop() is deprecated inside a running loop in Python 3.10+.
    asyncio.get_running_loop().run_in_executor(None, _run_bg)

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
        diagnostics=[d.model_dump() for d in record.diagnostics],
        verified_count=record.verified_count,
        requested_count=record.requested_count
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


@app.post("/api/v1/chat/runs/{run_id}/retry", response_model=AsyncChatStartResponse)
async def retry_agent_run(run_id: str):
    """
    Retries a FAILED/TIMEOUT/NO_RESULTS/CANCELLED run by starting a brand-new run
    with the same prompt/user/thread — used by the UI's [Retry] affordance. This does
    NOT resurrect the old run_id (a terminal run stays terminal); it starts a fresh one.
    """
    record = async_agent_manager.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    non_retryable = {AgentRunState.RUNNING, AgentRunState.WAITING_FOR_LLM, AgentRunState.QUEUED, AgentRunState.COMPLETED}
    if record.status in non_retryable:
        raise HTTPException(status_code=400, detail=f"Run is in state '{record.status}' and cannot be retried.")

    new_record = async_agent_manager.create_run(
        user_id=record.user_id,
        thread_id=record.thread_id,
        prompt=record.prompt,
        model=record.model,
    )

    def _run_bg():
        execute_tool_calling_flow(
            user_prompt=record.prompt,
            active_plugin_ids=[],
            model_name=record.model,
            document_context=[],
            history=None,
            user_id=record.user_id,
            run_id=new_record.run_id,
            thread_id=record.thread_id
        )

    asyncio.get_running_loop().run_in_executor(None, _run_bg)

    return AsyncChatStartResponse(
        run_id=new_record.run_id,
        status=AgentRunState.QUEUED,
        thread_id=record.thread_id,
        message=f"Retry started as a new run (original run '{run_id}' left untouched)."
    )


@app.post("/api/v1/chat/runs/{run_id}/continue", response_model=AsyncChatStartResponse)
async def continue_agent_run(run_id: str, req: Optional[ChatRequest] = None):
    """
    Resumes a run that is in WAITING_FOR_USER state (e.g. browser login required) by
    starting a new run continuing from the same thread/context — used by the UI's
    [Continue] affordance once the user has completed the required manual action
    (e.g. logging in inside the connected browser window).
    """
    record = async_agent_manager.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    if record.status != AgentRunState.WAITING_FOR_USER:
        raise HTTPException(status_code=400, detail=f"Run is in state '{record.status}', not WAITING_FOR_USER — nothing to continue.")

    continuation_prompt = (req.message.strip() if req and req.message and req.message.strip() else
                            "Continue the previous task now that the required user action has been completed.")

    new_record = async_agent_manager.create_run(
        user_id=record.user_id,
        thread_id=record.thread_id,
        prompt=continuation_prompt,
        model=record.model,
    )

    def _run_bg():
        execute_tool_calling_flow(
            user_prompt=continuation_prompt,
            active_plugin_ids=[],
            model_name=record.model,
            document_context=[],
            history=[{"role": "user", "content": record.prompt}, {"role": "assistant", "content": record.final_response or ""}],
            user_id=record.user_id,
            run_id=new_record.run_id,
            thread_id=record.thread_id
        )

    asyncio.get_running_loop().run_in_executor(None, _run_bg)

    return AsyncChatStartResponse(
        run_id=new_record.run_id,
        status=AgentRunState.QUEUED,
        thread_id=record.thread_id,
        message="Continuation started as a new run."
    )

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
    user_id = req.userId

    run_record = async_agent_manager.create_run(
        user_id=user_id,
        thread_id=thread_id,
        prompt=user_msg,
        model=target_model,
        run_id=req.runId
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

    # Use the length of the incoming history from PostgreSQL (req.history) as the
    # authoritative turn counter — the in-memory manager resets on server restart
    # and would show 0 after a restart even though many turns exist in the DB.
    history_count = len(req.history or []) + 2  # +2 for current user + AI turn

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
