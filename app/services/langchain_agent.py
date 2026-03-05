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
from app.services.db_knowledge import get_system_prompt
from app.services.sql_utils import is_read_only_sql

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


_cached_sql_db: Optional[SQLDatabase] = None


def _get_sql_db() -> SQLDatabase:
    """Return a cached LangChain SQLDatabase instance. Reflects tables once; reused thereafter."""
    global _cached_sql_db
    if _cached_sql_db is not None:
        print("[LangChainAgent] Reusing cached SQLDatabase connection")
        return _cached_sql_db

    import time
    t0 = time.time()
    print("[LangChainAgent] Creating SQLDatabase connection (read-only, first time — will be cached)...")
    conn_str = _build_connection_string()
    try:
        db = SQLDatabase.from_uri(conn_str, sample_rows_in_table_info=0)
        _original_run = db.run

        def _run_read_only_only(command: str, *args, **kwargs):
            if not is_read_only_sql(command):
                raise ValueError(
                    "Only read-only SQL (SELECT) is allowed. "
                    "This application never updates, edits, or deletes anything in the database."
                )
            return _original_run(command, *args, **kwargs)

        db.run = _run_read_only_only
        _cached_sql_db = db
        elapsed = time.time() - t0
        print(f"[LangChainAgent] SQLDatabase connected & cached (read-only) | {elapsed:.1f}s")
        return db
    except Exception as e:
        msg = str(e)
        print(f"[LangChainAgent] SQLDatabase connection FAILED: {msg}")
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


def get_table_row_counts() -> str:
    """
    Run read-only SELECT COUNT(*) for each table and return a text block for use as context.
    Used so the summary LLM reports actual row counts instead of guessing (e.g. 3).
    """
    try:
        db = _get_sql_db()
        tables = db.get_usable_table_names()
        if not tables:
            return ""
        lines = ["Table row counts (from SELECT COUNT(*) per table):"]
        for name in sorted(tables):
            try:
                # Read-only: only SELECT
                sql = f"SELECT COUNT(*) AS cnt FROM [{name}]"
                out = db.run(sql)
                # LangChain run() often returns "cnt\n123" or "(123,)" or just "123"
                count = "?"
                if out is not None:
                    s = str(out).strip()
                    if s.isdigit():
                        count = s
                    else:
                        # Take last line or last number (header line is often first)
                        for line in s.splitlines():
                            line = line.strip()
                            if line.isdigit():
                                count = line
                                break
                        if count == "?":
                            for part in re.sub(r"[\s,()]+", " ", s).split():
                                if part.isdigit():
                                    count = part
                                    break
                lines.append(f"  {name}: {count}")
            except Exception as e:
                lines.append(f"  {name}: (error: {e})")
        return "\n".join(lines)
    except Exception as e:
        print(f"[LangChainAgent] get_table_row_counts failed: {e}")
        return ""


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

def _parse_sql_tool_result_to_table(output: str) -> Optional[tuple[list[str], list[dict]]]:
    """Parse sql_db_query tool output (e.g. '[(a, b), (c, d)]' or with Decimal) into table_columns and table_data."""
    if not output or not isinstance(output, str):
        return None
    s = output.strip()
    if not s.startswith("[") or "(" not in s:
        return None
    # LangChain often returns repr of list of tuples with Decimal(...) — literal_eval can't parse Decimal
    s = re.sub(r"Decimal\s*\(\s*['\"]?([^'\"]+)['\"]?\s*\)", r"\1", s)
    try:
        import ast
        rows = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None
    if not rows or not isinstance(rows, list):
        return None
    first = rows[0]
    if isinstance(first, (list, tuple)):
        ncols = len(first)
    else:
        return None
    columns = [f"Column {i + 1}" for i in range(ncols)]
    data = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != ncols:
            continue
        data.append(dict(zip(columns, [str(c) for c in row])))
    if not data:
        return None
    return (columns, data)


def _build_markdown_table(columns: list[str], data: list[dict]) -> str:
    """Build a markdown table string from column names and list of row dicts."""
    if not columns or not data:
        return ""
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "|" + "|".join(":---" for _ in columns) + "|"
    rows = []
    for row in data:
        cells = [str(row.get(c, "")).replace("|", "\\|") for c in columns]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep] + rows)


