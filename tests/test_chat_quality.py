"""
Agentic Q/A test suite for the chat-with-database flow.

- All questions are read-only (SELECT only); no write/update/delete.
- Tests easy, complex, and super-complex questions.
- Ensures responses never contain technical phrases: "query", "sql", "returned no results", etc.

Run against a live server (e.g. http://localhost:8000). Uses test@test.com / testtest.

Usage:
  cd backend && python -m tests.test_chat_quality
  python tests/test_chat_quality.py [--verbose] [base_url]

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

# Phrases that indicate hallucination or failure (plain substring, case-insensitive)
BAD_PHRASES = [
    "values are illustrative",
    "actual query result was not returned",
    "I don't have access",
    "I cannot query",
    "I cannot access the database",
    "as an AI I cannot",
]

# Phrases that must NOT appear in user-facing response (credibility: no technical jargon)
FORBIDDEN_RESPONSE_PHRASES = [
    "the query returned no results",
    "query returned no results",
    "query returned",
    "the query ",
    " sql query",
    "sql query ",
    "the sql ",
    "returned no results",
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


def send_chat(token: str, question: str, stream_timeout: int = 300) -> dict[str, Any]:
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
        timeout=stream_timeout,
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


def has_forbidden_response_phrases(text: str) -> tuple[bool, str]:
    """
    True if response contains any forbidden technical phrase (query, sql, returned no results).
    Returns (True, phrase_found) if forbidden, (False, "") if clean.
    """
    lower = (text or "").lower()
    for phrase in FORBIDDEN_RESPONSE_PHRASES:
        if phrase.lower() in lower:
            return True, phrase
    return False, ""


def is_read_only_sql(sql: str) -> bool:
    """True if SQL looks like SELECT only (no INSERT/UPDATE/DELETE/DROP etc.)."""
    if not sql or not sql.strip():
        return True
    s = sql.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "EXECUTE"]
    for w in forbidden:
        if re.search(r"\b" + re.escape(w) + r"\b", s):
            return False
    return True


def count_table_rows(result: dict) -> int:
    """Number of data rows in the first table returned."""
    data = result.get("table_data") or []
    if isinstance(data, list):
        return len(data)
    return 0


def count_markdown_table_rows(text: str) -> int:
    """Count data rows in the first markdown table."""
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
    if len(table_lines) <= 2:
        return 0
    return len(table_lines) - 2


def assert_no_forbidden_phrases(result: dict) -> tuple[bool, str]:
    """Check full_response for forbidden phrases. Return (True, '') or (False, reason)."""
    text = result.get("full_response") or ""
    found, phrase = has_forbidden_response_phrases(text)
    if found:
        return False, f"Response contains forbidden phrase: '{phrase}'"
    return True, ""


def assert_read_only_sql(result: dict) -> tuple[bool, str]:
    """If sql_query is present, ensure it is read-only."""
    sql = result.get("sql_query") or ""
    if not sql.strip():
        return True, ""
    if not is_read_only_sql(sql):
        return False, "Captured SQL is not read-only"
    return True, ""


# ---------------------------------------------------------------------------
# Test scenarios — EASY (single fact, simple SELECT)
# ---------------------------------------------------------------------------

def test_easy_how_many_tables(token: str) -> tuple[bool, str, dict]:
    """Easy: How many tables? Expect number or table, no forbidden phrases, read-only."""
    clear_history(token)
    result = send_chat(token, "How many tables are in the database?")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    if has_bad_phrases(result["full_response"]):
        return False, f"Bad phrase in response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    has_number = any(c.isdigit() for c in result["full_response"])
    has_table = result["has_table"] or "|" in result["full_response"]
    if not (has_number or has_table):
        return False, "No number and no table", result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_easy_list_tables(token: str) -> tuple[bool, str, dict]:
    """Easy: List all table names. No 'query'/'sql' in response."""
    clear_history(token)
    result = send_chat(token, "List all table names in the database.")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    if has_bad_phrases(result["full_response"]):
        return False, "Bad phrase", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    lower = result["full_response"].lower()
    if "if you want" in lower and "more" in lower and "i can" in lower:
        return False, "Incomplete answer (offered to show more)", result
    rows = count_table_rows(result) or count_markdown_table_rows(result["full_response"])
    if rows < 1:
        return False, "No table rows", result
    return True, f"OK ({rows} rows, {result['elapsed_sec']:.1f}s)", result


def test_easy_top_customers(token: str) -> tuple[bool, str, dict]:
    """Easy: Top 10 customers by revenue. Read-only, no forbidden phrases."""
    clear_history(token)
    result = send_chat(token, "Who are the top 10 customers by revenue?")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    if has_bad_phrases(result["full_response"]):
        return False, "Bad phrase", result
    has_data = result["has_table"] or "|" in result["full_response"] or any(c.isdigit() for c in result["full_response"])
    if not has_data:
        return False, "No data in response", result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_easy_quarter_sales(token: str) -> tuple[bool, str, dict]:
    """Easy: Total sales by quarter for 2025."""
    clear_history(token)
    result = send_chat(token, "What is the total sales of each quarter in 2025?")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    has_data = "2025" in result["full_response"] and ("|" in result["full_response"] or any(c.isdigit() for c in result["full_response"]))
    if not has_data:
        return False, "No 2025 quarter data", result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_easy_greeting(token: str) -> tuple[bool, str, dict]:
    """Easy: Hi -> friendly reply, no SQL."""
    clear_history(token)
    result = send_chat(token, "Hi")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    if result["sql_query"]:
        return False, "Greeting should not run SQL", result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_easy_thanks(token: str) -> tuple[bool, str, dict]:
    """Easy: Thanks -> no SQL."""
    clear_history(token)
    result = send_chat(token, "Thanks!")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    if result["sql_query"]:
        return False, "Thanks should not run SQL", result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


# ---------------------------------------------------------------------------
# Test scenarios — COMPLEX (multi-table, aggregation, filters)
# ---------------------------------------------------------------------------

def test_complex_region_comparison(token: str) -> tuple[bool, str, dict]:
    """Complex: Compare NORTHEAST vs WESTERN sales over 2 years. May return empty if no such regions."""
    clear_history(token)
    result = send_chat(token, "Compare sales performance in NORTHEAST vs WESTERN regions over the past 2 years by month.")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    # Accept either data or a clear "no data" message (no "query returned" etc.)
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_complex_declining_products(token: str) -> tuple[bool, str, dict]:
    """Complex: Products with consistent decline 3+ consecutive months."""
    clear_history(token)
    result = send_chat(token, "Which products have shown a consistent decline in sales for more than 3 consecutive months?")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


def test_complex_break_down_by_month(token: str) -> tuple[bool, str, dict]:
    """Complex: Follow-up — break total sales down by month."""
    clear_history(token)
    r1 = send_chat(token, "What is the total sales amount in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}", r1
    r2 = send_chat(token, "break it down by month")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}", r2
    if not r2["full_response"].strip():
        return False, "Empty follow-up", r2
    ok, msg = assert_no_forbidden_phrases(r2)
    if not ok:
        return False, msg, r2
    has_table_or_data = r2["has_table"] or "|" in r2["full_response"] or any(c.isdigit() for c in r2["full_response"])
    substantive = len(r2["full_response"].strip()) > 40
    if not (has_table_or_data or substantive):
        return False, "No breakdown data or substantive answer", r2
    return True, f"OK ({r2['elapsed_sec']:.1f}s)", r2


# ---------------------------------------------------------------------------
# Test scenarios — SUPER COMPLEX (CTEs, multi-step, context-heavy)
# ---------------------------------------------------------------------------

def test_super_followup_yes_after_tables(token: str) -> tuple[bool, str, dict]:
    """Super: How many tables? -> yes. Expect full list, no forbidden phrases."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}", r1
    r2 = send_chat(token, "yes")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}", r2
    if not r2["full_response"].strip():
        return False, "Follow-up empty", r2
    if has_bad_phrases(r2["full_response"]):
        return False, "Follow-up bad phrase", r2
    ok, msg = assert_no_forbidden_phrases(r2)
    if not ok:
        return False, msg, r2
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, "Follow-up did not return table/list data", r2
    return True, f"OK ({r2['elapsed_sec']:.1f}s)", r2


