"""
Unified Orchestrator Agent — single LangGraph ReAct loop that combines
hosted MCP tools and the SQL ReAct subagent for SQL-intent queries.

Architecture:
  • Tool list = every cached MCP tool (flat, direct) + one `query_sql_database`
    wrapper that internally runs the full SQL ReAct subagent
    (_run_sql_react_agent from langchain_agent.py).
  • If no MCP tools are cached/configured, only `query_sql_database` is in
    the tool list — behaviour is identical to the old SQL-only path.
  • The orchestrator's skill file (app/skills/orchestrator_skill.md) instructs
    the agent to try MCP tools first and only fall back to `query_sql_database`
    when MCP alone can't answer.
  • No separate LLM-based router (mcp_router.py has been removed). The only
    non-LLM short-circuit is a free static check: if MCP has no cached tools,
    skip the live-catalog text and run with just the SQL tool.

Public entry point: stream_chat_with_database_with_mcp(question, chat_history, role)
  — yields the exact same SSE event shapes as stream_chat_with_database() in
  langchain_agent.py, so app/routes/chat.py needs zero changes.
"""

import asyncio
import json
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from app.config import settings
from app.services.mcp_manager import (
    get_cached_mcp_tools,
    get_mcp_tool_catalog_text,
    is_mcp_configured,
)
from app.services.mcp_skill_prompt import build_orchestrator_system_prompt
from app.services.question_resolver import get_role_scope_text
from app.services.langchain_agent import (
    _run_sql_react_agent,
    _parse_json_final_answer,
    _parse_all_tables_from_markdown,
    _sanitize_user_response,
    _build_history_prefix,
    _build_markdown_table,
)

print("[MCPAgent] Module loaded")


# ---------------------------------------------------------------------------
# query_sql_database — SQL subagent wrapped as a single LangChain tool
# ---------------------------------------------------------------------------

# These are set once per agent invocation (before the tool is called) via
# the closure captured when _make_sql_tool() builds the tool at request time.
# Using a factory avoids module-level global state for per-request context.

def _make_sql_tool(question_context: str, chat_history: list[dict], role: str):
    """Return a @tool-decorated function that calls the SQL ReAct subagent.

    All three context values are captured in the closure so the outer
    orchestrator agent only needs to pass a sub-question string as the
    tool argument — no hidden globals needed.
    """

    @tool
    async def query_sql_database(sub_question: str) -> str:
        """Query the live SQL database by providing a plain-language question.

        Use this tool when the hosted MCP tools cannot fully answer the
        question.  The tool runs a bounded SQL ReAct subagent, constructs
        and executes the appropriate SQL, and returns a JSON string with keys:
          response (str), has_table (bool), tables (list), sql_query (str),
          full_response (str).

        The `tables` value is a list of {columns, data} dicts — copy it
        verbatim into your final JSON answer; do NOT retype the data.

        Call this tool at most once per turn. Formulate a comprehensive
        sub_question that covers everything you still need from the database.
        """
        print(f"[MCPAgent] query_sql_database tool called | sub_question='{sub_question[:120]}'")
        try:
            # Pass empty history — the QuestionResolver is the sole context-resolution
            # layer. By the time sub_question arrives here it is fully self-contained,
            # so feeding chat_history into the SQL subagent only introduces variation
            # (different history on each run → different SQL for the same question).
            result = await _run_sql_react_agent(sub_question, [], role=role)
            return json.dumps(result)
        except Exception as e:
            print(f"[MCPAgent] query_sql_database tool error: {type(e).__name__}: {e}")
            return json.dumps({
                "response": f"Database query failed: {e}",
                "has_table": False,
                "tables": [],
                "sql_query": "",
                "full_response": f"Database query failed: {e}",
            })

    return query_sql_database


# ---------------------------------------------------------------------------
# Orchestrator agent builder
# ---------------------------------------------------------------------------

def _build_unified_agent(tools: list, role: str):
    """Build the unified orchestrator ReAct agent for one request."""
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatOpenAI(model="gpt-4.1", temperature=0, seed=42, frequency_penalty=0, presence_penalty=0, openai_api_key=settings.OPENAI_API_KEY)

    # Dynamic catalog text — empty string if no MCP tools; the skill file
    # already describes how to use query_sql_database without any catalog.
    mcp_tool_objects = [t for t in tools if t.name != "query_sql_database"]
    catalog = get_mcp_tool_catalog_text() if mcp_tool_objects else ""

    role_scope = get_role_scope_text(role)
    system_prompt = build_orchestrator_system_prompt(catalog, role_scope)

    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)


# ---------------------------------------------------------------------------
# Main public streaming entry point
# ---------------------------------------------------------------------------

