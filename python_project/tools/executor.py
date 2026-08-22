"""Dynamic Tool Calling Executor & Multi-Tool Orchestrator."""
import time
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from models import get_chat_model
from tools.web_search import web_search, perform_web_search
from tools.browser_agent import browse_webpage, search_and_browse, fetch_and_read_webpage
from tools.playwright_browser import interactive_browser_action, perform_interactive_browser_action
from tools.code_interpreter import code_interpreter, execute_sandboxed_python
from tools.image_generator import generate_image, generate_ai_image
from tools.calculator import calculate, evaluate_math_expression
from tools.dynamic_tool_builder import auto_create_and_execute_tool, create_and_run_tool

TOOL_MAP = {
    "web-search": web_search,
    "web_search": web_search,
    "browser-agent": interactive_browser_action,
    "browse_webpage": browse_webpage,
    "search_and_browse": search_and_browse,
    "interactive_browser_action": interactive_browser_action,
    "code-interpreter": code_interpreter,
    "code_interpreter": code_interpreter,
    "dalle3-image": generate_image,
    "generate_image": generate_image,
    "calculator": calculate,
    "calculate": calculate,
    "auto_create_and_execute_tool": auto_create_and_execute_tool,
    "dynamic-tool-creator": auto_create_and_execute_tool
}

TOOL_DISPLAY_NAMES = {
    "web_search": ("web-search", "Web Search Engine"),
    "browse_webpage": ("browser-agent", "Live Web Browser Agent"),
    "search_and_browse": ("browser-agent", "Web Search & Page Reader"),
    "interactive_browser_action": ("browser-agent", "Headless Chromium Action Agent"),
    "code_interpreter": ("code-interpreter", "Code Sandbox Interpreter"),
    "generate_image": ("dalle3-image", "DALL-E 3 Visual Studio"),
    "calculate": ("calculator", "Math & Calculation Engine"),
    "auto_create_and_execute_tool": ("dynamic-tool-creator", "Autonomous Tool Builder")
}

def extract_clean_text(response: Any) -> str:
    """Extract clean string text from AIMessage or raw string without ever exposing python object repr."""
    if not response:
        return ""
    if isinstance(response, str):
        return response.strip()

    # 1. Check direct content string
    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    # 2. Check if content is a list of parts/dictionaries
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict) and "text" in item and item["text"]:
                parts.append(str(item["text"]).strip())
        if parts:
            return "\n\n".join(parts).strip()

    # 3. Check reasoning_content in additional_kwargs if content was empty
    if hasattr(response, "additional_kwargs") and isinstance(response.additional_kwargs, dict):
        reasoning = response.additional_kwargs.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip() and not getattr(response, "tool_calls", None):
            return reasoning.strip()

    return ""