def test_super_three_turn_context(token: str) -> tuple[bool, str, dict]:
    """Super: Tables count -> What are their names? -> context preserved."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"Turn 1 error: {r1['error']}", r1
    r2 = send_chat(token, "What are their names?")
    if r2["error"]:
        return False, f"Turn 2 error: {r2['error']}", r2
    if not r2["full_response"].strip():
        return False, "Turn 2 empty", r2
    ok, msg = assert_no_forbidden_phrases(r2)
    if not ok:
        return False, msg, r2
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, "Turn 2 did not return table names", r2
    return True, f"OK ({r2['elapsed_sec']:.1f}s)", r2


def test_super_clarification(token: str) -> tuple[bool, str, dict]:
    """Super: Data question then 'what does that column mean?' — simple reply, no SQL jargon."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}", r1
    r2 = send_chat(token, "what does that column mean?")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}", r2
    if not r2["full_response"].strip():
        return False, "Empty follow-up", r2
    ok, msg = assert_no_forbidden_phrases(r2)
    if not ok:
        return False, msg, r2
    return True, f"OK ({r2['elapsed_sec']:.1f}s)", r2


def test_super_show_me_all(token: str) -> tuple[bool, str, dict]:
    """Super: How many tables -> show me all. Full list, no forbidden phrases."""
    clear_history(token)
    r1 = send_chat(token, "How many tables are in the database?")
    if r1["error"]:
        return False, f"First error: {r1['error']}", r1
    r2 = send_chat(token, "show me all")
    if r2["error"]:
        return False, f"Follow-up error: {r2['error']}", r2
    if not r2["full_response"].strip():
        return False, "Empty follow-up", r2
    ok, msg = assert_no_forbidden_phrases(r2)
    if not ok:
        return False, msg, r2
    has_data = r2["has_table"] or count_table_rows(r2) > 0 or "|" in r2["full_response"]
    if not has_data:
        return False, "Follow-up did not return table data", r2
    return True, f"OK ({r2['elapsed_sec']:.1f}s)", r2


