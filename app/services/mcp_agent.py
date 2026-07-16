"""
MCP ReAct Agent — bounded multi-tool execution over cached MCP tools, with a
transparent fallback to the existing LangChain SQL agent whenever MCP tools
can't resolve the question (not configured, no matching tool, timeout, or the
loop gives up).

Public entry point: stream_chat_with_database_with_mcp(...) — yields the exact
same SSE event shapes as stream_chat_with_database() in langchain_agent.py, so
app/routes/chat.py needs no changes beyond importing this function instead for
the "sql" intent path.

Flow per question:
  1. Cheap router (mcp_router.decide_mcp_tools) — decide if MCP tools are even
     worth attempting. Skipped entirely if MCP isn't configured.
  2. If yes: run a bounded LangGraph ReAct loop (langgraph.prebuilt.create_react_agent)
     over the cached MCP tools, capped by MCP_MAX_TOOL_CALLS and
     MCP_AGENT_TIMEOUT_SECONDS. The loop is fully resolved (not token-streamed)
     before anything is emitted — so on failure we can fall back cleanly
     without ever having sent partial/wrong output to the client.
  3. If no / on any failure / on timeout / on "CANNOT_RESOLVE_WITH_TOOLS":
     transparently delegate to stream_chat_with_database() (existing LangChain
     SQL agent), unchanged.
"""

import asyncio
import json
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from app.config import settings
from app.services.mcp_manager import get_cached_mcp_tools, get_mcp_tool_catalog_text, is_mcp_configured
from app.services.mcp_router import decide_mcp_tools
from app.services.mcp_skill_prompt import build_orchestrator_system_prompt
from app.services.question_resolver import get_role_scope_text
from app.services.langchain_agent import (
    stream_chat_with_database,
    _parse_all_tables_from_markdown,
    _sanitize_user_response,
    _build_history_prefix,
)

print("[MCPAgent] Module loaded")

_CANNOT_RESOLVE_MARKER = "CANNOT_RESOLVE_WITH_TOOLS"


class MCPUnresolvedError(Exception):
    """Raised when the MCP ReAct loop cannot confidently answer the question —
    the caller should fall back to the LangChain SQL agent."""


def _build_react_agent(tools: list, role: str):
    """Build a fresh bounded ReAct agent bound to the cached MCP tools."""
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatOpenAI(model="gpt-4.1", temperature=0, openai_api_key=settings.OPENAI_API_KEY)
    catalog = get_mcp_tool_catalog_text()
    role_scope = get_role_scope_text(role)
    system_prompt = build_orchestrator_system_prompt(catalog, role_scope)

    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)


async def _run_mcp_react(question: str, chat_history: list[dict], role: str) -> str:
    """Run the bounded ReAct loop once. Returns the final answer text.

    Raises MCPUnresolvedError if the agent gives up, times out, hits the
    tool-call limit, or explicitly signals it cannot resolve the question.
    """
    tools = await get_cached_mcp_tools()
    if not tools:
        raise MCPUnresolvedError("No MCP tools available")

    agent = _build_react_agent(tools, role)

    history_prefix = _build_history_prefix(chat_history, include_sql=False)
    full_question = f"{history_prefix}{question}" if history_prefix else question

    # Each tool-call round is ~2 graph steps (assistant turn -> tool turn);
    # add a small buffer for the final answer step.
    recursion_limit = max(4, settings.MCP_MAX_TOOL_CALLS * 2 + 2)

    t0 = time.time()
    try:
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [HumanMessage(content=full_question)]},
                config={"recursion_limit": recursion_limit},
            ),
            timeout=settings.MCP_AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as e:
        raise MCPUnresolvedError(
            f"MCP agent timed out after {settings.MCP_AGENT_TIMEOUT_SECONDS}s"
        ) from e
    except Exception as e:
        # Covers GraphRecursionError (tool-call limit hit) and any tool/session failure.
        raise MCPUnresolvedError(f"MCP agent failed: {type(e).__name__}: {e}") from e

    elapsed = time.time() - t0
    messages = result.get("messages", []) if isinstance(result, dict) else []
    tool_call_count = sum(1 for m in messages if getattr(m, "type", "") == "tool")
    final_text = ""
    for m in reversed(messages):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            final_text = content.strip()
            break

    print(
        f"[MCPAgent] ReAct loop complete | {elapsed:.2f}s | "
        f"tool_calls={tool_call_count} | messages={len(messages)} | output_len={len(final_text)}"
    )

    if not final_text or _CANNOT_RESOLVE_MARKER in final_text:
        raise MCPUnresolvedError("MCP agent could not resolve the question with available tools")

    return final_text


async def stream_chat_with_database_with_mcp(
    question: str,
    chat_history: list[dict],
    role: str = "executive",
) -> AsyncGenerator[str, None]:
    """
    Try hosted MCP tool(s) first (bounded ReAct loop) when the cheap router
    thinks they're relevant; otherwise — or on any MCP failure/timeout —
    transparently fall back to the existing LangChain SQL agent.

    Yields the exact same SSE event shapes as stream_chat_with_database(), so
    app/routes/chat.py's parsing logic needs no changes.
    """
    use_mcp = False
    if settings.MCP_ENABLED and is_mcp_configured():
        try:
            decision = await decide_mcp_tools(question, role=role)
            use_mcp = bool(decision.get("use_tools"))
        except Exception as e:
            print(f"[MCPAgent] Router decision failed, defaulting to LangChain SQL agent: {e}")
            use_mcp = False

    if not use_mcp:
        async for chunk in stream_chat_with_database(question, chat_history, role=role):
            yield chunk
        return

    print(f"[MCPAgent] Router selected MCP tools — attempting bounded ReAct loop | question='{question[:80]}'")
    yield f"data: {json.dumps({'type': 'status', 'content': 'Checking available tools...'})}\n\n"

    try:
        full_response = await _run_mcp_react(question, chat_history, role)
    except MCPUnresolvedError as e:
        print(f"[MCPAgent] MCP path did not resolve ({e}) — falling back to LangChain SQL agent")
        async for chunk in stream_chat_with_database(question, chat_history, role=role):
            yield chunk
        return
    except Exception as e:
        print(f"[MCPAgent] Unexpected MCP error ({type(e).__name__}: {e}) — falling back to LangChain SQL agent")
        async for chunk in stream_chat_with_database(question, chat_history, role=role):
            yield chunk
        return

    full_response = _sanitize_user_response(full_response)
    all_tables = _parse_all_tables_from_markdown(full_response)
    has_table = len(all_tables) > 0
    table_data = all_tables[0]["data"] if all_tables else []
    table_columns = all_tables[0]["columns"] if all_tables else []

    # Pre-save signal — mirrors stream_chat_with_database() so chat.py can
    # persist the full payload before token chunks even if the client drops.
    yield (
        "data: "
        + json.dumps(
            {
                "type": "pre_done",
                "full_response": full_response,
                "has_table": has_table,
                "table_data": table_data,
                "table_columns": table_columns,
                "tables": all_tables,
                "sql_query": "",
            }
        )
        + "\n\n"
    )

    chunk_size = 12
    for i in range(0, len(full_response), chunk_size):
        chunk = full_response[i : i + chunk_size]
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        if (i // chunk_size) % 5 == 4:
            await asyncio.sleep(0.01)

    done_event = json.dumps(
        {
            "type": "done",
            "has_table": has_table,
            "table_data": table_data,
            "table_columns": table_columns,
            "tables": all_tables,
            "full_response": full_response,
            "sql_query": "",
        }
    )
    yield f"data: {done_event}\n\n"
    print("[MCPAgent] MCP stream complete")
