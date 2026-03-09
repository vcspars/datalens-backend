"""
Vanna AI agent for Chat with Database.
Streams SSE events compatible with the LangChain agent (token, done with sql_query, error).
Training uses ChromaDB (persistent) and shared db_knowledge (views + docs).
"""

import json
import asyncio
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Optional

# Official analytics views; qualify with dbo. only if present in the database.
# Any other view names from earlier training/runs are no longer used.
_VANNA_VIEW_NAMES = [
    "VW_SalesByWarehouse",
    "VW_SalesMonthly",
    "VW_CustomerCreditYearly",
    "VW_CustomerPayment",
    "VW_VendorReturnQtyMonthly",
]

# Disable Chroma telemetry before any chromadb import
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from app.config import settings
from app.services.db_knowledge import get_training_docs, ALL_VIEW_DDLS
from app.services.sql_utils import is_read_only_sql

# Reuse table parsing from langchain_agent (no circular import: langchain_agent does not import vanna_agent)
from app.services.langchain_agent import _parse_all_tables_from_markdown

print("[VannaAgent] Module loaded")


def _vanna_chromadb_path() -> str:
    """Persistent ChromaDB directory under backend."""
    backend = Path(__file__).resolve().parent.parent.parent
    path = backend / "vanna_chromadb"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _build_odbc_conn_str() -> str:
    """Build ODBC connection string for Vanna MSSQL."""
    return (
        f"DRIVER={{{settings.SQL_DRIVER}}};"
        f"SERVER={settings.SQL_SERVER};"
        f"DATABASE={settings.SQL_DATABASE};"
        f"UID={settings.SQL_USER};"
        f"PWD={settings.SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )


def _dataframe_to_markdown(df) -> str:
    """Convert pandas DataFrame to markdown table."""
    if df is None or df.empty:
        return ""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) if row.get(c) is not None else "" for c in cols) + " |")
    return "\n".join(lines)


def _looks_like_sql(text: str) -> bool:
    """Return True if text appears to be executable SQL (SELECT/WITH), not conversational."""
    s = text.strip()
    if not s:
        return False
    upper = s.upper()
    if upper.startswith("SELECT") or upper.startswith("WITH") or upper.startswith("("):
        return True
    if "SELECT" in upper and "FROM" in upper:
        return True
    if s.startswith("--") and "SELECT" in upper:
        return True
    return False


def _ensure_mssql_batch(sql: str) -> str:
    """
    If the extracted SQL references common T-SQL variables (@CurrentYear, @CurrentMonth)
    that Vanna's extract_sql() stripped from the batch, prepend DECLAREs so execution succeeds.
    Returns the SQL to run; caller keeps original sql_query for UI/done event.
    """
    s = sql.strip()
    if not s:
        return sql
    decls = []
    if "@CurrentYear" in s:
        decls.append("DECLARE @CurrentYear INT = YEAR(GETDATE());")
    if "@CurrentMonth" in s:
        decls.append("DECLARE @CurrentMonth INT = MONTH(GETDATE());")
    if not decls:
        return sql
    return "\n".join(decls) + "\n" + s


def _qualify_view_schema(sql: str) -> str:
    """
    Qualify known view names with dbo. so SQL Server resolves them (avoids Invalid object name).
    Only replaces unqualified occurrences after FROM/JOIN.
    """
    result = sql
    for view_name in _VANNA_VIEW_NAMES:
        escaped = re.escape(view_name)
        # FROM view_name or JOIN view_name (case-insensitive), only when not already dbo.view_name
        result = re.sub(
            rf"(?i)\b(FROM)\s+(?!dbo\.){escaped}\b",
            rf"\1 dbo.{view_name}",
            result,
        )
        result = re.sub(
            rf"(?i)\b(JOIN)\s+(?!dbo\.){escaped}\b",
            rf"\1 dbo.{view_name}",
            result,
        )
    return result


# ---------------------------------------------------------------------------
# Vanna instance and training (lazy)
# ---------------------------------------------------------------------------

_vn = None
_trained = False


def _get_vn():
    """Create and return the Vanna instance; run training once."""
    global _vn, _trained
    if _vn is not None:
        if not _trained:
            _ensure_trained(_vn)
            _trained = True
        return _vn

    print("[VannaAgent] Initializing Vanna (ChromaDB + OpenAI)...")
    try:
        from vanna.legacy.openai.openai_chat import OpenAI_Chat
        from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
    except ImportError as e:
        raise ImportError(
            "Vanna AI dependencies missing. Install with: pip install vanna chromadb"
        ) from e

    class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
        def __init__(self, config=None):
            config = config or {}
            ChromaDB_VectorStore.__init__(self, config=config)
            OpenAI_Chat.__init__(self, config=config)

    chroma_path = _vanna_chromadb_path()
    _vn = MyVanna(config={
        "api_key": settings.OPENAI_API_KEY,
        "model": "gpt-4.1-mini",
        "path": chroma_path,
    })
    print(f"[VannaAgent] ChromaDB path: {chroma_path}")

    odbc_str = _build_odbc_conn_str()
    print(f"[VannaAgent] Connecting to MSSQL | server={settings.SQL_SERVER} | db={settings.SQL_DATABASE}")
    _vn.connect_to_mssql(odbc_conn_str=odbc_str)
    print("[VannaAgent] MSSQL connection ready")

    _ensure_trained(_vn)
    _trained = True
    return _vn


