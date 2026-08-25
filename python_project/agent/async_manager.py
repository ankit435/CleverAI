"""Asynchronous Agent Run Manager: Stateful execution, explicit states, timeouts, and cancellation."""
import time
import uuid
import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncGenerator
from pydantic import BaseModel, Field

logger = logging.getLogger("agent.runner")

# ==========================================
# EXPLICIT COMPONENT TIMEOUT SPECIFICATIONS
# ==========================================
NIM_CONNECT_TIMEOUT = 5.0           # TCP handshake / SSL negotiation to api.nvidia.com
NIM_READ_TIMEOUT = 30.0             # Max time waiting for response stream / tokens from NIM
NIM_REQUEST_TIMEOUT = 30.0          # Total per-single LLM inference budget

BROWSER_CONNECT_TIMEOUT = 5.0       # CDP connection to existing/managed browser
BROWSER_NAVIGATION_TIMEOUT = 25.0   # Page navigation (page.goto)
BROWSER_ACTION_TIMEOUT = 15.0       # DOM interaction (click, type, hover, scroll)

INDIVIDUAL_TOOL_TIMEOUT = 20.0      # Maximum duration for an individual tool
AGENT_ITERATION_TIMEOUT = 35.0      # Per-iteration limit (LLM + action)
AGENT_TOTAL_TIMEOUT = 300.0         # Full multi-step agent run budget
API_REQUEST_TIMEOUT = 15.0          # Ingestion / dispatch HTTP socket timeout

# Aliases for backward-compatibility
HTTP_REQUEST_TIMEOUT = API_REQUEST_TIMEOUT
LLM_REQUEST_TIMEOUT = NIM_REQUEST_TIMEOUT
AGENT_TOTAL_RUN_TIMEOUT = AGENT_TOTAL_TIMEOUT

class AgentRunState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_LLM = "WAITING_FOR_LLM"
    WAITING_FOR_BROWSER = "WAITING_FOR_BROWSER"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"                # some, but not all, requested items were verified
    NO_RESULTS = "NO_RESULTS"          # executed correctly, nothing matched the request
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"  # the needed capability genuinely could not be used
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

# Terminal states: no further progress will occur without new user input.
TERMINAL_RUN_STATES = {
    AgentRunState.COMPLETED, AgentRunState.PARTIAL, AgentRunState.NO_RESULTS,
    AgentRunState.TOOL_UNAVAILABLE, AgentRunState.FAILED, AgentRunState.TIMEOUT,
    AgentRunState.CANCELLED,
}

class ErrorType(str, Enum):
    NIM_TIMEOUT = "NIM_TIMEOUT"
    NIM_CONNECTION_ERROR = "NIM_CONNECTION_ERROR"
    NIM_RATE_LIMIT = "NIM_RATE_LIMIT"
    NIM_SERVER_ERROR = "NIM_SERVER_ERROR"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    BROWSER_TIMEOUT = "BROWSER_TIMEOUT"
    BROWSER_DISCONNECTED = "BROWSER_DISCONNECTED"
    USER_CANCELLED = "USER_CANCELLED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class TimingEvent(BaseModel):
    event_name: str
    run_id: str
    user_id: int
    iteration: int = 1
    tool: Optional[str] = None
    duration_ms: int = 0
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

class TimeoutDiagnostic(BaseModel):
    component: str
    timeout_type: str
    configured_timeout_ms: int
    elapsed_ms: int
    operation: str
    upstream: str
    retry_count: int = 0
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

class AgentRunRecord(BaseModel):
    run_id: str
    user_id: int
    thread_id: str
    prompt: str
    model: str
    status: AgentRunState = AgentRunState.QUEUED
    current_action: Optional[str] = None
    iteration: int = 0
    max_iterations: int = 6
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    execution_time_ms: int = 0
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    final_response: Optional[str] = None
    error: Optional[str] = None
    timing_logs: List[TimingEvent] = Field(default_factory=list)
    diagnostics: List[TimeoutDiagnostic] = Field(default_factory=list)
    # Task-completion verification metadata (distinct from `status`/`error`
    # above): what was actually verified against the user's request, so the
    # UI/final response can never claim more than what was proven true.
    verified_count: Optional[int] = None
    requested_count: Optional[int] = None

