"""
Direct SQL test endpoint — no LangChain agent involved.

Flow:
  1. Receive natural-language question + role
  2. Generate SQL with GPT-4.1 using the same role-specific schema prompt
  3. Validate the SQL is a safe SELECT
  4. Run it against the existing cached MSSQL connection
  5. Return structured JSON with columns, rows, and timing

Accessible via FastAPI /docs at POST /api/test/direct-query
"""

import re
import time
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from openai import OpenAI

from app.config import settings
from app.services.db_knowledge_router import get_system_prompt_for_role
from app.services.langchain_agent import _get_sql_db

router = APIRouter(tags=["Test: Direct SQL (No Agent)"])

_openai_client: Optional[OpenAI] = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


class DirectQueryRequest(BaseModel):
    question: str
    role: str = "executive"  # executive | sales | operations


class DirectQueryResponse(BaseModel):
    question: str
    generated_sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int
    error: Optional[str] = None


def _strip_sql_fences(text: str) -> str:
    """Remove markdown ```sql ... ``` or ``` ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _is_safe_select(sql: str) -> bool:
    """Return True only if the SQL starts with SELECT or WITH (CTE)."""
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    return first_word in ("SELECT", "WITH")


@router.post(
    "/test/direct-query",
    response_model=DirectQueryResponse,
    summary="Direct SQL generation + execution (no LangChain agent)",
    description=(
        "Generates a SQL query from a natural-language question using GPT-4.1 "
        "and the same role-specific schema prompt used by the main chat agent, "
        "then executes it directly against the cached MSSQL database.\n\n"
        "**role** options: `executive`, `sales`, `operations`\n\n"
        "This endpoint is for testing the non-agent SQL path — it is NOT "
        "protected by auth and is intended for FastAPI /docs testing only."
    ),
)
def direct_query(req: DirectQueryRequest) -> DirectQueryResponse:
    t_start = time.time()
    role = req.role.lower().strip()
    if role not in ("executive", "sales", "operations"):
        role = "executive"

    print(f"[DirectQuery] question={req.question!r} role={role!r}")

    # ------------------------------------------------------------------ #
    # Step 1: Build system prompt (same schema doc used by main agent)    #
    # ------------------------------------------------------------------ #
    schema_prompt = get_system_prompt_for_role(role)

    sql_gen_system = (
        schema_prompt
        + "\n\n"
        + "Your ONLY task is to generate a single valid T-SQL SELECT query for the question below.\n"
        + "Rules:\n"
        + "  - Use SELECT TOP 40 unless the question asks for fewer rows or is a single-row aggregate.\n"
        + "  - NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, EXEC or any DDL/DML.\n"
        + "  - Return ONLY the raw SQL — no explanation, no markdown fences, no commentary.\n"
        + "  - The database is SQL Server (T-SQL dialect). Schema: StarScemaSPARS, dbo.\n"
    )

    # ------------------------------------------------------------------ #
    # Step 2: Call GPT-4.1 for SQL generation                             #
    # ------------------------------------------------------------------ #
    try:
        client = _get_openai_client()
        print(f"[DirectQuery] Calling GPT-4.1 for SQL generation...")
        completion = client.chat.completions.create(
            model="gpt-4.1",
            temperature=0,
            max_tokens=800,
            messages=[
                {"role": "system", "content": sql_gen_system},
                {"role": "user", "content": f"Generate a T-SQL query for: {req.question}"},
            ],
        )
        raw_sql = (completion.choices[0].message.content or "").strip()
        generated_sql = _strip_sql_fences(raw_sql)
        print(f"[DirectQuery] Generated SQL: {generated_sql[:300]}")
    except Exception as e:
        elapsed = int((time.time() - t_start) * 1000)
        print(f"[DirectQuery] LLM error: {e}")
        return DirectQueryResponse(
            question=req.question,
            generated_sql="",
            columns=[],
            rows=[],
            row_count=0,
            elapsed_ms=elapsed,
            error=f"SQL generation failed: {e}",
        )

    # ------------------------------------------------------------------ #
    # Step 3: Safety check — only allow SELECT / WITH                     #
    # ------------------------------------------------------------------ #
    if not _is_safe_select(generated_sql):
        elapsed = int((time.time() - t_start) * 1000)
        print(f"[DirectQuery] Rejected non-SELECT SQL: {generated_sql[:100]}")
        return DirectQueryResponse(
            question=req.question,
            generated_sql=generated_sql,
            columns=[],
            rows=[],
            row_count=0,
            elapsed_ms=elapsed,
            error="Rejected: generated SQL is not a SELECT statement.",
        )

    # ------------------------------------------------------------------ #
    # Step 4: Execute against cached MSSQL connection                     #
    # ------------------------------------------------------------------ #
    try:
        sql_db = _get_sql_db()
        print(f"[DirectQuery] Executing SQL against DB...")
        with sql_db._engine.connect() as conn:
            result = conn.execute(text(generated_sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
        elapsed = int((time.time() - t_start) * 1000)
        print(f"[DirectQuery] Done | rows={len(rows)} | {elapsed}ms")
        return DirectQueryResponse(
            question=req.question,
            generated_sql=generated_sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=elapsed,
            error=None,
        )
    except Exception as e:
        elapsed = int((time.time() - t_start) * 1000)
        print(f"[DirectQuery] DB execution error: {e}")
        return DirectQueryResponse(
            question=req.question,
            generated_sql=generated_sql,
            columns=[],
            rows=[],
            row_count=0,
            elapsed_ms=elapsed,
            error=f"DB execution failed: {e}",
        )
