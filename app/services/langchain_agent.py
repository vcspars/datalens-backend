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
import datetime as _dt
from decimal import Decimal
from typing import AsyncGenerator, Optional

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.services.db_knowledge_router import get_system_prompt_for_role
from app.services.skill_loader import load_skill

print("[LangChainAgent] Module loaded")


def _create_chat_llm(*, streaming: bool = False, callbacks: list | None = None):
    """Create the chat LLM based on USE_GEMINI setting.

    When USE_GEMINI=true and langchain-google-genai is installed → Gemini 2.5 Pro.
    Otherwise → gpt-4.1 via langchain-openai.
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
        seed=42,
        frequency_penalty=0,
        presence_penalty=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    if streaming and callbacks:
        kwargs["streaming"] = True
        kwargs["callbacks"] = callbacks
    else:
        kwargs["streaming"] = False
    print("[LangChainAgent] Using gpt-4.1")
    return ChatOpenAI(**kwargs)


def _create_mini_llm(*, streaming: bool = True, callbacks: list | None = None):
    """Create a lighter LLM for simple chat / report generation.

    When USE_GEMINI=true and langchain-google-genai is installed → Gemini 2.5 Pro.
    Otherwise → gpt-4.1-mini.
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
        seed=42,
        frequency_penalty=0,
        presence_penalty=0,
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
                # If the LLM's table has MORE data rows than the raw SQL result,
                # it means the LLM added computed/derived rows (e.g. P&L template
                # with Gross Profit, Operating Profit, Net Profit lines).
                # Preserve those rows — do NOT overwrite with raw SQL data.
                lm_data_row_count = len(block) - 2  # subtract header + separator
                if lm_data_row_count > len(captured_data):
                    result.extend(block)
                    print(f"[TablePipeFix] Preserved LLM-computed table ({lm_data_row_count} rows > {len(captured_data)} SQL rows)")
                else:
                    # Same or fewer rows — rebuild with properly escaped raw SQL data.
                    # Use actual SQL column names as header (not the LLM's renamed/reordered
                    # headers) so that column header and data order always match.
                    # Auto-detect alignment: right-align numeric columns, left-align text.
                    def _is_numeric_col(col: str) -> bool:
                        for r in captured_data:
                            v = str(r.get(col, "")).strip().lstrip("-").replace(",", "").replace(".", "", 1)
                            if v and not v.isdigit():
                                return False
                        return bool(captured_data)
                    sep_parts = ["---:" if _is_numeric_col(col) else ":---" for col in captured_cols]
                    header = "| " + " | ".join(str(c) for c in captured_cols) + " |"
                    separator = "| " + " | ".join(sep_parts) + " |"
                    result.append(header)
                    result.append(separator)
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

def _extract_sql_col_names(sql: str) -> list[str]:
    """Extract column names/aliases from the final SELECT of a SQL statement (handles CTEs).
    Returns actual names in SELECT order, or empty list on failure."""
    if not sql:
        return []
    upper = sql.upper()
    # Find the last top-level SELECT (after all CTE closing parens)
    depth = 0
    last_select_pos = -1
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == '(':
            depth += 1
        elif c == ')':
            if depth > 0:
                depth -= 1
        elif depth == 0 and upper[i:i+6] == 'SELECT':
            last_select_pos = i
        i += 1
    if last_select_pos == -1:
        return []
    # Find FROM after this SELECT at depth 0
    depth = 0
    from_pos = -1
    i = last_select_pos + 6
    while i < len(sql):
        c = sql[i]
        if c == '(':
            depth += 1
        elif c == ')':
            if depth > 0:
                depth -= 1
        elif depth == 0 and upper[i:i+5] in (' FROM', '\tFROM', '\nFROM'):
            from_pos = i
            break
        i += 1
    if from_pos == -1:
        return []
    select_clause = sql[last_select_pos + 6:from_pos].strip()
    # Remove TOP N
    select_clause = re.sub(r'^TOP\s+\d+\s+', '', select_clause, flags=re.IGNORECASE).strip()
    # Split by comma at depth 0 (ignore commas inside function calls)
    items: list[str] = []
    depth = 0
    current = ""
    for char in select_clause:
        if char == '(':
            depth += 1
            current += char
        elif char == ')':
            depth -= 1
            current += char
        elif char == ',' and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        items.append(current.strip())
    # Extract alias (AS <name>) or bare column name for each item
    names: list[str] = []
    for item in items:
        item = item.strip()
        as_match = re.search(r'\bAS\b\s+([`"\[]?[\w]+[`"\]]?)\s*$', item, re.IGNORECASE)
        if as_match:
            names.append(as_match.group(1).strip('`"[]'))
        else:
            parts = item.split()
            if parts:
                last = parts[-1].strip('`"[]')
                if '.' in last:
                    last = last.split('.')[-1]
                names.append(last if last and last != '*' else f"Col{len(names)+1}")
    return names


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
    """Build a markdown table string from column names and list of row dicts.
    Numeric columns are right-aligned (---:), text columns left-aligned (:---)."""
    if not columns or not data:
        return ""
    def _is_numeric(col: str) -> bool:
        for r in data:
            v = str(r.get(col, "")).strip().lstrip("-").replace(",", "").replace(".", "", 1)
            if v and not v.isdigit():
                return False
        return bool(data)
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "|" + "|".join("---:" if _is_numeric(c) else ":---" for c in columns) + "|"
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