def test_empty_result_no_forbidden_phrases(token: str) -> tuple[bool, str, dict]:
    """When result is empty, response must not contain 'query', 'sql', 'returned no results'."""
    clear_history(token)
    # Ask for data that likely doesn't exist (sales in year 1990 or impossible filter)
    result = send_chat(token, "Show me total sales for the year 1990.")
    if result["error"]:
        return False, f"Error: {result['error']}", result
    if not result["full_response"].strip():
        return False, "Empty response", result
    ok, msg = assert_no_forbidden_phrases(result)
    if not ok:
        return False, msg, result
    ok, msg = assert_read_only_sql(result)
    if not ok:
        return False, msg, result
    return True, f"OK ({result['elapsed_sec']:.1f}s)", result


# ---------------------------------------------------------------------------
# Runner: run all, evaluate (time, SQL, response, forbidden phrases)
# ---------------------------------------------------------------------------

def run_all(base_url: str = BASE_URL, verbose: bool = False) -> bool:
    global API
    API = f"{base_url.rstrip('/')}/api"
    print(f"Chat Q/A tests | BASE_URL={base_url} | verbose={verbose}")
    print("Login...")
    try:
        token = login()
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    print("Clearing history...")
    try:
        clear_history(token)
    except Exception as e:
        print(f"FAIL: {e}")
        return False

    cases = [
        ("EASY: How many tables", test_easy_how_many_tables),
        ("EASY: List all tables", test_easy_list_tables),
        ("EASY: Top 10 customers by revenue", test_easy_top_customers),
        ("EASY: Quarter sales 2025", test_easy_quarter_sales),
        ("EASY: Greeting (Hi)", test_easy_greeting),
        ("EASY: Thanks", test_easy_thanks),
        ("COMPLEX: Region comparison NORTHEAST vs WESTERN", test_complex_region_comparison),
        ("COMPLEX: Products declining 3+ months", test_complex_declining_products),
        ("COMPLEX: Break down by month (follow-up)", test_complex_break_down_by_month),
        ("SUPER: Follow-up 'yes' after tables", test_super_followup_yes_after_tables),
        ("SUPER: 3-turn context (tables -> names)", test_super_three_turn_context),
        ("SUPER: Clarification (what does column mean)", test_super_clarification),
        ("SUPER: Show me all (follow-up)", test_super_show_me_all),
        ("EMPTY RESULT: No forbidden phrases (e.g. 1990 sales)", test_empty_result_no_forbidden_phrases),
    ]

    passed = 0
    failed = 0
    results_log = []

    for name, fn in cases:
        print(f"\n--- {name} ---")
        try:
            ok, msg, res = fn(token)
            elapsed = res.get("elapsed_sec", 0)
            sql_len = len(res.get("sql_query") or "")
            resp_len = len(res.get("full_response") or "")
            results_log.append({
                "name": name,
                "ok": ok,
                "msg": msg,
                "elapsed_sec": elapsed,
                "sql_len": sql_len,
                "resp_len": resp_len,
            })
            if ok:
                print(f"PASS: {msg} | time={elapsed:.1f}s sql_len={sql_len} resp_len={resp_len}")
                passed += 1
            else:
                print(f"FAIL: {msg} | time={elapsed:.1f}s")
                if verbose and res.get("full_response"):
                    print(f"  response preview: {res['full_response'][:300]}...")
                failed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            results_log.append({"name": name, "ok": False, "msg": str(e)})
            failed += 1

    print("\n" + "=" * 60)
    print(f"Result: {passed} passed, {failed} failed")
    if results_log:
        total_time = sum(r.get("elapsed_sec", 0) for r in results_log)
        print(f"Total time: {total_time:.1f}s")
    if failed > 0:
        return False
    return True