class AsyncAgentManager:
    """Central registry and executor for asynchronous long-running agent runs."""


    def __init__(self):
        self._runs: Dict[str, AgentRunRecord] = {}
        self._cancellation_events: Dict[str, asyncio.Event] = {}
        self._queues: Dict[str, List[asyncio.Queue]] = {}

    def create_run(
        self,
        user_id: int,
        thread_id: str,
        prompt: str,
        model: str,
        run_id: Optional[str] = None
    ) -> AgentRunRecord:
        """Create and register a new stateful AgentRun."""
        rid = run_id or f"run_{str(uuid.uuid4())[:12]}"
        record = AgentRunRecord(
            run_id=rid,
            user_id=user_id,
            thread_id=thread_id,
            prompt=prompt,
            model=model,
            status=AgentRunState.QUEUED,
            started_at=time.time()
        )
        self._runs[rid] = record
        self._cancellation_events[rid] = asyncio.Event()
        self._queues[rid] = []

        self.log_timing(rid, "agent_run_started", 0, iteration=0)
        return record

    def get_run(self, run_id: str) -> Optional[AgentRunRecord]:
        return self._runs.get(run_id)

    def is_cancelled(self, run_id: str) -> bool:
        evt = self._cancellation_events.get(run_id)
        return evt.is_set() if evt else False

    def cancel_run(self, run_id: str) -> bool:
        """Signal cancellation for an active agent run."""
        record = self._runs.get(run_id)
        if not record:
            return False

        if record.status in TERMINAL_RUN_STATES:
            return False

        evt = self._cancellation_events.get(run_id)
        if evt:
            evt.set()

        record.status = AgentRunState.CANCELLED
        record.completed_at = time.time()
        record.execution_time_ms = int((record.completed_at - record.started_at) * 1000)
        record.error = "Agent run was cancelled by user."

        self.log_timing(run_id, "agent_run_cancelled", record.execution_time_ms)
        self._broadcast(run_id, {"type": "status", "status": "CANCELLED", "message": "Run cancelled"})
        return True

    def set_state(self, run_id: str, state: AgentRunState, current_action: Optional[str] = None):
        """Update live execution state."""
        record = self._runs.get(run_id)
        if record and record.status != AgentRunState.CANCELLED:
            record.status = state
            if current_action:
                record.current_action = current_action
            self._broadcast(run_id, {"type": "state", "status": state.value, "current_action": current_action})

    def log_timing(
        self,
        run_id: str,
        event_name: str,
        duration_ms: int,
        iteration: int = 1,
        tool: Optional[str] = None
    ):
        """Structured timing logger without logging sensitive tokens/secrets."""
        record = self._runs.get(run_id)
        if not record:
            return

        ev = TimingEvent(
            event_name=event_name,
            run_id=run_id,
            user_id=record.user_id,
            iteration=iteration,
            tool=tool,
            duration_ms=duration_ms
        )
        record.timing_logs.append(ev)
        # Keep the record's live iteration counter monotonic and accurate so
        # `GET /chat/runs/{run_id}` reflects real progress instead of staying
        # stuck at whatever value was set once at run creation.
        if iteration > record.iteration:
            record.iteration = iteration
        logger.info(f"[{event_name}] run_id={run_id} iter={iteration} tool={tool} duration={duration_ms}ms")
        self._broadcast(run_id, {"type": "timing", "event": ev.model_dump()})

    def log_diagnostic(
        self,
        run_id: str,
        component: str,
        timeout_type: str,
        configured_timeout_ms: int,
        elapsed_ms: int,
        operation: str,
        upstream: str,
        retry_count: int = 0
    ):
        """Record diagnostic details on timeouts or degradations."""
        record = self._runs.get(run_id)
        if not record:
            return

        diag = TimeoutDiagnostic(
            component=component,
            timeout_type=timeout_type,
            configured_timeout_ms=configured_timeout_ms,
            elapsed_ms=elapsed_ms,
            operation=operation,
            upstream=upstream,
            retry_count=retry_count
        )
        record.diagnostics.append(diag)
        logger.warning(
            f"⚠️ TIMEOUT DIAGNOSTIC [{component}] op='{operation}' type='{timeout_type}' "
            f"configured={configured_timeout_ms}ms elapsed={elapsed_ms}ms upstream='{upstream}' retries={retry_count}"
        )
        self._broadcast(run_id, {"type": "diagnostic", "data": diag.model_dump()})

    def complete_run(
        self,
        run_id: str,
        response_text: str,
        tool_results: List[Dict[str, Any]],
        error: Optional[str] = None,
        is_timeout: bool = False,
        completion_status: Optional[AgentRunState] = None,
        verified_count: Optional[int] = None,
        requested_count: Optional[int] = None,
    ):
        """
        Finalize an agent run and notify listeners.

        `completion_status` lets callers report the TRUE task-completion verdict
        (COMPLETED / PARTIAL / NO_RESULTS / TOOL_UNAVAILABLE / WAITING_FOR_USER /
        ...) instead of this method always collapsing every non-error outcome
        into a blanket COMPLETED. If omitted, falls back to the previous
        error/is_timeout-only inference for backward compatibility.
        """
        record = self._runs.get(run_id)
        if not record:
            return

        record.completed_at = time.time()
        record.execution_time_ms = int((record.completed_at - record.started_at) * 1000)
        record.final_response = response_text
        record.tool_results = tool_results
        record.error = error
        record.verified_count = verified_count
        record.requested_count = requested_count

        if completion_status is not None:
            record.status = completion_status
            self.log_timing(run_id, f"agent_run_{completion_status.value.lower()}", record.execution_time_ms)
        elif is_timeout:
            record.status = AgentRunState.TIMEOUT
            self.log_timing(run_id, "agent_run_timeout", record.execution_time_ms)
        elif error:
            record.status = AgentRunState.FAILED
            self.log_timing(run_id, "agent_run_failed", record.execution_time_ms)
        else:
            record.status = AgentRunState.COMPLETED
            self.log_timing(run_id, "agent_run_completed", record.execution_time_ms)

        self._broadcast(run_id, {
            "type": "completed",
            "status": record.status.value,
            "reply": response_text,
            "tool_results": tool_results,
            "error": error,
            "execution_time_ms": record.execution_time_ms,
            "verified_count": verified_count,
            "requested_count": requested_count,
        })

    def _broadcast(self, run_id: str, message: Dict[str, Any]):
        """Broadcast live events to SSE subscriber queues."""
        queues = self._queues.get(run_id, [])
        for q in queues:
            try:
                q.put_nowait(message)
            except Exception:
                pass

    async def stream_events(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to live Server-Sent Events stream for a specific run."""
        record = self._runs.get(run_id)
        if not record:
            yield {"type": "error", "message": "Run not found"}
            return

        q: asyncio.Queue = asyncio.Queue()
        if run_id not in self._queues:
            self._queues[run_id] = []
        self._queues[run_id].append(q)

        # Yield current initial state
        yield {
            "type": "initial",
            "run_id": record.run_id,
            "status": record.status.value,
            "started_at": record.started_at
        }

        try:
            while True:
                msg = await q.get()
                yield msg
                if msg.get("type") in ("completed", "status") and msg.get("status") in {s.value for s in TERMINAL_RUN_STATES}:
                    break
        finally:
            if run_id in self._queues and q in self._queues[run_id]:
                self._queues[run_id].remove(q)

async_agent_manager = AsyncAgentManager()