def _sanitize_user_response(text: str) -> str:
    """Replace technical phrases so user never sees 'query', 'sql', 'returned no results' etc."""
    if not text or not text.strip():
        return text
    out = text
    for pattern, replacement, flags in _USER_FACING_FORBIDDEN:
        out = re.sub(pattern, replacement, out, flags=flags)
    return out


# ---------------------------------------------------------------------------
# SQL ReAct agent (LangGraph) — domain prompt, tools, JSON final-answer parsing
# ---------------------------------------------------------------------------

def _build_sql_domain_prompt(role: str, dialect: str = "mssql") -> str:
    """Build the full system prompt for the SQL ReAct subagent.

    Composes: role-specific schema knowledge (dynamic, from db_knowledge_router)
    + static SQL domain rules loaded from app/skills/sql_agent_skill.md.
    The dialect placeholder is spliced in as a one-liner header between the two.
    """
    parts = [
        get_system_prompt_for_role(role),
        f"\n\nDialect: {dialect}.\n\n",
        load_skill("sql_agent_skill"),
    ]
    return "".join(parts)


def _json_safe(value):
    """Convert a raw DB cell value into a JSON-serializable Python value."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, _dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (_dt.date, _dt.time)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


_SQL_AGENT_ROW_CAP = 500  # hard server-side cap regardless of what the LLM's own SQL requests


def _execute_sql_for_agent(sql_db: SQLDatabase, query: str) -> str:
    """Run *query* directly via SQLAlchemy (bypassing SQLDatabase.run's string
    formatting) so column names and values come back clean and JSON-safe —
    no ast.literal_eval / datetime-regex parsing needed downstream, and real
    column names come from the driver instead of guessed 'Column N' placeholders.

    Returns a JSON string: {"columns": [...], "rows": [...], "row_count": N,
    "truncated": bool} on success, or {"error": "..."} on failure. Errors are
    returned as tool output (not raised) so the agent can see the DB error and
    try a corrected query on its next turn.
    """
    from sqlalchemy import text as _sql_text

    stripped = (query or "").strip().rstrip(";")
    upper = stripped.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return json.dumps({"error": "Only SELECT/WITH (read-only) queries are allowed."})

    try:
        with sql_db._engine.connect() as conn:
            result = conn.execute(_sql_text(stripped))
            columns = list(result.keys())
            rows = result.fetchmany(_SQL_AGENT_ROW_CAP + 1)
    except Exception as e:
        print(f"[LangChainAgent][SQLTool] Query failed: {e}")
        return json.dumps({"error": str(e)[:500]})

    truncated = len(rows) > _SQL_AGENT_ROW_CAP
    rows = rows[:_SQL_AGENT_ROW_CAP]
    row_dicts = [
        {columns[i]: _json_safe(row[i]) for i in range(len(columns))}
        for row in rows
    ]
    print(f"[LangChainAgent][SQLTool] Query OK: {len(row_dicts)} rows, {len(columns)} cols, truncated={truncated}")
    return json.dumps({
        "columns": columns,
        "rows": row_dicts,
        "row_count": len(row_dicts),
        "truncated": truncated,
    }, default=str)


def _build_sql_tools(sql_db: SQLDatabase) -> list:
    """Build the tools the SQL ReAct agent can call.

    Deliberately minimal — no query-checker sub-chain (that would be a hidden
    extra LLM call per query) — so the only LLM calls made for a SQL question
    are the ReAct agent's own turns. If a query fails, the tool returns the DB
    error as its result and the agent can rewrite the query on its next turn.
    """

    @tool
    def sql_db_list_tables(tool_input: str = "") -> str:
        """List all tables available in the database. Input is ignored — pass an empty string."""
        try:
            return ", ".join(sql_db.get_usable_table_names())
        except Exception as e:
            return f"Error listing tables: {e}"

    @tool
    def sql_db_schema(table_names: str) -> str:
        """Get the CREATE TABLE statement and sample rows for a comma-separated
        list of table names, e.g. 'FactSalesInvoice, DimCustomer'."""
        names = [t.strip() for t in (table_names or "").split(",") if t.strip()]
        try:
            return sql_db.get_table_info(table_names=names or None)
        except Exception as e:
            return f"Error getting schema: {e}"

    @tool
    def sql_db_query(query: str) -> str:
        """Execute a read-only SQL SELECT/WITH query against the database and
        return the result as JSON: {"columns": [...], "rows": [...],
        "row_count": N, "truncated": bool}. Returns {"error": "..."} if the
        query fails — read the error, fix the query, and try again."""
        return _execute_sql_for_agent(sql_db, query)

    return [sql_db_list_tables, sql_db_schema, sql_db_query]


def _parse_json_final_answer(text: str) -> dict:
    """Parse the SQL ReAct agent's final message as JSON. Tolerates ```json
    fences and stray leading/trailing prose. Never raises — on failure it
    degrades gracefully to a plain-text response with no table, exactly like
    the old free-text path did when the agent didn't behave as instructed.
    """
    if not text or not text.strip():
        return {"response": "", "has_table": False, "tables": []}

    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()

    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: find the outermost {...} block and try that (handles stray
    # prose before/after the JSON object despite instructions not to).
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(s[start:end + 1])
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    print("[LangChainAgent] Final answer was not valid JSON — treating as plain text")
    return {"response": text.strip(), "has_table": False, "tables": []}


def _extract_last_sql_execution(messages: list) -> tuple[str, Optional[int]]:
    """Walk the ReAct loop's message trace and return (last_sql_query_text,
    last_row_count). last_row_count is None if no query ever executed
    successfully. Used to (a) report the exact SQL that ran — extracted from
    the tool-call args, never retyped by the LLM, so it can't drift — and
    (b) force an honest 'no data' response when the last query returned zero
    rows, regardless of what the LLM's JSON claims.
    """
    last_sql = ""
    last_row_count: Optional[int] = None
    for m in messages:
        for tc in (getattr(m, "tool_calls", None) or []):
            if tc.get("name") == "sql_db_query":
                q = (tc.get("args") or {}).get("query")
                if isinstance(q, str) and q.strip():
                    last_sql = q.strip()
        if getattr(m, "type", "") == "tool" and getattr(m, "name", "") == "sql_db_query":
            content = getattr(m, "content", "")
            try:
                parsed = json.loads(content) if isinstance(content, str) else None
            except (json.JSONDecodeError, ValueError):
                parsed = None
            if isinstance(parsed, dict) and "row_count" in parsed:
                last_row_count = parsed["row_count"]
    return last_sql, last_row_count


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
                # Replace generic "Column N" names with actual SQL column names/aliases
                sql_names = _extract_sql_col_names(self._last_sql or "")
                if sql_names and len(sql_names) == len(cols):
                    renamed_data = [
                        {sql_names[j]: row[cols[j]] for j in range(len(cols))}
                        for row in data
                    ]
                    cols = sql_names
                    data = renamed_data
                    print(f"[LangChainAgent][Callback] Resolved SQL column names: {cols}")
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

        llm = _create_chat_llm(streaming=False)

        # Build context prefix from history.  SQL strings are deliberately
        # excluded (include_sql=False) so the LLM input stays stable across
        # repeated identical questions, ensuring deterministic SQL at temperature=0.
        context_prefix = _build_history_prefix(chat_history, max_assistant_chars=1000, include_sql=False)
        if context_prefix:
            print(f"[LangChainAgent] Injecting {len(chat_history)} history messages as context")

        full_question = context_prefix + question

        # Build the SQL ReAct agent (LangGraph) — bounded tool-call loop over a
        # minimal tool set, JSON final answer parsed directly (no markdown
        # table regex-parsing, no callback-handler spying needed).
        dialect = "mssql"
        try:
            dialect = sql_db.dialect or dialect
        except Exception:
            pass
        system_prompt = _build_sql_domain_prompt(role, dialect)
        tools = _build_sql_tools(sql_db)
        agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)

        recursion_limit = max(4, settings.SQL_AGENT_MAX_TOOL_CALLS * 2 + 2)

        print("[LangChainAgent] Invoking SQL ReAct agent (LangGraph)...")
        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching the database...'})}\n\n"

        t0 = _time.time()
        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [HumanMessage(content=full_question)]},
                    config={"recursion_limit": recursion_limit},
                ),
                timeout=settings.SQL_AGENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            print(f"[LangChainAgent] Agent timed out after {settings.SQL_AGENT_TIMEOUT_SECONDS}s")
            raise RuntimeError("The database query took too long. Please try a simpler question.")

        elapsed = _time.time() - t0
        messages = result.get("messages", []) if isinstance(result, dict) else []
        tool_call_count = sum(1 for m in messages if getattr(m, "type", "") == "tool")

        final_text = ""
        for m in reversed(messages):
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                final_text = content.strip()
                break

        print(
            f"[LangChainAgent] SQL ReAct loop complete | {elapsed:.2f}s | "
            f"tool_calls={tool_call_count} | messages={len(messages)} | output_len={len(final_text)}"
        )

        sql_query, last_row_count = _extract_last_sql_execution(messages)
        sql_preview = sql_query[:200] + ("..." if len(sql_query) > 200 else "") if sql_query else "<none>"
        print(f"[LangChainAgent] Captured SQL: {sql_preview} | last_row_count={last_row_count}")

        answer = _parse_json_final_answer(final_text)
        response_text = str(answer.get("response") or "").strip()
        has_table = bool(answer.get("has_table"))
        raw_tables = answer.get("tables")
        if not raw_tables and (answer.get("table_columns") or answer.get("table_data")):
            # Tolerate a flattened (non-nested) shape too, in case the LLM drifts from the schema.
            raw_tables = [{"columns": answer.get("table_columns") or [], "data": answer.get("table_data") or []}]

        all_tables: list[dict] = []
        if isinstance(raw_tables, list):
            for t in raw_tables:
                if not isinstance(t, dict):
                    continue
                cols = t.get("columns") or []
                data = t.get("data") or []
                if isinstance(cols, list) and isinstance(data, list) and cols and data:
                    all_tables.append({"columns": cols, "data": data})

        # Safety net: a query that ran and returned 0 rows can never legitimately
        # produce table data — force an honest no-data message regardless of what
        # the LLM's JSON claims (same guard the old callback-handler path had).
        if sql_query and last_row_count == 0:
            print("[LangChainAgent] Query ran but returned 0 rows; forcing no-data message (no fabricated tables)")
            response_text = (
                "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."
            )
            has_table = False
            all_tables = []

        if not response_text and not all_tables:
            response_text = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

        response_text = _sanitize_user_response(response_text)
        has_table = has_table and bool(all_tables)

        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        # Build the unified text blob (narrative + rendered table(s)) that gets
        # chunk-streamed to the client — the frontend/MongoDB persistence layer
        # still expects one combined string, same shape as the old markdown path.
        response_parts = [response_text] if response_text else []
        for t in all_tables:
            md = _build_markdown_table(t["columns"], t["data"])
            if md:
                response_parts.append(md)
        full_response = "\n\n".join(p for p in response_parts if p).strip()
        if not full_response:
            full_response = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

        print(f"[LangChainAgent] Full response length: {len(full_response)} chars | has_table={has_table} | tables={len(all_tables)}")

        # ── Pre-save signal ─────────────────────────────────────────────────
        # Yield the complete response payload BEFORE any token chunks so that
        # chat.py can persist it to MongoDB the instant the agent finishes.
        # This event is never forwarded to the frontend (chat.py intercepts it).
        yield f"data: {json.dumps({'type': 'pre_done', 'full_response': full_response, 'has_table': has_table, 'table_data': table_data, 'table_columns': table_columns, 'tables': all_tables, 'sql_query': sql_query or ''})}\n\n"

        # Simulate streaming: send the final response in small chunks so the UI feels responsive
        chunk_size = 12
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            # Small delay every few chunks so the UI renders progressively
            if (i // chunk_size) % 5 == 4:
                await asyncio.sleep(0.01)

        # Emit done event (table fields already computed above)
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


async def _run_sql_react_agent(
    question: str,
    chat_history: list[dict],
    role: str = "executive",
) -> dict:
    """Run the SQL ReAct subagent and return a structured result dict.

    This is the non-streaming core of stream_chat_with_database(), extracted
    so that mcp_agent.py can call it directly as the implementation of the
    `query_sql_database` tool without duplicating any logic.

    Returns a dict with keys:
        response    (str)  — narrative text
        has_table   (bool)
        tables      (list) — list of {columns, data} dicts
        sql_query   (str)  — last SQL that ran (may be "")
        full_response (str) — narrative + rendered markdown tables combined
    """
    import time as _time

    try:
        sql_db = _get_sql_db_with_retry(max_retries=2)
    except Exception as conn_err:
        if _is_stale_connection_error(conn_err):
            raise RuntimeError("The database connection is temporarily unavailable. Please try again in a moment.") from conn_err
        raise

    llm = _create_chat_llm(streaming=False)

    context_prefix = _build_history_prefix(chat_history, max_assistant_chars=1000, include_sql=False)
    full_question = (context_prefix + question) if context_prefix else question

    dialect = "mssql"
    try:
        dialect = sql_db.dialect or dialect
    except Exception:
        pass

    system_prompt = _build_sql_domain_prompt(role, dialect)
    tools = _build_sql_tools(sql_db)
    agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
    recursion_limit = max(4, settings.SQL_AGENT_MAX_TOOL_CALLS * 2 + 2)

    print("[LangChainAgent] Invoking SQL ReAct subagent (via _run_sql_react_agent)...")
    t0 = _time.time()
    try:
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [HumanMessage(content=full_question)]},
                config={"recursion_limit": recursion_limit},
            ),
            timeout=settings.SQL_AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise RuntimeError("The database query took too long. Please try a simpler question.")

    elapsed = _time.time() - t0
    messages = result.get("messages", []) if isinstance(result, dict) else []
    tool_call_count = sum(1 for m in messages if getattr(m, "type", "") == "tool")

    final_text = ""
    for m in reversed(messages):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            final_text = content.strip()
            break

    print(
        f"[LangChainAgent] SQL ReAct subagent complete | {elapsed:.2f}s | "
        f"tool_calls={tool_call_count} | messages={len(messages)} | output_len={len(final_text)}"
    )

    sql_query, last_row_count = _extract_last_sql_execution(messages)
    answer = _parse_json_final_answer(final_text)

    response_text = str(answer.get("response") or "").strip()
    has_table = bool(answer.get("has_table"))
    raw_tables = answer.get("tables")
    if not raw_tables and (answer.get("table_columns") or answer.get("table_data")):
        raw_tables = [{"columns": answer.get("table_columns") or [], "data": answer.get("table_data") or []}]

    all_tables: list[dict] = []
    if isinstance(raw_tables, list):
        for t in raw_tables:
            if not isinstance(t, dict):
                continue
            cols = t.get("columns") or []
            data = t.get("data") or []
            if isinstance(cols, list) and isinstance(data, list) and cols and data:
                all_tables.append({"columns": cols, "data": data})

    if sql_query and last_row_count == 0:
        print("[LangChainAgent] SQL subagent: query returned 0 rows; forcing no-data message")
        response_text = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."
        has_table = False
        all_tables = []

    if not response_text and not all_tables:
        response_text = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

    response_text = _sanitize_user_response(response_text)
    has_table = has_table and bool(all_tables)

    response_parts = [response_text] if response_text else []
    for t in all_tables:
        md = _build_markdown_table(t["columns"], t["data"])
        if md:
            response_parts.append(md)
    full_response = "\n\n".join(p for p in response_parts if p).strip()
    if not full_response:
        full_response = "I couldn't find the relevant data. If you are sure that data is available, please try rephrasing your query."

    return {
        "response": response_text,
        "has_table": has_table,
        "tables": all_tables,
        "sql_query": sql_query or "",
        "full_response": full_response,
    }


def _build_history_prefix(
    chat_history: list[dict],
    max_assistant_chars: int = 1500,
    include_sql: bool = True,
) -> str:
    """Build [User]/[Assistant] history prefix for context.

    When include_sql=False (SQL agent path) previous SQL strings are omitted
    from the injected history so the LLM receives a stable input and generates
    deterministic SQL at temperature=0.  The conversation text (user questions
    and assistant summaries) is still included for contextual continuity.
    """
    if not chat_history:
        return ""
    parts = ["Previous conversation (oldest first):"]
    for i, msg in enumerate(chat_history, 1):
        role_label = "[User]" if msg.get("role") == "user" else "[Assistant]"
        content = msg.get("content") or ""
        if msg.get("role") == "assistant" and len(content) > max_assistant_chars:
            content = content[:max_assistant_chars] + "... [truncated]"
        if include_sql and msg.get("role") == "assistant":
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