# ---------------------------------------------------------------------------
# 50 management/client questions — SQL quality, response quality, time, context
# Schema reference: db_knowledge.py; optional verification: backend/db_resources/
#   Technical_Documentation_of_Database_For_DataLens_ Version 0.1 (1).docx
# ---------------------------------------------------------------------------

# Questions top management or clients might ask (all read-only). expect_sql=True for data questions.
MANAGEMENT_50_QUESTIONS = [
    {"id": 1, "question": "How many tables are in the database?", "expect_sql": True},
    {"id": 2, "question": "What is our total revenue to date?", "expect_sql": True},
    {"id": 3, "question": "Who are our top 10 customers by revenue?", "expect_sql": True},
    {"id": 4, "question": "What are total sales by quarter for 2025?", "expect_sql": True},
    {"id": 5, "question": "Show me sales by month for last year.", "expect_sql": True},
    {"id": 6, "question": "Which products have the highest sales amount this year?", "expect_sql": True},
    {"id": 7, "question": "How many customers do we have?", "expect_sql": True},
    {"id": 8, "question": "What is our total profit to date?", "expect_sql": True},
    {"id": 9, "question": "How many vendors do we have?", "expect_sql": True},
    {"id": 10, "question": "What is the total number of invoices?", "expect_sql": True},
    {"id": 11, "question": "Compare sales in Q1 vs Q4 for 2025.", "expect_sql": True},
    {"id": 12, "question": "Which regions have the most sales? Show top 10.", "expect_sql": True},
    {"id": 13, "question": "List all product categories and their total sales amount.", "expect_sql": True},
    {"id": 14, "question": "What is the average order value this year?", "expect_sql": True},
    {"id": 15, "question": "How many purchase orders do we have?", "expect_sql": True},
    {"id": 16, "question": "Show me top 5 products by quantity sold.", "expect_sql": True},
    {"id": 17, "question": "What is total sales by customer type?", "expect_sql": True},
    {"id": 18, "question": "Which warehouses or branches have the highest sales?", "expect_sql": True},
    {"id": 19, "question": "Show me total sales by year for the last 3 years.", "expect_sql": True},
    {"id": 20, "question": "Which customers have the most invoices? Top 10.", "expect_sql": True},
    {"id": 21, "question": "What is total discount given by month in 2025?", "expect_sql": True},
    {"id": 22, "question": "Which vendors do we order from most by purchase amount? Top 10.", "expect_sql": True},
    {"id": 23, "question": "Show me current inventory quantity by warehouse for top 10 products.", "expect_sql": True},
    {"id": 24, "question": "What is total tax collected this year?", "expect_sql": True},
    {"id": 25, "question": "How many sales invoices in 2024 vs 2025?", "expect_sql": True},
    {"id": 26, "question": "Top 10 products by profit.", "expect_sql": True},
    {"id": 27, "question": "Sales total by payment term.", "expect_sql": True},
    {"id": 28, "question": "How many products are discontinued?", "expect_sql": True},
    {"id": 29, "question": "Total shipping charges by year.", "expect_sql": True},
    {"id": 30, "question": "How many customers in each region?", "expect_sql": True},
    {"id": 31, "question": "Purchase orders count by status.", "expect_sql": True},
    {"id": 32, "question": "Sales by branch or warehouse for 2025.", "expect_sql": True},
    {"id": 33, "question": "What is total merchandise revenue vs services revenue?", "expect_sql": True},
    {"id": 34, "question": "Top 5 vendors by total purchase amount.", "expect_sql": True},
    {"id": 35, "question": "Invoices count by month for 2025.", "expect_sql": True},
    {"id": 36, "question": "Which month had the highest sales in 2025?", "expect_sql": True},
    {"id": 37, "question": "Customer count by country.", "expect_sql": True},
    {"id": 38, "question": "Total quantity sold by product category for 2025.", "expect_sql": True},
    {"id": 39, "question": "Compare profit by quarter in 2025.", "expect_sql": True},
    {"id": 40, "question": "Top customers by number of orders in 2025.", "expect_sql": True},
    {"id": 41, "question": "Revenue by product category for 2025.", "expect_sql": True},
    {"id": 42, "question": "What is our best-selling product this year by quantity?", "expect_sql": True},
    {"id": 43, "question": "List regions and their total sales amount.", "expect_sql": True},
    {"id": 44, "question": "Year-over-year revenue comparison: 2024 vs 2025.", "expect_sql": True},
    {"id": 45, "question": "Give me a summary: total revenue, total profit, customer count, and invoice count for 2025.", "expect_sql": True},
    {"id": 46, "question": "Hi", "expect_sql": False},
    {"id": 47, "question": "Thanks, that helps.", "expect_sql": False},
    {"id": 48, "question": "What can you tell me about our sales data?", "expect_sql": False},
    {"id": 49, "question": "List all table names in the database.", "expect_sql": True},
    {"id": 50, "question": "Show me top 20 customers by revenue with their total sales amount.", "expect_sql": True},
]

