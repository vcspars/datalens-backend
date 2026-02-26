"""
LangChain SQL Agent service for chatting with SQL Server via natural language.

Streaming is done via an async generator that yields SSE-formatted strings.
Each yielded chunk is one of:
  data: {"type": "token",  "content": "<partial text>"}\n\n
  data: {"type": "done",   "has_table": true|false, "table_data": [...], "table_columns": [...], "full_response": "..."}\n\n
  data: {"type": "error",  "content": "<error message>"}\n\n
"""

import json
import re
import asyncio
from typing import AsyncGenerator, Optional

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import HumanMessage, AIMessage

from app.config import settings

print("[LangChainAgent] Module loaded")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_connection_string() -> str:
    """
    Build a SQLAlchemy connection string for MSSQL via pyodbc using the
    `odbc_connect` approach.

    Using `odbc_connect` (raw ODBC string passed as a URL parameter) is the
    most reliable method for named SQL Server instances because it avoids all
    URL-encoding issues with backslashes, spaces, and special characters in the
    server name, driver name, and password.

    e.g.  VCSSQL02\\sparsweb  →  no backslash confusion in URL parsing.
    """
    from urllib.parse import quote_plus

    odbc_str = (
        f"DRIVER={{{settings.SQL_DRIVER}}};"
        f"SERVER={settings.SQL_SERVER};"
        f"DATABASE={settings.SQL_DATABASE};"
        f"UID={settings.SQL_USER};"
        f"PWD={settings.SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    conn = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"
    print(
        f"[LangChainAgent] Connection string built | "
        f"server={settings.SQL_SERVER} | db={settings.SQL_DATABASE} | "
        f"driver={settings.SQL_DRIVER}"
    )
    return conn


def _get_sql_db() -> SQLDatabase:
    """Create and return a LangChain SQLDatabase instance."""
    print("[LangChainAgent] Creating SQLDatabase connection...")
    conn_str = _build_connection_string()
    try:
        db = SQLDatabase.from_uri(conn_str)
        print("[LangChainAgent] SQLDatabase connected successfully")
        return db
    except Exception as e:
        msg = str(e)
        print(f"[LangChainAgent] SQLDatabase connection FAILED: {msg}")
        # Surface a clean, actionable message to the user
        if "08001" in msg or "Error Locating Server" in msg or "Login timeout" in msg:
            raise ConnectionError(
                f"Cannot reach SQL Server '{settings.SQL_SERVER}'. "
                "Please check: (1) the server name in .env is correct, "
                "(2) SQL Server Browser service is running on the host, "
                "(3) UDP 1434 / TCP port is not blocked by a firewall, "
                "(4) remote connections are enabled in SQL Server."
            ) from e
        if "28000" in msg or "Login failed" in msg:
            raise ConnectionError(
                f"SQL Server login failed for user '{settings.SQL_USER}'. "
                "Check SQL_USER and SQL_PASSWORD in .env."
            ) from e
        raise


def _parse_single_table(table_lines: list[str]) -> Optional[dict]:
    """
    Parse a contiguous block of markdown table lines into {columns, data}.
    Returns None if the block is malformed.
    """
    if len(table_lines) < 2:
        return None

    header_row = table_lines[0]
    columns = [c.strip() for c in header_row.strip("|").split("|") if c.strip()]
    if not columns:
        return None

    # table_lines[1] is the separator (--- | --- | ...)
    data_rows = []
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        while len(cells) < len(columns):
            cells.append("")
        cells = cells[: len(columns)]
        data_rows.append(dict(zip(columns, cells)))

    if not data_rows:
        return None

    return {"columns": columns, "data": data_rows}


def _parse_all_tables_from_markdown(text: str) -> list[dict]:
    """
    Extract every markdown table present in the response text.
    Returns a list of {columns: [...], data: [...]} dicts (one per table found).
    """
    lines = text.strip().splitlines()
    tables: list[dict] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_block.append(stripped)
        else:
            if current_block:
                parsed = _parse_single_table(current_block)
                if parsed:
                    tables.append(parsed)
                current_block = []

    # Flush any trailing block
    if current_block:
        parsed = _parse_single_table(current_block)
        if parsed:
            tables.append(parsed)

    if tables:
        print(f"[LangChainAgent] {len(tables)} table(s) detected in response")
        for i, t in enumerate(tables):
            print(f"  Table {i+1}: {len(t['columns'])} cols, {len(t['data'])} rows")

    return tables


def _parse_table_from_markdown(text: str) -> tuple[bool, list, list]:
    """
    Backward-compat wrapper — returns data for the first table only.
    Kept so the chat streaming path continues to work unchanged.
    """
    tables = _parse_all_tables_from_markdown(text)
    if not tables:
        return False, [], []
    first = tables[0]
    return True, first["data"], first["columns"]


def _build_context_messages(history: list[dict]) -> list:
    """
    Convert last N Q/A pairs from MongoDB into LangChain message objects.
    history items: {"role": "user"|"assistant", "content": "..."}
    """
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    return messages


# ---------------------------------------------------------------------------
# Streaming callback handler
# ---------------------------------------------------------------------------

class StreamingCallbackHandler(BaseCallbackHandler):
    """Collects streamed tokens into a queue for async consumption."""

    def __init__(self, token_queue: asyncio.Queue):
        super().__init__()
        self._queue = token_queue
        self._loop = None

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called by LangChain for each new streamed token."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._queue.put_nowait, token)
        else:
            self._queue.put_nowait(token)

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] LLM error: {error}")

    def on_agent_action(self, action, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Agent action: {action.tool} | input: {str(action.tool_input)[:200]}")

    def on_agent_finish(self, finish, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Agent finished")

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Tool start: {serialized.get('name')} | input: {str(input_str)[:200]}")

    def on_tool_end(self, output, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Tool end: {str(output)[:200]}")

    def on_tool_error(self, error, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Tool error: {error}")


# ---------------------------------------------------------------------------
# Main streaming generator
# ---------------------------------------------------------------------------

async def stream_chat_with_database(
    question: str,
    chat_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams SSE events for a user question.

    Args:
        question: The natural language question from the user.
        chat_history: List of {"role": ..., "content": ...} dicts (last 5 pairs).

    Yields:
        SSE-formatted strings.
    """
    print(f"[LangChainAgent] stream_chat_with_database called | question='{question[:100]}' | history_len={len(chat_history)}")

    token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    full_response_parts: list[str] = []

    try:
        # Build SQL DB connection
        sql_db = _get_sql_db()

        # LLM with streaming
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        # Build context prefix from history
        context_prefix = ""
        if chat_history:
            context_prefix = "Previous conversation context:\n"
            for msg in chat_history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                context_prefix += f"{role_label}: {msg['content']}\n"
            context_prefix += "\nCurrent question: "
            print(f"[LangChainAgent] Injecting {len(chat_history)} history messages as context")

        full_question = context_prefix + question

        # Callback handler to collect tokens
        handler = StreamingCallbackHandler(token_queue)

        # Create SQL agent
        print("[LangChainAgent] Creating SQL agent...")
        agent_executor = create_sql_agent(
            llm=llm,
            db=sql_db,
            agent_type="openai-tools",
            verbose=True,
            handle_parsing_errors=True,
            callbacks=[handler],
        )
        print("[LangChainAgent] SQL agent created, invoking...")

        # Run agent in a thread pool so we don't block the event loop
        sentinel = object()

        async def run_agent():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: agent_executor.invoke({"input": full_question}),
                )
                output = result.get("output", "") if isinstance(result, dict) else str(result)
                print(f"[LangChainAgent] Agent invocation complete | output_len={len(output)}")
                return output
            except Exception as e:
                print(f"[LangChainAgent] Agent error during invocation: {e}")
                raise
            finally:
                # Signal the token consumer that we're done
                await token_queue.put(None)

        # Start agent in background task
        agent_task = asyncio.create_task(run_agent())

        # Stream tokens as they arrive
        print("[LangChainAgent] Starting token stream...")
        while True:
            try:
                token = await asyncio.wait_for(token_queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                print("[LangChainAgent] Token queue timeout, stopping stream")
                break

            if token is None:  # sentinel — agent finished
                break

            full_response_parts.append(token)
            sse_event = json.dumps({"type": "token", "content": token})
            yield f"data: {sse_event}\n\n"

        # Wait for agent to fully finish
        try:
            agent_output = await asyncio.wait_for(agent_task, timeout=10.0)
        except asyncio.TimeoutError:
            print("[LangChainAgent] Agent task timeout after stream")
            agent_output = "".join(full_response_parts)

        # If streaming produced nothing but agent returned output, use that
        full_response = "".join(full_response_parts) if full_response_parts else agent_output
        if not full_response and isinstance(agent_output, str):
            full_response = agent_output

        print(f"[LangChainAgent] Full response length: {len(full_response)} chars")

        # Parse ALL tables from the response
        all_tables = _parse_all_tables_from_markdown(full_response)
        has_table = len(all_tables) > 0
        # Keep first-table fields for backward compat
        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        # Emit done event
        done_event = json.dumps({
            "type": "done",
            "has_table": has_table,
            "table_data": table_data,
            "table_columns": table_columns,
            # All tables for the frontend multi-table picker
            "tables": all_tables,
            "full_response": full_response,
        })
        yield f"data: {done_event}\n\n"
        print("[LangChainAgent] Stream complete")

    except Exception as e:
        print(f"[LangChainAgent] EXCEPTION in stream_chat_with_database: {e}")
        import traceback
        traceback.print_exc()
        error_event = json.dumps({"type": "error", "content": str(e)})
        yield f"data: {error_event}\n\n"


# ---------------------------------------------------------------------------
# Report generation streaming
# ---------------------------------------------------------------------------

async def stream_generate_report(
    prompt: str,
    items_context: str,
    template: str,
    custom_system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a markdown report based on selected dashboard items and user prompt.

    Args:
        prompt: The main instruction / question.
        items_context: Serialised context from dashboard items (may be empty).
        template: Report template label (e.g. "summary", "technical").
        custom_system_prompt: If provided, replaces the default report-style system
            prompt.  Use this to avoid the LLM prepending "Data Summary Report /
            Executive Summary" headers when you just want plain content.

    Yields SSE strings:
      data: {"type": "token",  "content": "..."}\n\n
      data: {"type": "done",   "full_report": "..."}\n\n
      data: {"type": "error",  "content": "..."}\n\n
    """
    print(f"[LangChainAgent] stream_generate_report | template={template} | prompt='{prompt[:100]}'")

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        if custom_system_prompt:
            system_prompt = custom_system_prompt
        else:
            system_prompt = (
                f"You are a professional data analyst generating a {template} report. "
                "Use the provided data context and generate a well-structured, detailed markdown report. "
                "Include sections like Executive Summary, Key Findings, Analysis, and Recommendations. "
                "Format all content as clean markdown. Do NOT wrap the output in code fences."
            )

        context_block = f"Data Context:\n{items_context}\n\n" if items_context.strip() else ""
        full_prompt = (
            f"{system_prompt}\n\n"
            f"{context_block}"
            f"Instructions:\n{prompt}"
        )

        full_report_parts: list[str] = []
        token_queue: asyncio.Queue = asyncio.Queue()
        handler = StreamingCallbackHandler(token_queue)

        async def run_llm():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: llm.invoke(full_prompt, config={"callbacks": [handler]}),
                )
                print(f"[LangChainAgent] Report LLM complete")
                return result.content if hasattr(result, "content") else str(result)
            except Exception as e:
                print(f"[LangChainAgent] Report LLM error: {e}")
                raise
            finally:
                await token_queue.put(None)

        llm_task = asyncio.create_task(run_llm())

        while True:
            try:
                token = await asyncio.wait_for(token_queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                print("[LangChainAgent] Report token queue timeout")
                break

            if token is None:
                break

            full_report_parts.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        try:
            llm_output = await asyncio.wait_for(llm_task, timeout=10.0)
        except asyncio.TimeoutError:
            llm_output = "".join(full_report_parts)

        full_report = "".join(full_report_parts) if full_report_parts else llm_output

        yield f"data: {json.dumps({'type': 'done', 'full_report': full_report})}\n\n"
        print(f"[LangChainAgent] Report stream complete | length={len(full_report)}")

    except Exception as e:
        print(f"[LangChainAgent] EXCEPTION in stream_generate_report: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
