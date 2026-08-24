"""Bridges Stagehand's provider-neutral LLM callback protocol to CleverAI's own
NVIDIA NIM-backed `get_chat_model()`.

Stagehand normally calls out to OpenAI/Anthropic/Google/Groq/Cerebras (or its
hosted "Model Gateway", which additionally requires a Browserbase cloud session).
None of those are available here — this project only has an `NVIDIA_API_KEY`.
Stagehand's Python SDK explicitly supports "bring your own LLM": pass an async
`generate(params) -> result` callable instead of a model name, and Stagehand
routes every internal `act`/`observe`/`extract` reasoning call through it. This
module implements that callable on top of `models.get_chat_model()`, so the
Browser Agent's AI reasoning uses the exact same NVIDIA-hosted model as the rest
of the app — no extra API key, no extra billing relationship.
"""
import json
import re
from typing import Any, Dict, List, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models import get_chat_model

try:
    from stagehand.client_models import LLMGenerateInput, LLMGenerateOutput
    from stagehand._generated.models import (
        LLMMessageGenerateParams,
        LLMMessageGenerateResult,
        LLMStructuredGenerateParams,
        LLMStructuredGenerateResult,
        LLMRole,
        LLMTextContent,
    )
except ImportError:  # pragma: no cover - surfaced clearly at call time instead
    LLMGenerateInput = Any  # type: ignore
    LLMGenerateOutput = Any  # type: ignore


def _extract_text(content: Any) -> str:
    """Flatten a Stagehand message content block (or list of blocks) to plain text."""
    blocks = content if isinstance(content, list) else [content]
    parts: List[str] = []
    for block in blocks:
        root = getattr(block, "root", block)
        text = getattr(root, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _to_langchain_messages(params: Union["LLMStructuredGenerateParams", "LLMMessageGenerateParams"]) -> List[Any]:
    messages: List[Any] = []
    if params.system_prompt:
        messages.append(SystemMessage(content=params.system_prompt))
    for msg in params.messages:
        text = _extract_text(msg.content)
        if msg.role == LLMRole.assistant:
            messages.append(AIMessage(content=text))
        else:
            messages.append(HumanMessage(content=text))
    return messages


def _parse_json_object(raw_text: str) -> Dict[str, Any]:
    """Extract the first JSON object from a model response (tolerating code fences/prose)."""
    candidate = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace_match:
            candidate = brace_match.group(0)
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"value": raw_text}


async def nvidia_generate(params: "LLMGenerateInput") -> "LLMGenerateOutput":
    """The `LLMGenerateCallback` passed to `Stagehand.create(model=...)`.

    Handles both Stagehand request shapes:
      * `LLMMessageGenerateParams` (act/observe — free-form text reasoning)
      * `LLMStructuredGenerateParams` (extract — must return JSON matching a schema)
    """
    is_structured = isinstance(params, LLMStructuredGenerateParams)
    messages = _to_langchain_messages(params)

    if is_structured:
        schema_name = getattr(params.response_format, "name", "result")
        schema_def = getattr(params.response_format, "schema_", None)
        schema_hint = json.dumps(schema_def.model_dump() if hasattr(schema_def, "model_dump") else schema_def)
        messages.append(
            SystemMessage(
                content=(
                    f"Respond with ONLY a single valid JSON object (no prose, no markdown fences) "
                    f"matching this JSON schema named '{schema_name}':\n{schema_hint}"
                )
            )
        )

    llm = get_chat_model(temperature=params.temperature if params.temperature is not None else 0.2)
    response = llm.invoke(messages)
    raw_text = response.content if isinstance(response.content, str) else str(response.content)

    if is_structured:
        structured = _parse_json_object(raw_text)
        return LLMStructuredGenerateResult(
            role=LLMRole.assistant,
            content=LLMTextContent(type="text", text=raw_text),
            output_format="json_schema",
            structured_content=structured,
        )

    return LLMMessageGenerateResult(
        role=LLMRole.assistant,
        content=LLMTextContent(type="text", text=raw_text),
        output_format="text",
    )