# Known tables from db_knowledge / Technical Documentation (for SQL sanity check)
KNOWN_TABLES = {
    "DimCustomer", "DimDate", "DimProduct", "DimVendors", "DimWarehouse", "DimInvoiceAddresses",
    "FactSalesInvoice", "FactSalesDetail", "FactPurchaseOrder", "FactPurchaseDetail",
    "FactInventorySnapshot", "FactCreditMemo", "FactCreditMemoDetail", "FactCustomerApplication",
    "FactCustomerPayment", "FactCustomerReturn", "FactCustomerReturnDetail", "FactVendorInvoice",
    "FactVendorInvoiceDetail", "FactVendorPayment",
}


def _sql_uses_known_tables(sql: str) -> tuple[bool, list[str]]:
    """Optional: check SQL uses known schema tables. Currently permissive (any SELECT allowed)."""
    if not sql or not sql.strip():
        return True, []
    return True, []


def evaluate_single_result(item: dict, result: dict) -> tuple[bool, list[str], dict]:
    """
    Evaluate one Q/A result. Returns (passed, list of issues, score_dict).
    score_dict: sql_read_only, sql_quality, response_quality, time_ok, no_forbidden, substantive.
    """
    issues = []
    score = {
        "sql_read_only": True,
        "sql_quality": True,
        "response_quality": True,
        "time_ok": True,
        "no_forbidden": True,
        "substantive": True,
        "elapsed_sec": result.get("elapsed_sec", 0),
        "sql_len": len(result.get("sql_query") or ""),
        "resp_len": len(result.get("full_response") or ""),
    }

    if result.get("error"):
        issues.append(f"Error: {result['error']}")
        return False, issues, score

    resp = (result.get("full_response") or "").strip()
    if not resp:
        issues.append("Empty response")
        score["response_quality"] = False
        score["substantive"] = False

    if has_bad_phrases(resp):
        issues.append("Response contains bad phrase (hallucination)")
        score["response_quality"] = False

    found, phrase = has_forbidden_response_phrases(resp)
    if found:
        issues.append(f"Forbidden phrase in response: '{phrase}'")
        score["no_forbidden"] = False
        score["response_quality"] = False

    sql = result.get("sql_query") or ""
    if sql:
        if not is_read_only_sql(sql):
            issues.append("SQL is not read-only")
            score["sql_read_only"] = False
        score["sql_quality"] = score["sql_read_only"]
    elif item.get("expect_sql"):
        # Data question but no SQL captured (e.g. list_tables tool) — allow; some tools don't emit sql_query
        pass

    if result.get("elapsed_sec", 0) > 120:
        issues.append(f"Slow: {result['elapsed_sec']:.0f}s")
        score["time_ok"] = False

    if item.get("expect_sql") and resp and not result.get("sql_query") and not result.get("has_table"):
        # Allow short numeric answers (e.g. "How many tables" -> "There are 19 tables.")
        if len(resp) < 30 and "|" not in resp and not any(c.isdigit() for c in resp):
            issues.append("Expected data/table but response is very short with no number or table")
            score["substantive"] = False

    passed = len(issues) == 0
    return passed, issues, score


