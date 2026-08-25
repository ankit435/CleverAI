"""Shared execution-status taxonomy for every tool/agent in this codebase.

This module exists to enforce ONE conceptual rule everywhere: tool
availability, tool execution, tool result, result verification, and task
completion are five different questions with five different answers. Nothing
in this codebase should collapse them into a single "success"/"failed" flag.

    TOOL_AVAILABILITY  -> can this capability even be used right now?
    EXECUTION_STATUS   -> did the tool operation itself succeed, fail, or time out?
    RESULT_STATUS      -> did execution produce usable data, no data, or partial data?
    TASK_COMPLETION    -> did the user's actual request get satisfied (verified)?

A tool call can be AVAILABLE + EXECUTION_SUCCESS + NO_RESULTS all at once —
that is a completely valid, non-error outcome and must never be reported to
the user as "this tool is unavailable."
"""
from enum import Enum


class ToolAvailability(str, Enum):
    """Whether a capability can even be invoked right now — independent of
    whether any particular invocation then succeeds, fails, or finds data."""
    AVAILABLE = "available"
    DEGRADED = "degraded"                  # works, but with reduced reliability/capability
    UNAVAILABLE = "unavailable"            # not registered, disabled, or cannot be initialized
    AUTH_REQUIRED = "auth_required"        # exists, but needs the user to authenticate first


class ExecutionStatus(str, Enum):
    """Whether the tool OPERATION itself completed — says nothing about the
    business result (e.g. whether any matching data was found)."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ResultStatus(str, Enum):
    """What the tool operation actually produced, given that it executed."""
    RESULTS_FOUND = "results_found"
    NO_RESULTS = "no_results"
    PARTIAL_RESULTS = "partial_results"
    INVALID_RESULT = "invalid_result"
    ERROR = "error"


class TaskCompletionStatus(str, Enum):
    """The user-facing verdict on whether the ORIGINAL user request was
    actually satisfied — distinct from any single tool's execution/result
    status, and distinct from the agent run simply reaching a stop point."""
    COMPLETED = "completed"                        # fully satisfied & verified
    PARTIAL = "partial"                            # some but not all requested items verified
    NO_RESULTS = "no_results"                      # executed correctly, nothing matched
    FAILED = "failed"                              # could not execute the request
    TIMEOUT = "timeout"                            # execution exceeded its time budget
    CANCELLED = "cancelled"                        # user (or system) cancelled the run
    WAITING_FOR_USER = "waiting_for_user"           # blocked on required human input (e.g. login)
    TOOL_UNAVAILABLE = "tool_unavailable"           # the needed capability genuinely can't be used


# Statuses that represent a genuine terminal stop of the run (no further
# progress will happen without new user input). Used by the SSE/telemetry
# layer to decide whether to keep waiting or close out the stream.
TERMINAL_COMPLETION_STATUSES = {
    TaskCompletionStatus.COMPLETED,
    TaskCompletionStatus.PARTIAL,
    TaskCompletionStatus.NO_RESULTS,
    TaskCompletionStatus.FAILED,
    TaskCompletionStatus.TIMEOUT,
    TaskCompletionStatus.CANCELLED,
    TaskCompletionStatus.TOOL_UNAVAILABLE,
}


def result_status_from_count(verified_count: int, requested_count: int) -> ResultStatus:
    """Pure helper: derive a ResultStatus from a verified/requested item count pair."""
    if requested_count <= 0:
        return ResultStatus.RESULTS_FOUND if verified_count > 0 else ResultStatus.NO_RESULTS
    if verified_count <= 0:
        return ResultStatus.NO_RESULTS
    if verified_count < requested_count:
        return ResultStatus.PARTIAL_RESULTS
    return ResultStatus.RESULTS_FOUND


def task_completion_from_counts(verified_count: int, requested_count: int) -> TaskCompletionStatus:
    """Pure helper: derive the user-facing TaskCompletionStatus from verified/requested counts."""
    status = result_status_from_count(verified_count, requested_count)
    if status == ResultStatus.RESULTS_FOUND:
        return TaskCompletionStatus.COMPLETED
    if status == ResultStatus.PARTIAL_RESULTS:
        return TaskCompletionStatus.PARTIAL
    return TaskCompletionStatus.NO_RESULTS