def _ensure_trained(vn):
    """Train on schema, view DDLs, and documentation if not already present."""
    try:
        existing = vn.get_training_data()
        if existing is not None and len(existing) > 0:
            print(f"[VannaAgent] Training data already present (count={len(existing)}), skipping train")
            return
    except Exception as e:
        print(f"[VannaAgent] get_training_data check: {e}, will train")

    print("[VannaAgent] Training: DDL (views) + documentation...")
    for ddl in ALL_VIEW_DDLS:
        vn.train(ddl=ddl.strip())
    vn.train(documentation=get_training_docs())
    print("[VannaAgent] Training complete")


# ---------------------------------------------------------------------------
# Streaming chat
# ---------------------------------------------------------------------------

async def stream_chat_with_database_vanna(
    question: str,
    chat_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams SSE events for a user question (Vanna path).
    Emits: token, done (with sql_query, has_table, table_data, table_columns, tables, full_response), error.
    """
    print(f"[VannaAgent] stream_chat_with_database_vanna | question='{question[:100]}' | history_len={len(chat_history)}")

    try:
        loop = asyncio.get_event_loop()
        vn = await loop.run_in_executor(None, _get_vn)

        # 1) Generate SQL (sync, in executor)
        print("[VannaAgent] Generating SQL...")
        sql_query = await loop.run_in_executor(None, lambda: vn.generate_sql(question))
        if not sql_query or not sql_query.strip():
            print("[VannaAgent] No SQL generated")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Could not generate a SQL query for your question.'})}\n\n"
            return

        print(f"[VannaAgent] Generated SQL (len={len(sql_query)}): {sql_query[:200]}...")

        # If the model returned conversational text (e.g. "hi" -> "I'm here to help..."), don't run as SQL
        if not _looks_like_sql(sql_query):
            print("[VannaAgent] Response is conversational, not SQL; returning as message")
            reply = sql_query.strip()
            yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'full_response': reply, 'sql_query': None, 'has_table': False, 'table_data': [], 'table_columns': [], 'tables': []})}\n\n"
            print("[VannaAgent] Stream complete (conversational)")
            return

        # 2) Run SQL (sync, in executor); prepend DECLAREs if needed, qualify views with dbo.
        sql_to_run = _ensure_mssql_batch(sql_query)
        sql_to_run = _qualify_view_schema(sql_to_run)
        if not is_read_only_sql(sql_to_run):
            print("[VannaAgent] Rejected non-read-only SQL; application never modifies the database")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Only read-only queries (SELECT) are allowed. This application never updates or deletes data in the database.'})}\n\n"
            return
        print("[VannaAgent] Running SQL (read-only)...")
        try:
            df = await loop.run_in_executor(None, lambda: vn.run_sql(sql_to_run))
        except Exception as e:
            print(f"[VannaAgent] run_sql error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return

        # 3) Build context for LLM: question + table as markdown
        table_md = _dataframe_to_markdown(df) if df is not None else ""
        context = f"Question: {question}\n\nResult data (markdown table):\n{table_md}" if table_md else f"Question: {question}\n\nNo rows returned."

        # 4) Stream natural language response from LLM (sync stream in executor + queue)
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        system = (
            "You are a helpful data analyst. Answer the user's question based on the result data provided. "
            "If there is a markdown table, you may summarize it and/or include it in your response. "
            "Format tables in markdown (| col | col |). Be concise."
        )
        full_parts = []
        token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def run_stream():
            try:
                for chunk in llm.stream([
                    SystemMessage(content=system),
                    HumanMessage(content=context),
                ]):
                    if chunk.content:
                        full_parts.append(chunk.content)
                        try:
                            loop.call_soon_threadsafe(token_queue.put_nowait, chunk.content)
                        except Exception:
                            pass
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        fut = loop.run_in_executor(None, run_stream)

        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        await fut  # re-raise any exception from run_stream
        text_response = "".join(full_parts)

        # Append the actual data table so the UI can parse it
        if table_md:
            text_response += "\n\n" + table_md

        # Parse tables from full response (for has_table, table_data, table_columns, tables)
        all_tables = _parse_all_tables_from_markdown(text_response)
        has_table = len(all_tables) > 0
        table_data = all_tables[0]["data"] if all_tables else []
        table_columns = all_tables[0]["columns"] if all_tables else []

        done_event = json.dumps({
            "type": "done",
            "has_table": has_table,
            "table_data": table_data,
            "table_columns": table_columns,
            "tables": all_tables,
            "full_response": text_response,
            "sql_query": sql_query.strip(),
        })
        yield f"data: {done_event}\n\n"
        print("[VannaAgent] Stream complete")

    except Exception as e:
        print(f"[VannaAgent] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