def run_management_50(base_url: str = BASE_URL, verbose: bool = False, output_json: str = "", start_from: int = 1) -> bool:
    """Run all 50 management questions; evaluate SQL quality, response quality, time, context. start_from=1 means from first (use 14 to resume from Q14)."""
    global API
    API = f"{base_url.rstrip('/')}/api"
    print("Management 50 Q/A suite | SQL quality, response quality, time, context")
    print("Login...")
    try:
        token = login()
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    if start_from <= 1:
        clear_history(token)

    results = []
    passed = 0
    failed = 0
    total_time = 0.0
    questions_to_run = [it for it in MANAGEMENT_50_QUESTIONS if it["id"] >= start_from]
    if not questions_to_run:
        print("No questions to run (start_from too high).")
        return True

    for i, item in enumerate(questions_to_run):
        q = item["question"]
        qid = item["id"]
        print(f"\n[{qid}/50] {q[:55]}{'...' if len(q) > 55 else ''}")
        res = send_chat(token, q, stream_timeout=600)
        total_time += res.get("elapsed_sec", 0)
        ok, issues, score = evaluate_single_result(item, res)
        rec = {
            "id": qid,
            "question": q,
            "passed": ok,
            "issues": issues,
            "elapsed_sec": round(score["elapsed_sec"], 1),
            "sql_len": score["sql_len"],
            "resp_len": score["resp_len"],
            "sql_preview": (res.get("sql_query") or "")[:200],
        }
        results.append(rec)
        if ok:
            passed += 1
            print(f"  PASS {score['elapsed_sec']:.1f}s | sql={score['sql_len']} resp={score['resp_len']}")
        else:
            failed += 1
            print(f"  FAIL {score['elapsed_sec']:.1f}s | {'; '.join(issues)}")
            if verbose and res.get("full_response"):
                print(f"  response: {res['full_response'][:250]}...")

    print("\n" + "=" * 60)
    print(f"Management 50: {passed} passed, {failed} failed | Total time: {total_time:.1f}s")
    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump({"results": results, "passed": passed, "failed": failed, "total_time_sec": round(total_time, 1)}, f, indent=2)
        print(f"Results written to {output_json}")

    return failed == 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    verbose = "--verbose" in argv or "-v" in argv
    management_50 = "--management-50" in argv or "--50" in argv
    output_json = ""
    if "--json" in argv:
        idx = argv.index("--json")
        if idx + 1 < len(argv):
            output_json = argv[idx + 1]
        argv = [a for i, a in enumerate(argv) if i != idx and i != idx + 1]
    start_from = 1
    if "--from" in argv:
        idx = argv.index("--from")
        if idx + 1 < len(argv):
            try:
                start_from = int(argv[idx + 1])
            except ValueError:
                pass
        argv = [a for i, a in enumerate(argv) if i != idx and i != idx + 1]
    argv = [a for a in argv if a not in ("--verbose", "-v", "--management-50", "--50")]
    url = argv[0] if argv else BASE_URL
    if management_50:
        success = run_management_50(url, verbose=verbose, output_json=output_json or "management_50_results.json", start_from=start_from)
    else:
        success = run_all(url, verbose=verbose)
    sys.exit(0 if success else 1)
