# Chat Q/A Test Suite

Agentic tests for the chat-with-database flow. All questions are **read-only** (SELECT only).

## What is tested

- **Easy**: How many tables, list tables, top customers, quarter sales, greeting, thanks.
- **Complex**: Region comparison (NORTHEAST vs WESTERN), products with 3+ month decline, follow-up “break down by month”.
- **Super complex**: Follow-up “yes” after tables, 3-turn context (tables → names), clarification, “show me all”, empty-result wording.
- **Credibility**: Responses must **not** contain phrases like “query”, “sql”, “returned no results” (user-friendly wording only).
- **Read-only**: Captured SQL is checked to ensure no INSERT/UPDATE/DELETE.

## 50 management/client questions

A separate run mode exercises **50 questions** that top management or clients might ask. It evaluates:

- **SQL generation quality**: read-only, sensible (schema aligns with `db_knowledge.py` / `backend/db_resources/Technical_Documentation_of_Database_For_DataLens_ Version 0.1 (1).docx`).
- **Response quality**: no forbidden phrases, non-empty, substantive.
- **Time**: per-question and total; slow answers (>120s) flagged.
- **Context**: single-turn and optional multi-turn behaviour.

Run the 50-question suite (server must be running):

```bash
cd backend
python -m tests.test_chat_quality --50
# or
python -m tests.test_chat_quality --management-50
```

Options:

- `--json <file>` — write results to JSON (default: `management_50_results.json`).
- `--from <n>` — start from question id `n` (e.g. resume after timeout: `--from 14`).
- `--verbose` / `-v` — extra output on failure.

Example:

```bash
python -m tests.test_chat_quality --50 --json management_50_results.json
```

## Run (standard suite)

From repo root, with server running on port 8000:

```bash
cd backend
python -m tests.test_chat_quality
```

Optional: `--verbose` for more output, or pass base URL:

```bash
python -m tests.test_chat_quality --verbose
python -m tests.test_chat_quality http://localhost:8000
```

## Config

- **Auth**: `test@test.com` / `testtest`
- **Forbidden phrases** (in `test_chat_quality.py`): `BAD_PHRASES`, `FORBIDDEN_RESPONSE_PHRASES`
- **Base URL**: `http://127.0.0.1:8000` (override via argv)

## Backend behavior (aligned with tests)

- **langchain_agent.py**: Prompt tells the LLM to use plain language for empty results (“No data matches that criteria”), and never use “query”/“sql”/“returned no results” in answers. Post-processing replaces any such phrasing via `_sanitize_user_response()`. Status message uses “Searching the database...” instead of “Querying database...”.