async def stream_chat_with_database_with_mcp(
    question: str,
    chat_history: list[dict],
    role: str = "executive",
) -> AsyncGenerator[str, None]:
    """
    Unified orchestrator for SQL-intent queries.

    Builds one ReAct agent with MCP tools (if available) + the SQL subagent
    tool, runs it to completion, then streams the result as SSE events.

    Yields the exact same event types as stream_chat_with_database() so
    app/routes/chat.py needs no changes.
    """
    print(
        f"[MCPAgent] stream_chat_with_database_with_mcp called | "
        f"question='{question[:80]}' | role={role}"
    )

    yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"

    try:
        # Build tool list: cached MCP tools (flat) + SQL subagent wrapper
        mcp_tools: list = []
        if settings.MCP_ENABLED and is_mcp_configured():
            try:
                mcp_tools = list(await get_cached_mcp_tools())
            except Exception as e:
                print(f"[MCPAgent] Could not fetch MCP tools: {e}. Continuing with SQL only.")
                mcp_tools = []

        sql_tool = _make_sql_tool(question, chat_history, role)
        all_tools = mcp_tools + [sql_tool]

        agent = _build_unified_agent(all_tools, role)
        recursion_limit = max(4, settings.ORCHESTRATOR_MAX_TOOL_CALLS * 2 + 2)

        history_prefix = _build_history_prefix(chat_history, include_sql=False)
        full_question = (history_prefix + question) if history_prefix else question

        tool_names = [getattr(t, "name", str(t)) for t in all_tools]
        print(
            f"[MCPAgent] ── Orchestrator START ──────────────────────────────────────\n"
            f"[MCPAgent]   role         : {role}\n"
            f"[MCPAgent]   mcp_tools    : {len(mcp_tools)}  {[getattr(t,'name',str(t)) for t in mcp_tools]}\n"
            f"[MCPAgent]   all_tools    : {tool_names}\n"
            f"[MCPAgent]   recursion_lim: {recursion_limit}\n"
            f"[MCPAgent]   question     : {question[:120]!r}"
        )

        t0 = time.time()

        async def _stream_loop() -> list:
            """Run the astream loop, log every step, return accumulated messages."""
            accumulated: list = []
            step = 0
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=full_question)]},
                config={"recursion_limit": recursion_limit},
                stream_mode="updates",
            ):
                step += 1
                elapsed_so_far = time.time() - t0

                # chunk is a dict: {"agent": {"messages": [...]}} or {"tools": {"messages": [...]}}
                for node_name, node_output in chunk.items():
                    node_messages = node_output.get("messages", []) if isinstance(node_output, dict) else []
                    accumulated.extend(node_messages)

                    if node_name == "agent":
                        for msg in node_messages:
                            tool_calls = getattr(msg, "tool_calls", None) or []
                            content = getattr(msg, "content", "") or ""
                            if tool_calls:
                                # Agent decided to call tool(s)
                                for tc in tool_calls:
                                    tc_name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                    args_preview = json.dumps(tc_args)[:200]
                                    print(
                                        f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] TOOL_CALL "
                                        f"→ {tc_name}({args_preview})"
                                    )
                            else:
                                # Agent produced a final answer (no more tool calls)
                                preview = content[:150].replace("\n", " ")
                                print(
                                    f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] FINAL_ANSWER "
                                    f"(len={len(content)}) preview={preview!r}"
                                )

                    elif node_name == "tools":
                        for msg in node_messages:
                            t_name = getattr(msg, "name", "?")
                            t_content = getattr(msg, "content", "") or ""
                            # For query_sql_database, show the SQL + row count; for others show raw preview
                            if t_name == "query_sql_database":
                                try:
                                    tr = json.loads(t_content)
                                    sql_prev = (tr.get("sql_query") or "")[:200]
                                    n_tables = len(tr.get("tables") or [])
                                    rows_in_first = len((tr.get("tables") or [{}])[0].get("data", [])) if n_tables else 0
                                    print(
                                        f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] TOOL_RESULT "
                                        f"← {t_name} | has_table={tr.get('has_table')} "
                                        f"tables={n_tables} rows_in_first={rows_in_first} "
                                        f"sql={sql_prev!r}"
                                    )
                                except Exception:
                                    print(
                                        f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] TOOL_RESULT "
                                        f"← {t_name} | raw={t_content[:200]!r}"
                                    )
                            else:
                                print(
                                    f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] TOOL_RESULT "
                                    f"← {t_name} | {t_content[:200]!r}"
                                )
                    else:
                        # Unknown node — log it raw
                        print(
                            f"[MCPAgent] Step {step:02d} [{elapsed_so_far:.1f}s] NODE={node_name} "
                            f"messages={len(node_messages)}"
                        )

            return accumulated

        try:
            messages = await asyncio.wait_for(
                _stream_loop(),
                timeout=settings.ORCHESTRATOR_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"The request timed out after {settings.ORCHESTRATOR_TIMEOUT_SECONDS:.0f}s. "
                "Please try a simpler or more specific question."
            )

        elapsed = time.time() - t0
        tool_call_count = sum(1 for m in messages if getattr(m, "type", "") == "tool")

        # ── Short-circuit: if query_sql_database was the ONLY tool called,
        #    use its result directly — skip the orchestrator's final LLM re-wrap.
        #    This saves ~10-15s and the cost of one extra LLM call for pure SQL
        #    queries, since the subagent already returns the exact same JSON schema.
        tool_names_used: set[str] = {
            getattr(m, "name", "")
            for m in messages
            if getattr(m, "type", "") == "tool"
        }
        sql_direct_result: dict | None = None
        if tool_names_used == {"query_sql_database"}:
            for m in messages:
                if getattr(m, "type", "") == "tool" and getattr(m, "name", "") == "query_sql_database":
                    try:
                        sql_direct_result = json.loads(m.content)
                        print(
                            f"[MCPAgent] SHORT-CIRCUIT: query_sql_database was the only tool — "
                            f"using subagent result directly (orchestrator final LLM call skipped)"
                        )
                    except Exception:
                        pass
                    break

        if sql_direct_result is not None:
            # ── Fast path: pull everything from the subagent's result dict ──
            answer = sql_direct_result
            output_len = len(sql_direct_result.get("full_response") or sql_direct_result.get("response") or "")
        else:
            # ── Normal path: read the orchestrator's final AI message ──
            final_text = ""
            for m in reversed(messages):
                content = getattr(m, "content", None)
                if isinstance(content, str) and content.strip():
                    final_text = content.strip()
                    break

            if not final_text:
                final_text = json.dumps({
                    "response": "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query.",
                    "has_table": False,
                    "tables": [],
                })
            answer = _parse_json_final_answer(final_text)
            output_len = len(final_text)

        print(
            f"[MCPAgent] ── Orchestrator END ────────────────────────────────────────\n"
            f"[MCPAgent]   elapsed      : {elapsed:.2f}s\n"
            f"[MCPAgent]   total_msgs   : {len(messages)}\n"
            f"[MCPAgent]   tool_results : {tool_call_count}\n"
            f"[MCPAgent]   short_circuit: {sql_direct_result is not None}\n"
            f"[MCPAgent]   output_len   : {output_len}"
        )

        response_text = str(answer.get("response") or "").strip()
        has_table = bool(answer.get("has_table"))
        raw_tables = answer.get("tables") or []

        all_tables: list[dict] = []
        if isinstance(raw_tables, list):
            for t in raw_tables:
                if not isinstance(t, dict):
                    continue
                cols = t.get("columns") or []
                data = t.get("data") or []
                if isinstance(cols, list) and isinstance(data, list) and cols and data:
                    all_tables.append({"columns": cols, "data": data})

        if not response_text and not all_tables:
            response_text = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

        response_text = _sanitize_user_response(response_text)
        has_table = has_table and bool(all_tables)

        # Build full_response (narrative + rendered markdown tables).
        # For the short-circuit path the subagent already built full_response;
        # reuse it only when the tables match what we validated above.
        if sql_direct_result is not None and sql_direct_result.get("full_response") and all_tables:
            full_response = sql_direct_result["full_response"].strip()
        else:
            response_parts = [response_text] if response_text else []
            for t in all_tables:
                md = _build_markdown_table(t["columns"], t["data"])
                if md:
                    response_parts.append(md)
            full_response = "\n\n".join(p for p in response_parts if p).strip()

        if not full_response:
            full_response = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

        # Pull SQL query — available in the subagent result or from tool result messages
        sql_query = (sql_direct_result or {}).get("sql_query") or ""
        if not sql_query:
            for m in messages:
                if getattr(m, "type", "") == "tool" and getattr(m, "name", "") == "query_sql_database":
                    try:
                        tool_result = json.loads(m.content)
                        if tool_result.get("sql_query"):
                            sql_query = tool_result["sql_query"]
                            break
                    except Exception:
                        pass

        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        print(
            f"[MCPAgent] Building SSE events | full_response_len={len(full_response)} | "
            f"has_table={has_table} | tables={len(all_tables)}"
        )

        # Pre-save signal — intercepted by chat.py for MongoDB persistence.
        yield (
            "data: "
            + json.dumps({
                "type": "pre_done",
                "full_response": full_response,
                "has_table": has_table,
                "table_data": table_data,
                "table_columns": table_columns,
                "tables": all_tables,
                "sql_query": sql_query,
            })
            + "\n\n"
        )

        # Token streaming
        chunk_size = 12
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i : i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            if (i // chunk_size) % 5 == 4:
                await asyncio.sleep(0.01)

        done_event = json.dumps({
            "type": "done",
            "has_table": has_table,
            "table_data": table_data,
            "table_columns": table_columns,
            "tables": all_tables,
            "full_response": full_response,
            "sql_query": sql_query,
        })
        yield f"data: {done_event}\n\n"
        print("[MCPAgent] Stream complete")

    except Exception as e:
        print(f"[MCPAgent] EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
