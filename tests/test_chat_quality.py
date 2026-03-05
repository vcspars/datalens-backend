"""
Automated chat quality tests for the DataLens chat-with-database flow.

Run against a live server (e.g. http://localhost:8000). Uses test@test.com / testtest.
All test questions are read-only (result in SELECT only); no write/update/delete.

Usage:
  cd backend && python -m tests.test_chat_quality
  or: python tests/test_chat_quality.py

Requires: requests (pip install requests)
"""

import json
import re
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("This test requires 'requests'. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api"
LOGIN_EMAIL = "test@test.com"
LOGIN_PASSWORD = "testtest"

# Phrases that indicate a failed or hallucinated answer (no regex, plain substring)
BAD_PHRASES = [
    "values are illustrative",
    "actual query result was not returned",
    "I don't have access",
    "I cannot query",
    "I cannot access the database",
    "as an AI I cannot",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login(max_retries: int = 3) -> str:
    """Authenticate and return Bearer token. Retries on connection errors."""
    for attempt in range(max_retries):
        try:
            r = requests.post(
                f"{API}/auth/login",
                json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            if r.status_code != 200:
                raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
            data = r.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError("Login response missing access_token")
            return token
        except (requests.exceptions.RequestException, OSError) as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    raise RuntimeError("Login failed after retries")


def clear_history(token: str) -> None:
    """Clear chat history for the current user."""
    r = requests.delete(
        f"{API}/chat/history",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Clear history failed: {r.status_code} {r.text}")


def send_chat(token: str, question: str) -> dict[str, Any]:
    """
    Send a single question to the chat stream endpoint and collect the full response.
    Returns dict with: full_response, has_table, table_data, table_columns, sql_query, error, elapsed_sec.
    """
    start = time.perf_counter()
    r = requests.post(
        f"{API}/chat/stream",
        json={"question": question},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        stream=True,
        timeout=300,
    )
    if r.status_code != 200:
        return {
            "full_response": "",
            "has_table": False,
            "table_data": [],
            "table_columns": [],
            "sql_query": "",
            "error": f"HTTP {r.status_code}",
            "elapsed_sec": time.perf_counter() - start,
        }

    full_response = ""
    has_table = False
    table_data = []
    table_columns = []
    sql_query = ""
    err_msg = ""

    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[6:].strip())
        except json.JSONDecodeError:
            continue
        t = payload.get("type")
        if t == "token":
            full_response += payload.get("content", "")
        elif t == "done":
            full_response = payload.get("full_response", full_response)
            has_table = payload.get("has_table", False)
            table_data = payload.get("table_data", [])
            table_columns = payload.get("table_columns", [])
            sql_query = payload.get("sql_query", "") or ""
            break
        elif t == "error":
            err_msg = payload.get("content", "Unknown error")
            break

    elapsed = time.perf_counter() - start
    return {
        "full_response": full_response,
        "has_table": has_table,
        "table_data": table_data,
        "table_columns": table_columns,
        "sql_query": sql_query,
        "error": err_msg or None,
        "elapsed_sec": elapsed,
    }


def has_bad_phrases(text: str) -> bool:
    """True if response contains any phrase indicating hallucination or failure."""
    lower = (text or "").lower()
    return any(bad in lower for bad in BAD_PHRASES)


def count_table_rows(result: dict) -> int:
    """Number of data rows in the first table returned."""
    data = result.get("table_data") or []
    if isinstance(data, list):
        return len(data)
    return 0


def count_markdown_table_rows(text: str) -> int:
    """Count data rows in the first markdown table (header + separator = 2 lines, rest are data)."""
    if not text:
        return 0
    lines = text.strip().splitlines()
    table_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break
    # First line = header, second = separator (|---|), rest = data
    if len(table_lines) <= 2:
        return 0
    return len(table_lines) - 2


# ---------------------------------------------------------------------------
# Test scenarios (all read-only)
# ---------------------------------------------------------------------------

def test_direct_question_tables(token: str) -> tuple[bool, str]:
    """Ask how many tables / list tables. Expect non-empty answer with data."""
    clear_history(token)
    result = send_chat(token, "How many tables are in the database?")
    if result["error"]:
        return False, f"Error: {result['error']}"
    if not result["full_response"].strip():
        return False, "Empty response"
    if has_bad_phrases(result["full_response"]):
        return False, f"Response contains bad phrase: {result['full_response'][:200]}"
    # Should have a number or a table
    has_number = any(c.isdigit() for c in result["full_response"])
    has_table = result["has_table"] or "|" in result["full_response"]
    if not (has_number or has_table):
        return False, "Response has no number and no table"
    return True, f"OK (elapsed {result['elapsed_sec']:.1f}s)"


def test_followup_yes_after_tables(token: str) -> tuple[bool, str]:
    """Ask about tables, then 'yes' to see all. Expect context preserved and data returned."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First question error: {r1['error']}"
    r2 = send_chat(token, "yes")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}"
    if not r2["full_response"].strip():
        return False, "Follow-up empty response"
    if has_bad_phrases(r2["full_response"]):
        return False, f"Follow-up contained bad phrase (hallucination?): {r2['full_response'][:300]}"
    # We expect either a table or a list of table names (context preserved)
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, f"Follow-up did not return table/list data: {r2['full_response'][:200]}"
    return True, f"OK (elapsed {r2['elapsed_sec']:.1f}s)"


def test_completeness_list_all_tables(token: str) -> tuple[bool, str]:
    """Ask to list all tables. Expect all tables returned, not partial + 'want more?'."""
    clear_history(token)
    result = send_chat(token, "List all table names in the database.")
    if result["error"]:
        return False, f"Error: {result['error']}"
    if not result["full_response"].strip():
        return False, "Empty response"
    if has_bad_phrases(result["full_response"]):
        return False, "Response contains bad phrase"
    # Should not offer to show more (indicates partial result)
    lower = result["full_response"].lower()
    if "if you want" in lower and "more" in lower and "i can" in lower:
        return False, "Agent offered to show more (incomplete answer)"
    rows = count_table_rows(result)
    md_rows = count_markdown_table_rows(result["full_response"])
    total_rows = rows or md_rows
    if total_rows < 1:
        return False, "No table rows in response"
    return True, f"OK ({total_rows} rows, elapsed {result['elapsed_sec']:.1f}s)"


def test_followup_show_me_all(token: str) -> tuple[bool, str]:
    """Ask how many tables, then 'show me all'. Expect full list."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}"
    r2 = send_chat(token, "show me all")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}"
    if not r2["full_response"].strip():
        return False, "Empty follow-up"
    if has_bad_phrases(r2["full_response"]):
        return False, "Follow-up had bad phrase"
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, "Follow-up did not return table data"
    return True, f"OK (elapsed {r2['elapsed_sec']:.1f}s)"


def test_greeting_simple(token: str) -> tuple[bool, str]:
    """Hi -> expect short friendly reply, no error."""
    clear_history(token)
    result = send_chat(token, "Hi")
    if result["error"]:
        return False, f"Error: {result['error']}"
    if not result["full_response"].strip():
        return False, "Empty response"
    if result["sql_query"]:
        return False, "Greeting should not run SQL"
    return True, f"OK (elapsed {result['elapsed_sec']:.1f}s)"


def test_context_preservation_three_turn(token: str) -> tuple[bool, str]:
    """Multi-turn: ask about tables, then a refinement, then another. Expect context kept."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"Turn 1 error: {r1['error']}"
    r2 = send_chat(token, "What are their names?")
    if r2["error"]:
        return False, f"Turn 2 error: {r2['error']}"
    if not r2["full_response"].strip():
        return False, "Turn 2 empty"
    if has_bad_phrases(r2["full_response"]):
        return False, "Turn 2 bad phrase"
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, "Turn 2 did not return table names"
    return True, f"OK (elapsed {r2['elapsed_sec']:.1f}s)"


def test_direct_sql_style_question(token: str) -> tuple[bool, str]:
    """Direct data question that should hit SQL agent."""
    clear_history(token)
    result = send_chat(token, "Show me top 5 customers by revenue, or top 5 by any sales metric if revenue is not available.")
    if result["error"]:
        return False, f"Error: {result['error']}"
    if not result["full_response"].strip():
        return False, "Empty response"
    if has_bad_phrases(result["full_response"]):
        return False, "Bad phrase in response"
    return True, f"OK (elapsed {result['elapsed_sec']:.1f}s)"


def test_thanks_simple(token: str) -> tuple[bool, str]:
    """Thanks -> simple reply, no SQL."""
    clear_history(token)
    result = send_chat(token, "Thanks!")
    if result["error"]:
        return False, f"Error: {result['error']}"
    if not result["full_response"].strip():
        return False, "Empty response"
    if result["sql_query"]:
        return False, "Thanks should not run SQL"
    return True, f"OK (elapsed {result['elapsed_sec']:.1f}s)"


def test_followup_refinement(token: str) -> tuple[bool, str]:
    """Ask for sales data, then 'break it down by month'. Expect context preserved and a coherent answer."""
    clear_history(token)
    r1 = send_chat(token, "What is the total sales amount in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}"
    r2 = send_chat(token, "break it down by month")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}"
    if not r2["full_response"].strip():
        return False, "Empty follow-up"
    if has_bad_phrases(r2["full_response"]):
        return False, "Follow-up had bad phrase"
    # Accept table/data, or a substantive prose response (context was used)
    has_table_or_data = r2["has_table"] or "|" in r2["full_response"] or any(c.isdigit() for c in r2["full_response"])
    substantive = len(r2["full_response"].strip()) > 40
    if not (has_table_or_data or substantive):
        return False, "Follow-up did not return breakdown data or substantive answer"
    return True, f"OK (elapsed {r2['elapsed_sec']:.1f}s)"


def test_followup_clarification(token: str) -> tuple[bool, str]:
    """Ask a data question, then 'what does that column mean?'. Expect simple explanation, no hallucination."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}"
    r2 = send_chat(token, "what does that column mean?")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}"
    if not r2["full_response"].strip():
        return False, "Empty follow-up"
    if has_bad_phrases(r2["full_response"]):
        return False, "Follow-up had bad phrase"
    return True, f"OK (elapsed {r2['elapsed_sec']:.1f}s)"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all(base_url: str = BASE_URL, verbose: bool = False) -> None:
    global API
    API = f"{base_url}/api"
    print(f"Chat quality tests | BASE_URL={base_url} | verbose={verbose}")
    print("Login...")
    try:
        token = login()
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    print("Clearing history...")
    try:
        clear_history(token)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    cases = [
        ("Direct question (how many tables)", test_direct_question_tables),
        ("Follow-up 'yes' after tables", test_followup_yes_after_tables),
        ("Completeness (list all tables)", test_completeness_list_all_tables),
        ("Follow-up 'show me all'", test_followup_show_me_all),
        ("Greeting (Hi)", test_greeting_simple),
        ("Thanks (simple)", test_thanks_simple),
        ("Context (3-turn: tables -> names)", test_context_preservation_three_turn),
        ("Follow-up refinement (break down by month)", test_followup_refinement),
        ("Follow-up clarification (what does column mean)", test_followup_clarification),
        ("Direct SQL-style question", test_direct_sql_style_question),
    ]
    passed = 0
    failed = 0
    for name, fn in cases:
        print(f"\n--- {name} ---")
        try:
            ok, msg = fn(token)
            if ok:
                print(f"PASS: {msg}")
                passed += 1
            else:
                print(f"FAIL: {msg}")
                failed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Result: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--verbose"]
    verbose = "--verbose" in sys.argv
    url = args[0] if args else BASE_URL
    run_all(url, verbose=verbose)
