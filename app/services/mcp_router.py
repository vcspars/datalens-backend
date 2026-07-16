"""
MCP Tool Router — cheap decision step that runs before any MCP tool is
actually called.

Its only job: decide whether the cached MCP tool catalog can plausibly answer
the (already-resolved) question. This keeps the common case — where MCP tools
don't apply — fast and cheap: one short LLM call instead of spinning up a full
bounded ReAct loop that would only end up giving up.

Always defaults to "don't use MCP" on any ambiguity or error, since the
LangChain SQL agent fallback is always available and safe.
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.services.mcp_manager import get_cached_mcp_tools, get_mcp_tool_catalog_text, is_mcp_configured

print("[MCPRouter] Module loaded")

_ROUTER_LLM: ChatOpenAI | None = None


def _get_router_llm() -> ChatOpenAI:
    global _ROUTER_LLM
    if _ROUTER_LLM is None:
        _ROUTER_LLM = ChatOpenAI(
            model="gpt-4.1",
            temperature=0,
            max_tokens=150,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    return _ROUTER_LLM


SYSTEM_PROMPT = """You decide whether a set of available tools can answer a user's question — \
without calling any tool yourself.

You will be given a list of available tools (name, description, arguments) and a user question.

Reply with ONLY valid JSON, no markdown fences, no other text:
{"use_tools": true or false, "reasoning": "<one short sentence>"}

Rules:
- Set use_tools=true ONLY if one tool, or a small combination of 2-3 tools, could plausibly \
answer the question based on their stated purpose.
- Set use_tools=false if no tool's description is clearly relevant, or if answering requires \
general/ad-hoc SQL querying that these tools do not cover.
- Be conservative: when in doubt, use_tools=false — a fallback SQL agent will handle it, so a \
false negative is cheap but a false positive wastes time.
- Never invent tool capabilities beyond what their description states."""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    return raw.strip()


async def decide_mcp_tools(question: str, role: str = "executive") -> dict[str, Any]:
    """Fast check: can the cached MCP tools plausibly answer this question?

    Returns {"use_tools": bool, "reasoning": str}. Defaults to
    {"use_tools": False, ...} (safe — falls back to the LangChain SQL agent)
    whenever MCP isn't configured, has no cached tools, or the router errors.
    """
    if not is_mcp_configured():
        return {"use_tools": False, "reasoning": "MCP not configured"}

    tools = await get_cached_mcp_tools()
    if not tools:
        return {"use_tools": False, "reasoning": "No MCP tools cached"}

    catalog = get_mcp_tool_catalog_text()
    user_prompt = (
        f"Available tools:\n{catalog}\n\n"
        f"User question: {question}\n\n"
        "JSON decision:"
    )

    try:
        llm = _get_router_llm()
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        result = await llm.ainvoke(messages)
        raw = _strip_fences(result.content or "")
        data = json.loads(raw)
        use_tools = bool(data.get("use_tools", False))
        reasoning = str(data.get("reasoning", ""))
        print(f"[MCPRouter] decision=use_tools:{use_tools} | reasoning={reasoning!r} | question='{question[:80]}'")
        return {"use_tools": use_tools, "reasoning": reasoning}
    except Exception as e:
        print(f"[MCPRouter] ERROR: {type(e).__name__}: {e} — defaulting to use_tools=False (safe fallback)")
        return {"use_tools": False, "reasoning": f"router error: {e}"}