class StreamingCallbackHandler(BaseCallbackHandler):
    """Collects streamed tokens into a queue for async consumption; captures SQL from sql_db_query tool."""

    def __init__(self, token_queue: asyncio.Queue):
        super().__init__()
        self._queue = token_queue
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._last_sql: Optional[str] = None
        self._query_result_columns: Optional[list[str]] = None
        self._query_result_table: Optional[list[dict]] = None
        self._last_tool_was_sql_query = False
        # Suppress raw SQL code blocks in streamed response
        self._stream_buffer = ""
        self._in_sql_block = False
        self._stream_buffer_max = 200

    def _enqueue(self, item):
        """Thread-safe enqueue: always use call_soon_threadsafe since callbacks run in executor thread."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        else:
            try:
                self._queue.put_nowait(item)
            except Exception:
                pass

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Stream only final-answer tokens; suppress tool-call chunks and ```sql...``` blocks."""
        chunk = kwargs.get("chunk")
        if chunk is not None:
            msg = getattr(chunk, "message", None)
            if msg is not None:
                tcc = getattr(msg, "tool_call_chunks", None)
                if tcc:
                    return
                tc = getattr(msg, "tool_calls", None)
                if tc:
                    return
                ak = getattr(msg, "additional_kwargs", {})
                if ak.get("tool_calls"):
                    return
        if not token:
            return
        # Buffer and suppress ```sql ... ``` blocks so raw SQL never appears in the stream
        self._stream_buffer += token
        if self._in_sql_block:
            if "```" in self._stream_buffer and self._stream_buffer.rstrip().endswith("```"):
                self._in_sql_block = False
                self._stream_buffer = ""
            return
        # Detect start of ```sql block (exactly 6 chars or at boundary)
        if len(self._stream_buffer) >= 6 and self._stream_buffer[:6].lower() == "```sql":
            self._stream_buffer = self._stream_buffer[6:]
            self._in_sql_block = True
            return
        if "```sql" in self._stream_buffer.lower():
            idx = self._stream_buffer.lower().index("```sql")
            for c in self._stream_buffer[:idx]:
                self._enqueue(c)
            self._stream_buffer = self._stream_buffer[idx + 6:]
            self._in_sql_block = True
            return
        # Flush only when we have more than 5 chars (keep 5 so we don't split "```sql")
        while len(self._stream_buffer) > 5:
            self._enqueue(self._stream_buffer[0])
            self._stream_buffer = self._stream_buffer[1:]

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] LLM error: {error}")

    def on_llm_end(self, response, **kwargs) -> None:
        """Flush any buffered tokens so we don't lose the last few chars of the response."""
        if not self._in_sql_block and self._stream_buffer:
            for c in self._stream_buffer:
                self._enqueue(c)
            self._stream_buffer = ""

    def on_agent_action(self, action, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Agent action: {action.tool} | input: {str(action.tool_input)[:200]}")
        # Send a status marker so the frontend knows the agent is working (resets timeout)
        self._enqueue("")

    def on_agent_finish(self, finish, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Agent finished")

    def _is_sql_query_tool(self, name: str, serialized: dict, kwargs: dict) -> bool:
        """True if this tool is the SQL *execution* tool (not checker/schema/list)."""
        if not name:
            name = kwargs.get("name") or ""
        name_lower = (name or "").lower()
        # Exclude checker, schema, list tools explicitly
        if "checker" in name_lower or "schema" in name_lower or "list" in name_lower:
            return False
        if name in ("sql_db_query", "QuerySQLDatabaseTool"):
            return True
        if "sql" in name_lower and "query" in name_lower:
            return True
        sid = serialized.get("id") or []
        if isinstance(sid, list) and sid:
            last_part = (sid[-1] or "").lower()
            if "query" in last_part and "sql" in last_part and "checker" not in last_part:
                return True
        return False

    @staticmethod
    def _extract_sql_from_input(input_str) -> Optional[str]:
        """Extract the SQL query string from the tool input (dict, JSON string, or Python repr)."""
        if isinstance(input_str, dict):
            return input_str.get("query") or input_str.get("input")
        if not isinstance(input_str, str):
            return None
        s = input_str.strip()
        # Try JSON first
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return data.get("query") or data.get("input")
        except (json.JSONDecodeError, ValueError):
            pass
        # Try Python dict repr (single quotes) — convert to JSON
        if s.startswith("{") and "query" in s:
            try:
                import ast
                data = ast.literal_eval(s)
                if isinstance(data, dict):
                    return data.get("query") or data.get("input")
            except Exception:
                pass
        # Fallback: if it looks like raw SQL (starts with SELECT/WITH)
        upper = s.lstrip().upper()
        if upper.startswith("SELECT") or upper.startswith("WITH"):
            return s
        return None

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        name = serialized.get("name") or kwargs.get("name") or ""
        if not name and isinstance(serialized.get("id"), list):
            name = serialized["id"][-1] if serialized["id"] else ""
        is_sql = self._is_sql_query_tool(name, serialized, kwargs)
        input_preview = str(input_str)[:300]
        print(f"[LangChainAgent][Callback] Tool start: name={name!r} | is_sql_query={is_sql} | input_len={len(str(input_str))} | input: {input_preview}")
        # Keepalive: reset token-consumer timeout while DB queries are running
        self._enqueue("")
        if is_sql:
            self._last_tool_was_sql_query = True
            query = self._extract_sql_from_input(input_str)
            if isinstance(query, str) and query.strip():
                self._last_sql = query.strip()
                print(f"[LangChainAgent][Callback] Captured SQL (len={len(self._last_sql)}): {self._last_sql[:150]}...")
        else:
            self._last_tool_was_sql_query = False

    def on_tool_end(self, output, **kwargs) -> None:
        out_str = str(output) if output is not None else "<None>"
        out_len = len(out_str)
        print(f"[LangChainAgent][Callback] Tool end (len={out_len}): {out_str[:300]}")
        if out_len == 0 or not out_str.strip():
            print("[LangChainAgent][Callback] WARNING: Tool returned empty/blank result")
        # Keepalive: reset token-consumer timeout while tools are still running
        self._enqueue("")
        if self._last_tool_was_sql_query and output is not None:
            parsed = _parse_sql_tool_result_to_table(str(output))
            if parsed:
                cols, data = parsed
                self._query_result_columns = cols
                self._query_result_table = data
                print(f"[LangChainAgent][Callback] Parsed query result: {len(data)} rows, {len(cols)} cols")
        self._last_tool_was_sql_query = False

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
    import time as _time
    print(f"[LangChainAgent] stream_chat_with_database called | question='{question[:100]}' | history_len={len(chat_history)}")

    try:
        # Build SQL DB connection
        sql_db = _get_sql_db()

        # Callback handler — only used for SQL capture & keepalive, NOT for token streaming
        token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        handler = StreamingCallbackHandler(token_queue)

        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0,
            streaming=False,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        # Build context prefix from history (larger assistant context for SQL path)
        context_prefix = _build_history_prefix(chat_history, max_assistant_chars=1500)
        if context_prefix:
            print(f"[LangChainAgent] Injecting {len(chat_history)} history messages as context")

        full_question = context_prefix + question

        # Create SQL agent with DB knowledge prefix
        db_prefix = (
            get_system_prompt()
            + "\n\nYou are an expert SQL agent. Use the database schema and views above. Dialect: {dialect}. Only execute SELECT."
            + "\n\nIMPORTANT — Completeness: When the user asks for N items (e.g. \"list all 10 tables\", \"top 5 customers\", \"all table names\"), always return ALL requested items. Never show partial results and then offer to show more. Always fulfill the complete request. If the result set is very large (e.g. over 50 rows), you may limit to 50 but state the total count clearly."
            + "\n\nIMPORTANT — Row counts: When asked for table row counts or how many rows are in a table, always run SELECT COUNT(*) FROM [table_name] for each table. Do NOT infer row count from the number of sample rows in table info (table info may show 0 sample rows; the only way to get the real count is COUNT(*))."
            + "\n\nOUTPUT FORMAT — You MUST present query results as a markdown table, never as bullet lists or prose. Rules:"
            + "\n1. Always use a markdown table: header row, then separator row (e.g. |---|:---|---:|), then one row per result."
            + "\n2. NEVER use placeholders (e.g. [ProductName1], [Category1], [Value]). Every cell must show the ACTUAL value from the query result. Run the query and fill the table with the real data returned."
            + "\n3. In table headers, include units where applicable: e.g. 'Total Revenue ($)', 'Amount ($)', 'Price ($)', 'Quantity (units)', 'Count' so readers know what the numbers represent."
            + "\n4. Data representation: right-align numeric and currency columns (use ---: in the separator for those columns). Left-align text columns (use :---). Format numbers with thousands separators (e.g. 1,216,581.73)."
            + "\n5. Do NOT output the raw SQL in your response; only the markdown table and a brief one-line summary if needed."
            + "\n6. Do NOT include your intermediate reasoning, retries, or error-handling steps in the final answer. Only present the final result."
            + "\n7. If a query returns NO rows (empty result), say so clearly: \"The query returned no results.\" Then explain a possible reason (e.g. filter mismatch). NEVER fabricate or invent data. NEVER say \"the values are illustrative\". If you have no data, do not produce a table."
            + "\n8. Before presenting the final table, verify that the data in the table matches the actual query result returned by the tool. If the tool returned an empty result, you MUST NOT fill the table with made-up values."
        )
        print("[LangChainAgent] Creating SQL agent (with DB knowledge prefix)...")
        try:
            agent_executor = create_sql_agent(
                llm=llm,
                db=sql_db,
                agent_type="openai-tools",
                verbose=True,
                handle_parsing_errors=True,
                prefix=db_prefix,
                max_iterations=30,
                max_execution_time=240.0,
                top_k=50,
            )
        except TypeError:
            # top_k or prefix may not be supported in some versions
            try:
                agent_executor = create_sql_agent(
                    llm=llm,
                    db=sql_db,
                    agent_type="openai-tools",
                    verbose=True,
                    handle_parsing_errors=True,
                    prefix=db_prefix,
                    max_iterations=30,
                    max_execution_time=240.0,
                )
            except TypeError:
                print("[LangChainAgent] prefix not supported, injecting DB context into question")
                full_question = db_prefix[:2000] + "\n\n---\n\n" + full_question
                agent_executor = create_sql_agent(
                    llm=llm,
                    db=sql_db,
                    agent_type="openai-tools",
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=30,
                    max_execution_time=240.0,
                )
        print("[LangChainAgent] SQL agent created, invoking...")

        # Send a "thinking" keepalive so the frontend knows we're working
        yield f"data: {json.dumps({'type': 'status', 'content': 'Querying database...'})}\n\n"

        # Run agent synchronously in a thread — wait for final output (no intermediate streaming)
        t0 = _time.time()

        async def run_agent():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent_executor.invoke(
                    {"input": full_question},
                    config={"callbacks": [handler]},
                ),
            )
            output = result.get("output", "") if isinstance(result, dict) else str(result)
            return output

        try:
            agent_output = await asyncio.wait_for(run_agent(), timeout=300.0)
        except asyncio.TimeoutError:
            print("[LangChainAgent] Agent timed out after 300s")
            raise RuntimeError("The database query took too long. Please try a simpler question.")

        elapsed = _time.time() - t0
        print(f"[LangChainAgent] Agent invocation complete | output_len={len(agent_output)} | {elapsed:.1f}s")
        captured_sql = handler._last_sql or ""
        sql_preview = captured_sql[:200] + ("..." if len(captured_sql) > 200 else "") if captured_sql else "<none>"
        print(f"[LangChainAgent] Captured SQL: {sql_preview}")
        qrows = len(handler._query_result_table) if handler._query_result_table else 0
        print(f"[LangChainAgent] Captured query result: cols={handler._query_result_columns is not None} rows={qrows}")
        if "illustrative" in agent_output.lower() or "no results" in agent_output.lower():
            print("[LangChainAgent] WARNING: Agent output may contain fabricated or empty data")

        # Clean the final output: strip ```sql...``` blocks and intermediate reasoning
        full_response = re.sub(
            r"```\s*sql\s*.*?```",
            "",
            agent_output,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        if not full_response:
            full_response = agent_output

        print(f"[LangChainAgent] Full response length: {len(full_response)} chars")

        # Post-process: detect fabricated data and replace with real result or honest no-results message
        hallucination_phrases = [
            "values are illustrative",
            "actual query result was not returned",
            "illustrative as the actual",
            "data shown is hypothetical",
        ]
        if any(phrase in full_response.lower() for phrase in hallucination_phrases):
            print("[LangChainAgent] WARNING: Detected fabricated data in agent output, cleaning up")
            qcols = getattr(handler, "_query_result_columns", None)
            qdata = getattr(handler, "_query_result_table", None)
            if qcols and qdata and len(qdata) > 0:
                full_response = _build_markdown_table(qcols, qdata) + "\n\nQuery returned the above results."
                print(f"[LangChainAgent] Replaced with real captured result: {len(qdata)} rows, {len(qcols)} cols")
            else:
                full_response = (
                    "The query returned no results. This may be due to filter conditions not matching any data "
                    "in the database. Please try adjusting your query (e.g. check filter values like SalesType or date ranges)."
                )
                print("[LangChainAgent] Replaced with honest no-results message")

        # Simulate streaming: send the final response in small chunks so the UI feels responsive
        chunk_size = 12
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            # Small delay every few chunks so the UI renders progressively
            if (i // chunk_size) % 5 == 4:
                await asyncio.sleep(0.01)

        # Parse markdown tables from the response
        all_tables = _parse_all_tables_from_markdown(full_response)
        has_table = len(all_tables) > 0
        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        # If LLM didn't output a markdown table but we captured query result from sql_db_query tool, use it
        if not all_tables:
            qcols = getattr(handler, "_query_result_columns", None)
            qdata = getattr(handler, "_query_result_table", None)
            if qcols and qdata:
                all_tables = [{"columns": qcols, "data": qdata}]
                table_data = qdata
                table_columns = qcols
                has_table = True
                print(f"[LangChainAgent] Using captured query result: {len(qdata)} rows, {len(qcols)} cols")

        sql_query = getattr(handler, "_last_sql", None) or ""

        # Emit done event
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
        if sql_query:
            print(f"[LangChainAgent] Emitted sql_query (len={len(sql_query)})")
        print("[LangChainAgent] Stream complete")

    except Exception as e:
        print(f"[LangChainAgent] EXCEPTION in stream_chat_with_database: {e}")
        import traceback
        traceback.print_exc()
        error_event = json.dumps({"type": "error", "content": str(e)})
        yield f"data: {error_event}\n\n"


def _build_history_prefix(chat_history: list[dict], max_assistant_chars: int = 1500) -> str:
    """Build [User]/[Assistant] history prefix for context (shared by SQL and simple chat). Includes sql_query when present for assistant messages."""
    if not chat_history:
        return ""
    parts = ["Previous conversation (oldest first):"]
    for i, msg in enumerate(chat_history, 1):
        role_label = "[User]" if msg.get("role") == "user" else "[Assistant]"
        content = msg.get("content") or ""
        if msg.get("role") == "assistant" and len(content) > max_assistant_chars:
            content = content[:max_assistant_chars] + "... [truncated]"
        if msg.get("role") == "assistant":
            sql_query = msg.get("sql_query") or ""
            if sql_query:
                content = content + "\n(SQL that was run: " + (sql_query[:400] + "..." if len(sql_query) > 400 else sql_query) + ")"
        parts.append(f"--- Pair {i} ---")
        parts.append(f"{role_label}\n{content}")
    parts.append("---")
    parts.append("Current question:")
    return "\n".join(parts) + " "


async def stream_simple_chat(
    question: str,
    chat_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Stream a simple LLM response (no SQL agent). Used for greetings, thanks, follow-ups.
    Yields same SSE format as stream_chat_with_database: token events, then done with
    has_table=false, sql_query="".
    """
    print(f"[LangChainAgent] stream_simple_chat called | question='{question[:80]}' | history_len={len(chat_history)}")

    token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    full_response_parts: list[str] = []

    try:
        handler = StreamingCallbackHandler(token_queue)
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY,
            callbacks=[handler],
        )
        schema_context = get_system_prompt()
        history_prefix = _build_history_prefix(chat_history)
        full_prompt = (
            f"{schema_context}\n\n"
            "You are a helpful assistant for a database analytics app. "
            "Answer briefly and naturally. Do not run SQL unless the user explicitly asks for data. "
            "For greetings, thanks, or clarification requests, respond in a short friendly way.\n\n"
            f"{history_prefix}{question}"
        )

        async def run_llm():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: llm.invoke(full_prompt, config={"callbacks": [handler]}),
                )
                return result.content if hasattr(result, "content") else str(result)
            except Exception as e:
                print(f"[LangChainAgent] stream_simple_chat LLM error: {e}")
                raise
            finally:
                await token_queue.put(None)

        llm_task = asyncio.create_task(run_llm())

        print("[LangChainAgent] stream_simple_chat streaming tokens...")
        while True:
            try:
                token = await asyncio.wait_for(token_queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                print("[LangChainAgent] stream_simple_chat token timeout")
                break
            if token is None:
                break
            if token == "":
                continue
            full_response_parts.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        try:
            await asyncio.wait_for(llm_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass

        full_response = "".join(full_response_parts)
        print(f"[LangChainAgent] stream_simple_chat complete | len={len(full_response)}")

        done_event = json.dumps({
            "type": "done",
            "has_table": False,
            "table_data": [],
            "table_columns": [],
            "tables": [],
            "full_response": full_response,
            "sql_query": "",
        })
        yield f"data: {done_event}\n\n"

    except Exception as e:
        print(f"[LangChainAgent] EXCEPTION in stream_simple_chat: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


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
            model="gpt-4.1-mini",
            temperature=0,
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
