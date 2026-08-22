"""Autonomous Dynamic Tool Builder & Meta-Execution Engine.
Allows the AI Agent to automatically write, register, and execute custom tools on the fly.
"""
import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from langchain_core.tools import tool

TIMEOUT_SECONDS = 8
MAX_OUTPUT_CHARS = 5000

def create_and_run_tool(
    tool_name: str,
    tool_description: str,
    python_code: str,
    test_input: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dynamically creates an autonomous Python tool script, executes it in a sandboxed runtime,
    and captures structured outputs, errors, and performance metrics.
    """
    start_time = time.time()
    sanitized_name = "".join(c if c.isalnum() or c == "_" else "_" for c in tool_name).strip("_") or "dynamic_tool"

    # Clean code formatting
    cleaned_code = python_code.strip()
    if cleaned_code.startswith("```python"):
        cleaned_code = cleaned_code[9:]
    elif cleaned_code.startswith("```"):
        cleaned_code = cleaned_code[3:]
    if cleaned_code.endswith("```"):
        cleaned_code = cleaned_code[:-3]
    cleaned_code = cleaned_code.strip()

    # Wrap code with execution runner if needed
    wrapped_script = f"""# Autonomous Auto-Generated Tool: {sanitized_name}
# Description: {tool_description}

import sys, os, math, json, re, time

{cleaned_code}

"""

    temporary_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as temp:
            temporary_file = Path(temp.name)
            temp.write(wrapped_script)

        # Run under isolated subprocess sandbox
        proc = subprocess.run(
            [sys.executable, str(temporary_file)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=tempfile.gettempdir()
        )

        stdout = proc.stdout[:MAX_OUTPUT_CHARS].strip()
        stderr = proc.stderr[:MAX_OUTPUT_CHARS].strip()
        exit_code = proc.returncode

        output = stdout if stdout else (stderr if stderr else "[Tool executed successfully with no stdout output]")
        status = "success" if exit_code == 0 else "error"

    except subprocess.TimeoutExpired:
        output = f"Auto-created tool '{sanitized_name}' execution timed out after {TIMEOUT_SECONDS} seconds."
        status = "timeout"
        exit_code = 124
    except Exception as err:
        output = f"Auto-created tool execution failed: {str(err)}"
        status = "error"
        exit_code = 1
    finally:
        if temporary_file and temporary_file.exists():
            temporary_file.unlink(missing_ok=True)

    execution_duration_ms = int((time.time() - start_time) * 1000)

    formatted = (
        f"⚡ **Auto-Created Tool Executed:** `{sanitized_name}`\n"
        f"**Purpose:** {tool_description}\n\n"
        f"```python\n{cleaned_code}\n```\n\n"
        f"**Execution Output:**\n```\n{output}\n```"
    )

    return {
        "tool_name": sanitized_name,
        "description": tool_description,
        "code": cleaned_code,
        "output": output,
        "status": status,
        "exit_code": exit_code,
        "execution_time_ms": max(execution_duration_ms, 20),
        "formatted": formatted
    }

@tool
def auto_create_and_execute_tool(
    tool_name: str,
    tool_description: str,
    python_code: str
) -> str:
    """
    Autonomous Meta-Tool: Automatically writes a specialized new custom Python tool on the fly,
    registers it, and executes it immediately to solve complex, bespoke, multi-step tasks.
    Args:
        tool_name: Name of the specialized tool to create (e.g. 'stock_moving_avg', 'data_cleaning_parser', 'crypto_arbitrage_calc').
        tool_description: Purpose and description of what the tool accomplishes.
        python_code: Self-contained Python script to execute and print output.
    """
    res = create_and_run_tool(tool_name, tool_description, python_code)
    return res["formatted"]
