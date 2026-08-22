"""Tool 2: Safe Isolated Code Sandbox Interpreter for Python execution."""
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from langchain_core.tools import tool

TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 4000

def execute_sandboxed_python(code: str) -> Dict[str, Any]:
    """Execute Python code in a separate subprocess sandbox and capture output."""
    start_time = time.time()
    
    cleaned_code = code.strip()
    if cleaned_code.startswith("```python"):
        cleaned_code = cleaned_code[9:]
    elif cleaned_code.startswith("```"):
        cleaned_code = cleaned_code[3:]
    if cleaned_code.endswith("```"):
        cleaned_code = cleaned_code[:-3]
    cleaned_code = cleaned_code.strip()

    temporary_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as temp:
            temporary_file = Path(temp.name)
            temp.write(cleaned_code)

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

        output = stdout if stdout else (stderr if stderr else "[Process completed with no output]")
        status = "success" if exit_code == 0 else "error"
        
    except subprocess.TimeoutExpired:
        output = f"Execution timed out after {TIMEOUT_SECONDS} seconds."
        status = "timeout"
        exit_code = 124
    except Exception as err:
        output = f"Execution failed: {str(err)}"
        status = "error"
        exit_code = 1
    finally:
        if temporary_file and temporary_file.exists():
            temporary_file.unlink(missing_ok=True)

    execution_duration_ms = int((time.time() - start_time) * 1000)
    formatted = f"```python\n{cleaned_code}\n```\n\n**Output:**\n```\n{output}\n```"

    return {
        "code": cleaned_code,
        "output": output,
        "status": status,
        "exit_code": exit_code,
        "execution_time_ms": execution_duration_ms,
        "formatted": formatted
    }

@tool
def code_interpreter(code: str) -> str:
    """
    Execute Python code in a safe sandbox to perform calculations, data processing, algorithms, or script validation.
    Args:
        code: Valid Python code string to run.
    """
    data = execute_sandboxed_python(code)
    return data["formatted"]
