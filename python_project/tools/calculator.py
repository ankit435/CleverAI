"""Tool 4: Calculator and Mathematical Evaluation Engine."""
import math
import re
from typing import Any, Dict
from langchain_core.tools import tool

SAFE_MATH_NAMES = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sqrt': math.sqrt,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'pi': math.pi,
    'e': math.e,
    'abs': abs,
    'round': round,
    'pow': pow,
    'floor': math.floor,
    'ceil': math.ceil
}

def evaluate_math_expression(expression: str) -> Dict[str, Any]:
    """Safely parse and calculate math expressions."""
    cleaned = expression.strip()
    
    # Handle percentage syntax like "15% of 250" -> "0.15 * 250"
    percent_match = re.match(r'([\d.]+)\s*%\s*(?:of)?\s*([\d.]+)', cleaned, re.IGNORECASE)
    if percent_match:
        p, val = percent_match.groups()
        cleaned = f"({p} / 100) * {val}"

    # Replace ^ with **
    cleaned = cleaned.replace('^', '**')
    
    # Validate allowable characters for safe math evaluation
    if not re.match(r'^[0-9a-zA-Z_\s\+\-\*\/\%\(\)\.\,]+$', cleaned):
        return {
            "expression": expression,
            "result": "Invalid characters in mathematical expression.",
            "status": "error",
            "formatted": f"⚠️ **Math Error**: Invalid expression `{expression}`"
        }

    try:
        # Safe restricted eval with only math symbols
        result = eval(cleaned, {"__builtins__": {}}, SAFE_MATH_NAMES)
        formatted = f"**Calculation:** `{expression}`\n\n**Result:** `{result}`"
        return {
            "expression": expression,
            "result": result,
            "status": "success",
            "formatted": formatted
        }
    except Exception as err:
        return {
            "expression": expression,
            "result": str(err),
            "status": "error",
            "formatted": f"⚠️ **Math Error**: Unable to evaluate `{expression}` ({str(err)})"
        }

@tool
def calculate(expression: str) -> str:
    """
    Perform mathematical calculations, arithmetic, percentages, powers, square roots, and trigonometric calculations.
    Args:
        expression: Mathematical expression string to calculate (e.g. 'sqrt(144) + 2**8', '18% of 4500').
    """
    data = evaluate_math_expression(expression)
    return data["formatted"]
