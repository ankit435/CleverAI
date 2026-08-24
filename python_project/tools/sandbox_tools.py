"""Sandbox Execution Tools — local code & shell execution for the Sandbox Agent.

SECURITY NOTE (explicit product decision — revisit before any production/multi-tenant
deployment): per project owner's instruction, these tools currently execute directly
on the host machine with NO container/VM isolation, to allow fast local testing of the
Sandbox Agent end-to-end.

TODO(sandbox-hardening): before exposing this to untrusted/production users, wrap
`execute_shell_command` / `execute_python_code` inside an isolated Docker container
(no host filesystem or network access by default). `config.py`'s `sandbox_execution_mode`
setting already exists as the switch for that future mode — this module only needs to
branch on it once the container runner is implemented.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from config import settings

DEFAULT_TIMEOUT_SECONDS = settings.sandbox_command_timeout_seconds
MAX_OUTPUT_CHARS = settings.sandbox_max_output_chars


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    hidden = len(text) - MAX_OUTPUT_CHARS
    return f"{text[:MAX_OUTPUT_CHARS]}\n...[truncated {hidden} more characters]"


def _run_subprocess(cmd: Any, cwd: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or None,
        )
        stdout = _truncate(proc.stdout.strip())
        stderr = _truncate(proc.stderr.strip())
        status = "success" if proc.returncode == 0 else "error"
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "status": status,
            "duration_ms": int((time.time() - start) * 1000),
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s.",
            "exit_code": 124,
            "status": "timeout",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "exit_code": 1,
            "status": "error",
            "duration_ms": int((time.time() - start) * 1000),
        }


def _format_execution_result(header: str, result: Dict[str, Any]) -> str:
    return (
        f"{header}\n"
        f"[exit_code={result['exit_code']} status={result['status']} duration={result['duration_ms']}ms]\n"
        f"stdout:\n{result['stdout'] or '(empty)'}\n"
        f"stderr:\n{result['stderr'] or '(empty)'}"
    )


@tool
def execute_shell_command(command: str, working_directory: Optional[str] = None) -> str:
    """
    Execute an arbitrary shell/bash command on the local host (unsandboxed local dev
    mode) and return stdout/stderr/exit code. Use for installing packages, running
    scripts/binaries, or any command-line operation.
    Args:
        command: The full shell command to execute (e.g. 'pip install requests', 'ls -la').
        working_directory: Optional absolute path to run the command from.
    """
    result = _run_subprocess(command, cwd=working_directory)
    return _format_execution_result(f"$ {command}", result)


@tool
def execute_python_code(code: str, working_directory: Optional[str] = None) -> str:
    """
    Execute a Python script in an isolated subprocess and return its stdout/stderr/exit
    code. Use for data processing, calculations, algorithms, or validating logic.
    Args:
        code: Full Python source code to execute.
        working_directory: Optional absolute path to run the script from.
    """
    cleaned = code.strip()
    for fence in ("```python", "```py", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(cleaned)
        result = _run_subprocess(
            [sys.executable, str(tmp_path)],
            cwd=working_directory or tempfile.gettempdir(),
        )
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return _format_execution_result(f"```python\n{cleaned}\n```", result)


@tool
def read_file(path: str, max_chars: int = 4000) -> str:
    """
    Read and return the text contents of a local file.
    Args:
        path: Absolute or relative file path to read.
        max_chars: Maximum characters to return (truncates longer files).
    """
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        return content[:max_chars] if len(content) <= max_chars else _truncate(content[:max_chars])
    except Exception as exc:
        return f"Error reading '{path}': {exc}"


@tool
def write_file(path: str, content: str) -> str:
    """
    Write text content to a local file, creating parent directories if needed. Use this
    to produce downloadable artifacts (scripts, reports, data files) for the user.
    Args:
        path: Absolute or relative destination file path.
        content: Full text content to write.
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to '{target}'."
    except Exception as exc:
        return f"Error writing '{path}': {exc}"


@tool
def list_directory(path: str = ".") -> str:
    """
    List files and subdirectories within a given directory path.
    Args:
        path: Directory path to list (defaults to current working directory).
    """
    try:
        entries: List[str] = sorted(os.listdir(path))
        if not entries:
            return f"'{path}' is empty."
        return "\n".join(entries[:200])
    except Exception as exc:
        return f"Error listing '{path}': {exc}"


@tool
def finish_sandbox_task(result: str) -> str:
    """
    TERMINAL TOOL: call this ONLY when the sandbox task is fully complete and verified.
    Pass the complete, concrete, user-facing Markdown summary (including exact outputs
    observed) to `result`.
    Args:
        result: The complete final user-facing Markdown answer.
    """
    return f"[TASK_COMPLETED]: {result}"


ALL_SANDBOX_TOOLS = [
    execute_shell_command,
    execute_python_code,
    read_file,
    write_file,
    list_directory,
    finish_sandbox_task,
]