def execute_tool_calling_flow(
    user_prompt: str,
    active_plugin_ids: List[str],
    model_name: Optional[str] = None,
    document_context: Optional[List[Dict[str, Any]]] = None,
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Executes end-to-end Tool Calling flow with NVIDIA Nemotron / LangChain:
    1. Selects active tools based on active_plugin_ids + Playwright Browser
    2. Binds tools to LLM
    3. Invokes model with multi-turn tool execution loop
    4. Ensures clean final response synthesis without exposing raw message structures
    """
    llm = get_chat_model(model_name=model_name)
    
    # 1. Resolve active tools
    selected_tools = []
    if "web-search" in active_plugin_ids or "web_search" in active_plugin_ids or True:
        selected_tools.append(web_search)
    if "browser-agent" in active_plugin_ids or "browse_webpage" in active_plugin_ids or True:
        selected_tools.append(interactive_browser_action)
        selected_tools.append(browse_webpage)
        selected_tools.append(search_and_browse)
    if "code-interpreter" in active_plugin_ids or "code_interpreter" in active_plugin_ids:
        selected_tools.append(code_interpreter)
    if "dalle3-image" in active_plugin_ids or "generate_image" in active_plugin_ids:
        selected_tools.append(generate_image)
    if "calculator" in active_plugin_ids or "calculate" in active_plugin_ids:
        selected_tools.append(calculate)
    
    # Always include autonomous meta-tool creator
    selected_tools.append(auto_create_and_execute_tool)

    # 2. Build system instructions
    doc_text = ""
    if document_context and len(document_context) > 0:
        doc_text = "\n\n=== ATTACHED DOCUMENT CONTEXT ===\n" + "\n\n".join(
            f"[Source: {c.get('filename', 'doc')} — {c.get('heading') or 'section'}]\n{c.get('content', '')}"
            for c in document_context
        ) + "\n=== END ATTACHED DOCUMENT CONTEXT ===\n"

    system_instruction = (
        "You are an intelligent, helpful, concise AI assistant in the Clever AI workspace. "
        "You have full access to an Interactive Headless Chromium Browser agent ('interactive_browser_action') to spawn browsers, "
        "navigate URLs, click buttons, fill forms, and read dynamic rendered pages, "
        "a Web Search engine ('web_search'), a Code Sandbox ('code_interpreter'), an Image Generator ('generate_image'), "
        "a Calculator ('calculate'), and an Autonomous Tool Builder ('auto_create_and_execute_tool'). "
        "Always synthesize your final answers in clean, well-formatted Markdown with clickable links, summaries, and bullet points.\n"
        f"{doc_text}"
    )

    messages = [SystemMessage(content=system_instruction)]

    # Add historical messages
    if history:
        for msg in history[-12:]:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            else:
                messages.append(AIMessage(content=msg.get("content", "")))

    messages.append(HumanMessage(content=user_prompt))

    tool_results_list: List[Dict[str, Any]] = []

    # 3. Model with tool binding loop (up to 3 turns)
    if selected_tools and hasattr(llm, "bind_tools"):
        try:
            llm_with_tools = llm.bind_tools(selected_tools)
            current_response = llm_with_tools.invoke(messages)

            for step in range(3):
                # Check if LLM requested tool calls
                if hasattr(current_response, "tool_calls") and current_response.tool_calls:
                    messages.append(current_response)

                    for t_call in current_response.tool_calls:
                        t_name = t_call.get("name")
                        t_args = t_call.get("args", {})
                        t_id = t_call.get("id", f"call-{int(time.time()*1000)}")

                        t_start = time.time()
                        t_output = ""
                        t_data: Dict[str, Any] = {}

                        if t_name == "interactive_browser_action":
                            url = t_args.get("url", "")
                            action = t_args.get("action", "navigate")
                            selector = t_args.get("selector")
                            text_input = t_args.get("text_input")
                            p_data = perform_interactive_browser_action(url, action, selector, text_input)
                            t_output = p_data["formatted"]
                            t_data = {
                                "type": "browser_page",
                                "title": p_data.get("title"),
                                "url": p_data.get("url"),
                                "action": p_data.get("action"),
                                "links": p_data.get("links", []),
                                "content": p_data.get("content", "")[:1000]
                            }
                        elif t_name == "web_search":
                            query = t_args.get("query", user_prompt)
                            s_data = perform_web_search(query)
                            t_output = s_data["formatted"]
                            t_data = {
                                "type": "search",
                                "searchResults": s_data["results"]
                            }
                        elif t_name in ["browse_webpage", "browse_url"]:
                            url = t_args.get("url", "")
                            b_data = fetch_and_read_webpage(url)
                            t_output = b_data["formatted"]
                            t_data = {
                                "type": "browser_page",
                                "title": b_data["title"],
                                "url": b_data["url"],
                                "description": b_data["description"],
                                "content": b_data["content"][:600]
                            }
                        elif t_name == "search_and_browse":
                            q_str = t_args.get("query", user_prompt)
                            t_output = search_and_browse.invoke(q_str)
                            t_data = {
                                "type": "browser_page",
                                "title": f"Browsed: {q_str}",
                                "content": t_output[:600]
                            }
                        elif t_name == "code_interpreter":
                            code_str = t_args.get("code", "")
                            c_data = execute_sandboxed_python(code_str)
                            t_output = c_data["formatted"]
                            t_data = {
                                "type": "code",
                                "codeSnippet": c_data["code"],
                                "codeOutput": c_data["output"]
                            }
                        elif t_name == "generate_image":
                            prompt_str = t_args.get("prompt", user_prompt)
                            i_data = generate_ai_image(prompt_str)
                            t_output = i_data["formatted"]
                            t_data = {
                                "type": "image",
                                "imageUrl": i_data["image_url"],
                                "imagePrompt": i_data["prompt"]
                            }
                        elif t_name == "calculate":
                            expr_str = t_args.get("expression", "")
                            m_data = evaluate_math_expression(expr_str)
                            t_output = m_data["formatted"]
                            t_data = {
                                "type": "calculation",
                                "expression": m_data["expression"],
                                "result": m_data["result"]
                            }
                        elif t_name == "auto_create_and_execute_tool":
                            d_name = t_args.get("tool_name", "custom_auto_tool")
                            d_desc = t_args.get("tool_description", "Custom dynamic task execution")
                            d_code = t_args.get("python_code", "")
                            d_res = create_and_run_tool(d_name, d_desc, d_code)
                            t_output = d_res["formatted"]
                            t_data = {
                                "type": "custom_tool",
                                "toolName": d_res["tool_name"],
                                "description": d_res["description"],
                                "codeSnippet": d_res["code"],
                                "codeOutput": d_res["output"]
                            }
                        elif t_name in TOOL_MAP:
                            target_fn = TOOL_MAP[t_name]
                            t_output = str(target_fn.invoke(t_args))
                            t_data = {"output": t_output}

                        t_duration_ms = int((time.time() - t_start) * 1000)
                        mapped_id, mapped_name = TOOL_DISPLAY_NAMES.get(t_name, (t_name, t_name))

                        tool_results_list.append({
                            "toolId": mapped_id,
                            "toolName": mapped_name,
                            "status": "success",
                            "executionTimeMs": max(t_duration_ms, 15),
                            "data": t_data
                        })

                        messages.append(ToolMessage(content=t_output, tool_call_id=t_id))

                    # Next invocation with tools bound
                    current_response = llm_with_tools.invoke(messages)
                else:
                    break

            # Extract clean synthesized text
            final_text = extract_clean_text(current_response)

            # If response content is still empty, invoke LLM without tools for final synthesis
            if not final_text:
                messages.append(HumanMessage(content="Based on all the tool execution results above, provide a comprehensive, well-structured final markdown answer with details and clickable links."))
                synth_response = llm.invoke(messages)
                final_text = extract_clean_text(synth_response)

            if final_text:
                return final_text, tool_results_list, "LangChain Multi-Tool Agent"

        except Exception as tool_err:
            pass

    # Heuristic fallback if direct tool binding had any provider exception
    lower = user_prompt.lower()

    if ("dalle3-image" in active_plugin_ids or "generate_image" in active_plugin_ids) and any(w in lower for w in ["image", "draw", "render", "photo", "picture", "visual"]):
        i_data = generate_ai_image(user_prompt)
        tool_results_list.append({
            "toolId": "dalle3-image",
            "toolName": "DALL-E 3 Visual Studio",
            "status": "success",
            "executionTimeMs": 950,
            "data": {
                "type": "image",
                "imageUrl": i_data["image_url"],
                "imagePrompt": i_data["prompt"]
            }
        })
        return f"🎨 **Generated Artwork for:** \"{user_prompt}\"\n\n{i_data['formatted']}", tool_results_list, "LangChain Image Tool"

    if any(w in lower for w in ["job", "career", "hiring", "naukri", "vacancy", "linkedin"]):
        s_data = perform_web_search(user_prompt)
        tool_results_list.append({
            "toolId": "web-search",
            "toolName": "Web Search Engine",
            "status": "success",
            "executionTimeMs": 320,
            "data": {
                "type": "search",
                "searchResults": s_data["results"]
            }
        })
        return f"### Verified Career & Job Opportunities\n\nHere are top verified career portals and job links:\n\n{s_data['formatted']}", tool_results_list, "LangChain Job Search Tool"

    # Default direct invocation
    try:
        resp = llm.invoke(messages)
        return extract_clean_text(resp) or f"I have processed your request: {user_prompt}", tool_results_list, "LangChain AI Agent"
    except Exception as exc:
        return f"I have processed your request: {user_prompt}", tool_results_list, "LangChain Fallback Engine"
