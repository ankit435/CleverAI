import sys
import os
import time
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add python_project directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_PROJECT_DIR = os.path.join(BASE_DIR, "python_project")
if PY_PROJECT_DIR not in sys.path:
    sys.path.insert(0, PY_PROJECT_DIR)

from tools.executor import execute_tool_calling_flow
from browser.service import browser_service
from agent.async_manager import async_agent_manager

INTERNAL_SERVICE_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "clever-internal-agent-secret-key-prod-2026")

app = FastAPI(
    title="Clever AI Autonomous Multi-Tool & Browser Agent Server",
    description="Python FastAPI Agent Server powered by LangChain, LangGraph, and Playwright",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def enforce_internal_service_authentication(request: Request, call_next):
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    
    auth_header = request.headers.get("x-internal-service-key") or request.headers.get("authorization", "").replace("Bearer ", "")
    if auth_header != INTERNAL_SERVICE_KEY:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized: Direct access forbidden without valid internal service credentials."}
        )
    
    return await call_next(request)

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    threadId: Optional[str] = None
    activePlugins: Optional[List[str]] = Field(default_factory=list)
    documentContext: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    userId: Optional[int] = 1

class ToolResult(BaseModel):
    toolId: str
    toolName: str
    status: str
    executionTimeMs: int
    data: Dict[str, Any]

class ChatResponse(BaseModel):
    reply: str
    toolResults: Optional[List[ToolResult]] = None
    provider: str = "Autonomous Multi-Tool Agent"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

@app.get("/health")
def health_check():
    b_status = browser_service.get_status(user_id=1)
    return {
        "status": "HEALTHY",
        "service": "Clever AI Python Agent Microservice",
        "browser_connected": b_status.connected,
        "mode": b_status.mode
    }

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    try:
        reply_text, tool_results, provider_name = execute_tool_calling_flow(
            user_prompt=request.message,
            active_plugin_ids=request.activePlugins or [],
            model_name=request.model,
            document_context=request.documentContext,
            history=request.history,
            user_id=request.userId or 1,
            thread_id=request.threadId
        )

        formatted_tools = []
        if tool_results:
            for tr in tool_results:
                formatted_tools.append(ToolResult(
                    toolId=tr.get("toolId", "agent-tool"),
                    toolName=tr.get("toolName", "Agent Tool"),
                    status=tr.get("status", "success"),
                    executionTimeMs=tr.get("executionTimeMs", 25),
                    data=tr.get("data", {})
                ))

        return ChatResponse(
            reply=reply_text,
            toolResults=formatted_tools if formatted_tools else None,
            provider=provider_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
    except Exception as e:
        print(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from documents import convert_upload
from fastapi import UploadFile, File
from browser.schema import BrowserMode

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

@app.get("/api/v1/browser/status")
def browser_get_status(userId: Optional[int] = 1):
    status = browser_service.get_status(user_id=userId or 1)
    return status.model_dump()

@app.post("/api/v1/chat/async")
async def chat_async_endpoint(request: ChatRequest):
    try:
        from agent.async_manager import async_agent_manager
        run_record = async_agent_manager.create_run(
            user_id=request.userId or 1,
            thread_id=request.threadId or "default-thread",
            prompt=request.message,
            model=request.model or os.getenv("DEFAULT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        )

        import threading
        def _run_bg():
            try:
                execute_tool_calling_flow(
                    user_prompt=request.message,
                    active_plugin_ids=request.activePlugins or [],
                    model_name=request.model,
                    document_context=request.documentContext,
                    history=request.history,
                    user_id=request.userId or 1,
                    run_id=run_record.run_id,
                    thread_id=request.threadId
                )
            except Exception as ex:
                print(f"Async run error: {ex}")

        threading.Thread(target=_run_bg, daemon=True).start()

        return {
            "success": True,
            "status": "QUEUED",
            "runId": run_record.run_id,
            "threadId": request.threadId,
            "message": "Agent execution initiated asynchronously."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
