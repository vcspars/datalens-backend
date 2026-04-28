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
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage

from app.config import settings
from app.services.db_knowledge import get_system_prompt
from app.services.db_knowledge_router import get_system_prompt_for_role

print("[LangChainAgent] Module loaded")


def _create_chat_llm(*, streaming: bool = False, callbacks: list | None = None):
    """Create the chat LLM based on USE_GEMINI setting.

    When USE_GEMINI=true and langchain-google-genai is installed → Gemini 2.5 Pro.
    Otherwise → GPT-4.1 via langchain-openai.
    Note: langchain-google-genai is not in requirements.txt because it requires langchain-core>=1.2,
    which conflicts with the SQL agent stack (langchain-core 0.3.x). Set USE_GEMINI=False for a conflict-free install.
    """
    if settings.USE_GEMINI and settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            kwargs: dict = dict(
                model="gemini-2.5-pro",
                temperature=0,
                google_api_key=settings.GEMINI_API_KEY,
            )
            if streaming and callbacks:
                kwargs["streaming"] = True
                kwargs["callbacks"] = callbacks
            print("[LangChainAgent] Using Gemini 2.5 Pro")
            return ChatGoogleGenerativeAI(**kwargs)
        except ImportError as e:
            print(f"[LangChainAgent] USE_GEMINI=True but langchain_google_genai not available: {e}. Falling back to GPT.")
        except Exception as e:
            print(f"[LangChainAgent] Gemini init failed: {e}. Falling back to GPT.")

    kwargs = dict(
        model="gpt-4.1",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    if streaming and callbacks:
        kwargs["streaming"] = True
        kwargs["callbacks"] = callbacks
    else:
        kwargs["streaming"] = False
    print("[LangChainAgent] Using GPT-4.1")
    return ChatOpenAI(**kwargs)


def _create_mini_llm(*, streaming: bool = True, callbacks: list | None = None):
    """Create a lighter LLM for simple chat / report generation.

    When USE_GEMINI=true and langchain-google-genai is installed → Gemini 2.5 Pro.
    Otherwise → GPT-4.1-mini.
    """
    if settings.USE_GEMINI and settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            kwargs: dict = dict(
                model="gemini-2.5-pro",
                temperature=0,
                google_api_key=settings.GEMINI_API_KEY,
            )
            if streaming and callbacks:
                kwargs["streaming"] = True
                kwargs["callbacks"] = callbacks
            return ChatGoogleGenerativeAI(**kwargs)
        except ImportError:
            pass
        except Exception:
            pass

    kwargs = dict(
        model="gpt-4.1",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    if streaming:
        kwargs["streaming"] = True
    if callbacks:
        kwargs["callbacks"] = callbacks
    return ChatOpenAI(**kwargs)


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
    pwd_len = len(settings.SQL_PASSWORD) if settings.SQL_PASSWORD else 0
    print(
        f"[LangChainAgent] Connection string built | "
        f"server={settings.SQL_SERVER} | db={settings.SQL_DATABASE} | "
        f"driver={settings.SQL_DRIVER} | SQL_PASSWORD length={pwd_len}"
    )
    return conn


_cached_sql_db: Optional[SQLDatabase] = None

_STALE_CONNECTION_MARKERS = (
    "08S01", "10054", "10053", "Communication link failure",
    "forcibly closed", "connection was lost", "connection is broken",
    "TCP Provider", "server is not found",
)


def _is_stale_connection_error(exc: Exception) -> bool:
    """Return True if the exception looks like a stale / dropped TCP connection."""
    msg = str(exc)
    return any(marker in msg for marker in _STALE_CONNECTION_MARKERS)


def _invalidate_cached_sql_db() -> None:
    """Clear the cached SQLDatabase so the next call creates a fresh connection."""
    global _cached_sql_db
    _cached_sql_db = None
    print("[LangChainAgent] Cached SQLDatabase invalidated")


def _get_sql_db() -> SQLDatabase:
    """Return a cached LangChain SQLDatabase instance. Validates the cached
    connection with a lightweight SELECT 1; rebuilds on stale-connection errors."""
    global _cached_sql_db

    if _cached_sql_db is not None:
        try:
            _cached_sql_db.run("SELECT 1")
            print("[LangChainAgent] Reusing cached SQLDatabase connection (validated)")
            return _cached_sql_db
        except Exception as e:
            if _is_stale_connection_error(e):
                print(f"[LangChainAgent] Cached connection stale ({e}), will reconnect")
                _invalidate_cached_sql_db()
            else:
                print(f"[LangChainAgent] Cached connection check failed ({e}), will reconnect")
                _invalidate_cached_sql_db()

    import time
    t0 = time.time()
    print("[LangChainAgent] Creating SQLDatabase connection (read-only, first time — will be cached)...")
    conn_str = _build_connection_string()
    try:
        db = SQLDatabase.from_uri(conn_str, sample_rows_in_table_info=3)
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


def _get_sql_db_with_retry(max_retries: int = 2) -> SQLDatabase:
    """Call _get_sql_db() with automatic retry on stale-connection errors.
    Retries up to *max_retries* times (total attempts = max_retries + 1)."""
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return _get_sql_db()
        except Exception as e:
            last_exc = e
            if _is_stale_connection_error(e) and attempt < max_retries:
                print(f"[LangChainAgent] Stale connection on attempt {attempt + 1}, retrying...")
                _invalidate_cached_sql_db()
                continue
            raise
    raise last_exc  # type: ignore[misc]


def get_table_row_counts() -> str:
    """
    Run read-only SELECT COUNT(*) for each table and return a text block for use as context.
    Used so the summary LLM reports actual row counts instead of guessing (e.g. 3).
    """
    try:
        db = _get_sql_db_with_retry(max_retries=2)
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


def _split_md_row(line: str) -> list[str]:
    """Split a markdown table row on *unescaped* pipe characters.

    Escaped pipes (``\\|``) inside cell values are preserved as literal ``|``
    so that data like ``ERIN GATES | BEIGE`` is treated as a single cell.
    """
    # Strip the leading/trailing outer pipes, then split on un-escaped |
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    # Split on | that is NOT preceded by a backslash
    parts = re.split(r'(?<!\\)\|', stripped)
    # Un-escape \| → | in each cell value and strip whitespace
    return [p.replace("\\|", "|").strip() for p in parts]


def _fix_response_table_pipes(
    response: str,
    captured_cols: list[str],
    captured_data: list[dict],
) -> str:
    """Rebuild markdown-table data rows in *response* so that pipe characters
    inside cell values are properly escaped (``\\|``).

    *captured_cols* are the dict-keys present in each *captured_data* row
    (e.g. ``["Column 1", "Column 2", ...]`` from the LangChain handler, or
    real SQL column names from a DataFrame).

    Only tables whose header column-count matches ``len(captured_cols)`` are
    rebuilt; others are left untouched.
    """
    if not captured_data or not captured_cols:
        return response

    lines = response.splitlines()
    result: list[str] = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        # Detect start of a markdown-table block
        if stripped.startswith("|") and stripped.endswith("|"):
            block: list[str] = []
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("|") and s.endswith("|"):
                    block.append(lines[i])
                    i += 1
                else:
                    break

            # Parse header — column names from SQL rarely contain |
            hdr = block[0].strip().strip("|")
            header_cells = [c.strip() for c in hdr.split("|") if c.strip()]

            if len(header_cells) == len(captured_cols) and len(block) >= 2:
                # Keep original header + separator, rebuild data rows
                result.append(block[0])
                result.append(block[1])
                for row in captured_data:
                    cells = [
                        str(row.get(col, "")).replace("|", "\\|")
                        for col in captured_cols
                    ]
                    result.append("| " + " | ".join(cells) + " |")
                print(f"[TablePipeFix] Rebuilt markdown table: {len(captured_data)} rows, {len(captured_cols)} cols")
            else:
                # Column-count mismatch — leave table as-is
                result.extend(block)
        else:
            result.append(lines[i])
            i += 1

    return "\n".join(result)


def _parse_single_table(table_lines: list[str]) -> Optional[dict]:
    """
    Parse a contiguous block of markdown table lines into {columns, data}.
    Returns None if the block is malformed.
    Handles escaped pipes (``\\|``) inside cell values so they are not
    mistaken for column separators.
    """
    if len(table_lines) < 2:
        return None

    header_row = table_lines[0]
    columns = [c for c in _split_md_row(header_row) if c]
    if not columns:
        return None

    # table_lines[1] is the separator (--- | --- | ...)
    data_rows = []
    for line in table_lines[2:]:
        cells = _split_md_row(line)
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
    # LangChain often returns repr of list of tuples with Decimal(...) and datetime objects
    # — literal_eval can't parse these, so normalise them first.
    s = re.sub(r"Decimal\s*\(\s*['\"]?([^'\"]+)['\"]?\s*\)", r"\1", s)

    def _fmt_datetime(m: re.Match) -> str:
        """Convert datetime.datetime(Y, Mo, D, H, Mi, S[, ...]) → 'YYYY-MM-DD HH:MM:SS'."""
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            y  = int(parts[0]) if len(parts) > 0 else 0
            mo = int(parts[1]) if len(parts) > 1 else 1
            d  = int(parts[2]) if len(parts) > 2 else 1
            h  = int(parts[3]) if len(parts) > 3 else 0
            mi = int(parts[4]) if len(parts) > 4 else 0
            sc = int(parts[5]) if len(parts) > 5 else 0
            return f'"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{sc:02d}"'
        except (ValueError, IndexError):
            return f'"{m.group(1)}"'

    def _fmt_date(m: re.Match) -> str:
        """Convert datetime.date(Y, Mo, D) → 'YYYY-MM-DD'."""
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f'"{y:04d}-{mo:02d}-{d:02d}"'
        except (ValueError, IndexError):
            return f'"{m.group(1)}-{m.group(2)}-{m.group(3)}"'

    s = re.sub(r"datetime\.datetime\s*\(([^)]+)\)", _fmt_datetime, s)
    s = re.sub(r"datetime\.date\s*\((\d+),\s*(\d+),\s*(\d+)\)", _fmt_date, s)
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


# Phrases that must not appear in user-facing responses (replace with friendly wording)
_USER_FACING_FORBIDDEN = [
    (r"the query returned no results?", "no data matches that criteria", re.IGNORECASE),
    (r"the query returned no results", "no data matches that criteria", re.IGNORECASE),
    (r"query returned the above results", "here are the results", re.IGNORECASE),
    (r"query returned no results", "no data matches that criteria", re.IGNORECASE),
    (r"the sql (?:query )?returned", "the search returned", re.IGNORECASE),
    (r"sql query", "search", re.IGNORECASE),
    (r"\bquery\s+returned", "search returned", re.IGNORECASE),
]


def _strip_sql_fences(text: str) -> str:
    """Remove ```sql ... ``` code blocks using plain string operations — no regex."""
    parts: list[str] = []
    remaining = text
    lower = remaining.lower()
    while True:
        start = lower.find("```sql")
        if start == -1:
            parts.append(remaining)
            break
        parts.append(remaining[:start])
        after_open = start + 6  # len("```sql") == 6
        end = lower.find("```", after_open)
        if end == -1:
            # No closing fence — drop everything from the opening marker onward
            break
        remaining = remaining[end + 3:]
        lower = remaining.lower()
    return "".join(parts).strip()


def _strip_captured_sql(text: str, captured_sql: str) -> str:
    """Remove the exact captured SQL from the response using str.replace — no regex.

    Tries a verbatim match first, then falls back to a single-line (whitespace-
    collapsed) match to handle cases where the LLM writes the SQL on one line
    while the captured version has newlines and indentation.
    """
    if not captured_sql or not text:
        return text
    if captured_sql in text:
        return text.replace(captured_sql, "").strip()
    sql_one_line = " ".join(captured_sql.split())
    if sql_one_line in text:
        return text.replace(sql_one_line, "").strip()
    return text


def _sanitize_user_response(text: str) -> str:
    """Replace technical phrases so user never sees 'query', 'sql', 'returned no results' etc."""
    if not text or not text.strip():
        return text
    out = text
    for pattern, replacement, flags in _USER_FACING_FORBIDDEN:
        out = re.sub(pattern, replacement, out, flags=flags)
    return out


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
            else:
                # Tool returned empty or unparseable — record 0 rows so post-process can block fabricated tables
                self._query_result_table = []
                self._query_result_columns = []
                print("[LangChainAgent][Callback] Parsed query result: 0 rows (empty or unparseable)")
        self._last_tool_was_sql_query = False

    def on_tool_error(self, error, **kwargs) -> None:
        print(f"[LangChainAgent][Callback] Tool error: {error}")


# ---------------------------------------------------------------------------
# Main streaming generator
# ---------------------------------------------------------------------------

async def stream_chat_with_database(
    question: str,
    chat_history: list[dict],
    role: str = "executive",
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams SSE events for a user question.

    Args:
        question: The natural language question from the user.
        chat_history: List of {"role": ..., "content": ...} dicts (last 5 pairs).
        role: User role for selecting the appropriate DB knowledge prompt.

    Yields:
        SSE-formatted strings.
    """
    import time as _time
    print(f"[LangChainAgent] stream_chat_with_database called | question='{question[:100]}' | history_len={len(chat_history)}")

    try:
        # Build SQL DB connection (with retry for stale TCP connections)
        try:
            sql_db = _get_sql_db_with_retry(max_retries=2)
        except Exception as conn_err:
            if _is_stale_connection_error(conn_err):
                print(f"[LangChainAgent] All connection retries exhausted: {conn_err}")
                yield f"data: {json.dumps({'type': 'error', 'content': 'The database connection is temporarily unavailable. Please try again in a moment.'})}\n\n"
                return
            raise

        # Callback handler — only used for SQL capture & keepalive, NOT for token streaming
        token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        handler = StreamingCallbackHandler(token_queue)

        llm = _create_chat_llm(streaming=False)

        # Build context prefix from history (larger assistant context for SQL path)
        context_prefix = _build_history_prefix(chat_history, max_assistant_chars=1500)
        if context_prefix:
            print(f"[LangChainAgent] Injecting {len(chat_history)} history messages as context")

        full_question = context_prefix + question

        # Create SQL agent with DB knowledge prefix (role-specific)
        db_prefix = (
            get_system_prompt_for_role(role)
            + "\n\nYou are an expert SQL agent for the StarScemaSPARS star schema database. "
            + "Dialect: {dialect}. Only execute SELECT queries — never INSERT, UPDATE, DELETE, DROP, or DDL."

            + "\n\n=== ROW LIMITS (CRITICAL — ABSOLUTE MAXIMUM 40 ROWS) ==="
            + "\n• ALWAYS include SELECT TOP 40 in EVERY query. TOP 40 is the hard maximum — never exceed it."
            + "\n• If user says 'top 10', use TOP 10. If user says 'top 5', use TOP 5."
            + "\n• If user says 'all' or requests more than 40 rows, silently cap at TOP 40."
            + "\n• GROUP BY queries (per-customer, per-product, per-reason breakdowns) MUST use TOP 40 — they return thousands of rows without it."
            + "\n• ONLY exception: a query returning exactly ONE row (SELECT SUM/COUNT with no GROUP BY) does not need TOP."
            + "\n• NEVER run any multi-row SELECT without TOP — fact tables contain millions of rows."
            + "\n• If user asks for row counts, run SELECT COUNT(*) with no GROUP BY — do NOT select all rows."
            + "\n• TOP-N PER GROUP (CRITICAL PATTERN): When the user asks for 'top N per category', 'top N per group',"
            + "\n  'top N within each X', or 'N items from each Y' — this is a PARTITION query, NOT a simple TOP query."
            + "\n  MANDATORY STRUCTURE:"
            + "\n    Step 1 — Compute the classification/grouping in a CTE (e.g. ABC_Category)"
            + "\n    Step 2 — In a separate CTE, assign ROW_NUMBER() OVER (PARTITION BY <classification_col> ORDER BY <metric> DESC) AS rn"
            + "\n    Step 3 — Final SELECT filters WHERE rn <= N  ← this is where the user's 'top N' is applied"
            + "\n    Step 4 — Outer SELECT TOP = N × number_of_groups  (e.g. top 10 per 3 ABC categories = SELECT TOP 30)"
            + "\n  CRITICAL: The user's 'top N' maps to WHERE rn <= N — NOT to the outer SELECT TOP clause."
            + "\n  CRITICAL: ALL groups must appear in the result — NEVER filter to just one group."
            + "\n  CRITICAL: NEVER add a WHERE clause that limits to a single group value (e.g. WHERE ABCCategory = 'A')."
            + "\n  CRITICAL: NEVER say 'only X category shown due to row limit' — show all groups using PARTITION BY."
            + "\n  CRITICAL PARTITION BY RULE: The PARTITION BY must contain ONLY the classification/group column."
            + "\n    CORRECT: PARTITION BY ABC_Category"
            + "\n    WRONG:   PARTITION BY ABC_Category, DP.Category   ← adding extra dimension columns creates thousands of micro-groups"
            + "\n    Adding any extra column to PARTITION BY (e.g. product Category, Region, Warehouse) multiplies the number"
            + "\n    of partitions and makes the rn filter meaningless — each tiny group gets rn=1,2,3... independently."
            + "\n  CRITICAL ABC ANALYSIS RULE: ABC classification must use the cumulative Pareto method (running sum):"
            + "\n    A = items where cumulative inventory value (ordered high→low) ≤ 80% of total inventory value"
            + "\n    B = cumulative value between 80% and 95%"
            + "\n    C = cumulative value above 95%"
            + "\n    Use SUM() OVER (ORDER BY value DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) for running total."
            + "\n    NEVER use PERCENTILE_CONT or value thresholds for ABC — only the cumulative Pareto running-sum method."
            + "\n  Example: 'top 5 per ABC category' (3 groups) → PARTITION BY ABC_Category only, WHERE rn <= 5, SELECT TOP 15."
            + "\n  Example: 'top 3 products per warehouse' (8 warehouses) → PARTITION BY WarehouseKey only, WHERE rn <= 3, SELECT TOP 24."
            + "\n  If N × number_of_groups exceeds 40, reduce N so that all groups still appear (e.g. top 13 × 3 = 39 ≤ 40)."

            + "\n\n=== COMPLETENESS ==="
            + "\n• Present the FULL result up to TOP 40. NEVER say 'similar data available for others'."
            + "\n• Do NOT infer row counts from samples — always run SELECT COUNT(*)."

            + "\n\n=== OUTPUT FORMAT — FINAL ANSWER RULES ==="
            + "\n• !! FINANCIAL STATEMENT EXCEPTION (Balance Sheet / P&L / Income Statement) !!"
            + "\n  When the user asks for any financial statement, output ONLY a TWO-COLUMN markdown table."
            + "\n  NO summary sentence, NO extra text before or after the table, NO SQL."
            + "\n  Use header: | Description | Amount ($) | with alignment |:---|---:|"
            + "\n"
            + "\n  BALANCE SHEET — HOW TO FORMAT EACH QUERY LEVEL:"
            + "\n  The SQL returns columns [Section], [Line Item], [Amount] OR [Section], [Sub Group], [Line Item], [Amount]."
            + "\n  Read the column names in the result to determine which level you are at:"
            + "\n"
            + "\n  LEVEL 1 — Main Grouped (SQL returns 3 cols: Section, Line Item, Amount):"
            + "\n    For each unique Section value, output:"
            + "\n      | **<Section value>** | |"
            + "\n      |     <Line Item value> | <Amount value> |   <- one row per Line Item"
            + "\n      | **Total <Section value>** | <sum of all amounts for this Section> |"
            + "\n      | | |   <- blank separator before next section"
            + "\n"
            + "\n  LEVEL 2 — Sub Grouped (SQL returns 4 cols: Section, Sub Group, Line Item, Amount):"
            + "\n    For each unique Section value, output:"
            + "\n      | **<Section value>** | |"
            + "\n      For each Sub Group within the Section:"
            + "\n        | **<Sub Group value>** | |"
            + "\n        |     <Line Item value> | <Amount value> |   <- one row per Line Item"
            + "\n        | **Total <Sub Group value>** | <sum of amounts for this Sub Group> |"
            + "\n        | | |"
            + "\n      | **Total <Section value>** | <sum of all amounts for this Section> |"
            + "\n      | | |"
            + "\n"
            + "\n  LEVEL 3 — Detailed (SQL returns 5 cols: Section, Sub Group, Detail Group, Account, Amount):"
            + "\n    4-level nesting: Section -> Sub Group -> Detail Group -> Account"
            + "\n    Bold headers for each level, indented line items for lowest level."
            + "\n"
            + "\n  P&L / INCOME STATEMENT — HOW TO FORMAT EACH QUERY LEVEL:"
            + "\n  IMPORTANT: P&L and Income Statement are the same report. Both use the same templates."
            + "\n"
            + "\n  LEVEL 1 — Main Grouped (SQL returns 2 cols: Group, Amount):"
            + "\n    The query returns raw group amounts. You MUST compute and insert the derived lines:"
            + "\n      Gross Profit/(Loss)     = SALES amount - COST OF SALES amount"
            + "\n      Total Operating Cost    = GENERAL & ADMINISTRATIVE amount + SELLING EXPENSES amount"
            + "\n      Operating Profit/(Loss) = Gross Profit - Total Operating Cost"
            + "\n      Net Profit/(Loss)       = Operating Profit + OTHER INCOME amount - INCOME TAXES amount"
            + "\n    Output order (regardless of ORDER BY in SQL):"
            + "\n      | **Sales** | <SALES amount> |"
            + "\n      | **Cost Of Sales** | <COST OF SALES amount> |"
            + "\n      | **Gross Profit/(Loss)** | <computed> |"
            + "\n      | | |"
            + "\n      | **Operating Cost** | |"
            + "\n      |     General & Administrative | <GENERAL & ADMINISTRATIVE amount> |"
            + "\n      |     Selling Expenses | <SELLING EXPENSES amount> |"
            + "\n      | **Total Operating Cost** | <computed> |"
            + "\n      | **Operating Profit/(Loss)** | <computed> |"
            + "\n      | | |"
            + "\n      | **Other Income** | <OTHER INCOME amount> |"
            + "\n      | **Income Taxes** | <INCOME TAXES amount> |"
            + "\n      | **Net Profit/(Loss)** | <computed> |"
            + "\n"
            + "\n  LEVEL 2 — Sub Grouped (SQL returns 3 cols: Main Group, Sub Group, Amount):"
            + "\n    For SALES and COST OF SALES: bold section header, indented sub-group items, bold Total row."
            + "\n    For GENERAL & ADMINISTRATIVE and SELLING EXPENSES: nest them under a bold 'Operating Cost' header."
            + "\n    Insert Gross Profit, Total Operating Cost, Operating Profit, Net Profit as computed bold rows."
            + "\n    For OTHER INCOME and INCOME TAXES: bold section header, indented sub-group items, bold Total row."
            + "\n"
            + "\n  LEVEL 3 — Detailed (SQL returns 4 cols: Main Group, Sub Group, Account, Amount):"
            + "\n    3-level nesting: bold Main Group header -> bold Sub Group header -> indented Account items."
            + "\n    Insert same computed lines (Gross Profit, Operating Profit, Net Profit) as bold rows."
            + "\n"
            + "\n  FORMATTING RULES (apply to ALL levels):"
            + "\n  - Section/Main headers: | **Header** | |  (no amount)"
            + "\n  - Sub-group headers: | **Sub Group name** | |  (no amount)"
            + "\n  - Line items: |     Line Item name | 1,234.56 |  (4 spaces indent)"
            + "\n  - Computed totals: | **Total Label** | 1,234,567.89 |"
            + "\n  - Blank separator: | | |  (between major sections)"
            + "\n  - Numbers: 2 decimal places, thousands separators (1,234,567.89), negative with minus sign"
            + "\n• !! ABSOLUTE RULE — ZERO SQL IN YOUR FINAL ANSWER !!"
            + "\n  The SQL you write runs internally as a tool. The user NEVER sees it."
            + "\n  Do NOT include SELECT, WITH, FROM, JOIN, WHERE, GROUP BY, ORDER BY,"
            + "\n  CASE WHEN, HAVING, or ANY other SQL keyword or syntax in the text you send to the user."
            + "\n  Violating this rule means your response is wrong regardless of the data."
            + "\n  1. If user requests for descriptive repsonse then use summarized descriptive response and then show the data as a markdown table, along 2 3 lines text."
            + "\n     - Write like a business analyst, not a developer."
            + "\n     - No technical words: never use 'table', 'query', 'column', 'row', 'database', 'SQL', 'dataset', 'record'."
            + "\n     - Naturally mention key figures or trends by thinking step by step for the calculation like SUM, AVG, MAX, MIN, COUNT, etc. and always follow the proper formatting like bold for headings, italic, $ sign, and etc" 
            + "\n     - Do NOT repeat the user's question back to them."
            + "\n  2. The data as a markdown table immediately after the summary."
            + "\n• Format the table: header row → separator row (|:---|---:|) → one data row per result."
            + "\n• NEVER use placeholders like [ProductName1] or [Value]. Every cell must be ACTUAL data."
            + "\n• Include units in column headers: 'Revenue ($)', 'Quantity (units)', 'Growth (%)'."
            + "\n• Right-align numeric columns (---:). Left-align text (:---). Use thousands separators: 1,216,581.73."
            + "\n• Do NOT show intermediate reasoning, retries, or tool calls — final result only."
            + "\n• If no matching rows: say exactly \"I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query.\" and briefly suggest why."
            + "\n• NEVER use the words 'query', 'SQL', or 'returned no results' in your response."
            + "\n• NEVER include SQL code in your final answer — not as a code block, not inline, not as a summary."
            + "\n  The SQL is captured and shown to users separately. Your answer must contain ONLY the business interpretation of the results."
            + "\n  Any SELECT, WITH, FROM, JOIN, WHERE, GROUP BY, or ORDER BY clause appearing in your final answer is a strict violation."
            + "\n• NEVER fabricate data, use illustrative values, or produce a table when the tool returned empty."

            + "\n\n=== DATA QUALITY — MANDATORY FILTERS ==="
            + "\n• SALES INVOICES: ALWAYS exclude voided, cancelled, and reversed invoices:"
            + "\n  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')"
            + "\n  Apply this on EVERY query against FactSalesInvoice — no exceptions."
            + "\n  Omitting this filter inflates revenue figures with invalid transactions."
            + "\n• SALES ORDERS: ALWAYS exclude cancelled and voided orders:"
            + "\n  AND FSO.Status NOT IN (8, 9)   -- 8=Cancel, 9=Void"
            + "\n• CREDIT MEMOS: ALWAYS exclude voided credit memos:"
            + "\n  AND FCM.Status <> 9   -- 9=Void"
            + "\n• VENDOR INVOICES: ALWAYS exclude voided vendor invoices:"
            + "\n  AND FVI.Status <> 3   -- 3=Void"

            + "\n\n=== MATHEMATICAL / BDMAS RULES (CRITICAL) ==="
            + "\n• Always follow BDMAS order of operations: Brackets → Division → Multiplication → Addition → Subtraction."
            + "\n• ALWAYS wrap compound arithmetic expressions in parentheses to make precedence explicit."
            + "  WRONG:  a + b * c        RIGHT:  a + (b * c)"
            + "  WRONG:  a - b / c        RIGHT:  a - (b / c)"
            + "\n• Division — ALWAYS use NULLIF to prevent divide-by-zero errors:"
            + "  WRONG:  numerator / denominator"
            + "  RIGHT:  numerator / NULLIF(denominator, 0)"
            + "\n• Percentage calculations — cast to decimal FIRST, then divide, then multiply:"
            + "  RIGHT:  ROUND(100.0 * numerator / NULLIF(denominator, 0), 2)"
            + "\n• Growth rate / change % — always use ABS on denominator to handle negative base values:"
            + "  RIGHT:  ROUND(100.0 * (current_val - prior_val) / NULLIF(ABS(prior_val), 0), 2)"
            + "\n• Averages — use NULLIF on COUNT to avoid divide-by-zero:"
            + "  RIGHT:  SUM(col) / NULLIF(COUNT(*), 0)"
            + "\n• Never rely on implicit integer division — always multiply by 1.0 or use 100.0 when a decimal result is needed."
            + "\n• Subtraction for net amounts: always parenthesise: (SalesAmount - CostAmount) AS ProfitAmount"
            + "\n• When combining SUM and arithmetic, apply SUM before dividing:"
            + "  RIGHT:  SUM(col1) / NULLIF(SUM(col2), 0)    WRONG:  SUM(col1 / col2)"
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
                max_iterations=16,
                max_execution_time=240.0,
                top_k=30,
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
                    max_iterations=16,
                    max_execution_time=240.0,
                    top_k=30,
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
                    max_iterations=16,
                    max_execution_time=240.0,
                    top_k=30,
                )
        print("[LangChainAgent] SQL agent created, invoking...")

        # Send a "thinking" keepalive so the frontend knows we're working
        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching the database...'})}\n\n"

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

        # Extract captured SQL early — used both for cleaning and the done event
        sql_query = getattr(handler, "_last_sql", None) or ""

        # Strip fenced SQL blocks (no regex) then remove any bare SQL that matches
        # exactly what was executed (verbatim or whitespace-collapsed)
        full_response = _strip_sql_fences(agent_output)
        if not full_response:
            full_response = agent_output
        if sql_query:
            full_response = _strip_captured_sql(full_response, sql_query)

        print(f"[LangChainAgent] Full response length: {len(full_response)} chars")

        qcols = getattr(handler, "_query_result_columns", None)
        qdata = getattr(handler, "_query_result_table", None)
        qrows = len(qdata) if qdata else 0
        has_captured_sql = bool((getattr(handler, "_last_sql", None) or "").strip())

        # When the DB query returned 0 rows, never show fabricated tables — force no-data message
        if has_captured_sql and qrows == 0:
            print("[LangChainAgent] Query ran but returned 0 rows; forcing no-data message (no placeholders)")
            full_response = (
                "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."
            )
        else:
            # Post-process: detect fabricated data (placeholders or illustrative phrasing) and replace
            hallucination_phrases = [
                "values are illustrative",
                "actual query result was not returned",
                "illustrative as the actual",
                "data shown is hypothetical",
            ]
            placeholder_pattern = re.compile(r"\[[A-Za-z]+\d+\]")  # e.g. [ProductName1], [WarehouseName2]
            has_placeholder_cells = bool(placeholder_pattern.search(full_response))

            if has_placeholder_cells or any(phrase in full_response.lower() for phrase in hallucination_phrases):
                print("[LangChainAgent] WARNING: Detected fabricated data or placeholders in agent output, cleaning up")
                if qcols and qdata and len(qdata) > 0:
                    full_response = _build_markdown_table(qcols, qdata) + "\n\nHere are the results."
                    print(f"[LangChainAgent] Replaced with real captured result: {len(qdata)} rows, {len(qcols)} cols")
                else:
                    full_response = (
                        "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."
                    )
                    print("[LangChainAgent] Replaced with honest no-results message")

        full_response = _sanitize_user_response(full_response)

        # Fix pipe-in-data: rebuild markdown tables with properly escaped
        # values from the captured SQL result (immune to embedded pipes).
        _rc = getattr(handler, "_query_result_columns", None)
        _rd = getattr(handler, "_query_result_table", None)
        if _rc and _rd and len(_rd) > 0:
            full_response = _fix_response_table_pipes(full_response, _rc, _rd)

        # Simulate streaming: send the final response in small chunks so the UI feels responsive
        chunk_size = 12
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            # Small delay every few chunks so the UI renders progressively
            if (i // chunk_size) % 5 == 4:
                await asyncio.sleep(0.01)

        # Build structured table data for the UI (save/export/graph).
        # The markdown tables in full_response have already been rebuilt by
        # _fix_response_table_pipes (escaped pipes, real data from captured
        # SQL result).  Parse them to get real column names + all tables.
        all_tables = _parse_all_tables_from_markdown(full_response)
        has_table = len(all_tables) > 0
        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        # If no markdown tables found, fall back to raw captured SQL result
        if not all_tables:
            qcols = getattr(handler, "_query_result_columns", None)
            qdata = getattr(handler, "_query_result_table", None)
            if qcols and qdata and len(qdata) > 0:
                all_tables = [{"columns": qcols, "data": qdata}]
                table_data = qdata
                table_columns = qcols
                has_table = True
                print(f"[LangChainAgent] Using captured query result (fallback): {len(qdata)} rows, {len(qcols)} cols")

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
        if _is_stale_connection_error(e):
            _invalidate_cached_sql_db()
            user_msg = "The database connection was interrupted. Please try your question again."
        else:
            user_msg = str(e)
        error_event = json.dumps({"type": "error", "content": user_msg})
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
    role: str = "executive",
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
        llm = _create_mini_llm(streaming=True, callbacks=[handler])
        schema_context = get_system_prompt_for_role(role)
        history_prefix = _build_history_prefix(chat_history)
        full_prompt = (
            f"{schema_context}\n\n"
            "Think step by step. You are a helpful assistant for a database analytics app. "
            "Answer briefly and naturally using plain English only.\n"
            "STRICT RULES — never break these:\n"
            "  1. NEVER write SQL, code, or any SELECT/VALUES/INSERT statement in your response — not even as an example.\n"
            "  2. If the user asks about their previous questions or conversation history, read the conversation above and list them as plain numbered text.\n"
            "  3. For greetings, thanks, or clarification requests, respond in a short friendly way.\n"
            "  4. For advisory questions (e.g. 'how can this help me', 'what should I do'), give a concise plain-English answer based on what has already been discussed.\n"
            "  5. MATHEMATICAL / BDMAS RULES — when explaining or computing any numbers:\n"
            "     • Follow BDMAS order: Brackets → Division → Multiplication → Addition → Subtraction.\n"
            "     • Always resolve brackets/parentheses first before any other operation.\n"
            "     • Multiplication and Division are evaluated before Addition and Subtraction.\n"
            "     • Percentage: divide first, then multiply by 100.  e.g. (part / total) × 100.\n"
            "     • Growth rate: (current − previous) / |previous| × 100.\n"
            "     • Never divide by zero — if denominator is zero, state 'N/A' or 'undefined'.\n"
            "     • Show intermediate steps when explaining a calculation so the user can verify.\n\n"
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
        llm = _create_mini_llm(streaming=True)

        if custom_system_prompt:
            system_prompt = custom_system_prompt
        else:
            system_prompt = (
                f"You are a professional data analyst generating a {template} report. "
                "Use the provided data context and generate a well-structured, detailed markdown report. "
                "Include sections like Executive Summary, Key Findings, Analysis, and Recommendations. "
                "Format all content as clean markdown. Do NOT wrap the output in code fences. "
                "Do NOT end with phrases like 'If you require further detailed analysis or specific data visualizations, please let me know' or similar open-ended offers to the reader.\n\n"
                "CRITICAL RULES:\n"
                "- NEVER use placeholders like [placeholder], [value], [column name], [X], [Y], or ANY bracket-enclosed placeholder text anywhere in the report, including inside tables.\n"
                "- Every cell in every table MUST contain actual data values from the provided data context. If a specific value is not available, write 'N/A' — never a placeholder.\n"
                "- If a mathematical calculation is needed (totals, averages, percentages, growth rates, differences, etc.), compute it using the data provided. Never leave a calculated field as a placeholder or say 'to be calculated'.\n"
                "- All numerical values in tables and text must be real figures derived from the data context.\n"
                "- Do NOT leave ANY field, bullet point, or table cell with placeholder or template text."
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
