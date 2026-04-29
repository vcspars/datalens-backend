"""
Comprehensive agent test: diagnostics → 50 business questions → context-awareness.

Usage:
  cd backend && python -m tests.run_full_test --phase diag
  cd backend && python -m tests.run_full_test --phase full
  cd backend && python -m tests.run_full_test --phase context
  cd backend && python -m tests.run_full_test             # all phases
  cd backend && python -m tests.run_full_test --from 20   # resume full from Q20
"""
import json, re, sys, time, argparse
from typing import Any, Optional

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api"
LOGIN_EMAIL = "test@test.com"
LOGIN_PASSWORD = "testtest"

BAD_PHRASES = [
    "values are illustrative", "actual query result was not returned",
    "I don't have access", "I cannot query", "I cannot access the database",
]
FORBIDDEN_PHRASES = [
    "the query returned no results", "query returned no results",
    "query returned", "the query ", " sql query", "sql query ",
    "the sql ", "returned no results",
]


def login() -> str:
    for attempt in range(3):
        try:
            r = requests.post(f"{API}/auth/login",
                              json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
                              timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
            return r.json()["access_token"]
        except requests.exceptions.RequestException:
            if attempt == 2: raise
            time.sleep(2)
    raise RuntimeError("Login failed after retries")


def clear_history(token: str):
    r = requests.delete(f"{API}/chat/history",
                        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        print(f"  [warn] clear_history: {r.status_code}")


def send_chat(token: str, question: str, timeout: int = 600) -> dict:
    start = time.perf_counter()
    try:
        r = requests.post(f"{API}/chat/stream",
                          json={"question": question},
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                          stream=True, timeout=timeout)
    except Exception as e:
        return {"full_response": "", "has_table": False, "table_data": [],
                "table_columns": [], "sql_query": "", "error": str(e),
                "elapsed_sec": time.perf_counter() - start}

    if r.status_code != 200:
        return {"full_response": "", "has_table": False, "table_data": [],
                "table_columns": [], "sql_query": "",
                "error": f"HTTP {r.status_code}", "elapsed_sec": time.perf_counter() - start}

    full_response = ""; has_table = False; table_data = []; table_columns = []
    sql_query = ""; err = ""

    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "): continue
        try:
            p = json.loads(line[6:].strip())
        except json.JSONDecodeError:
            continue
        if p.get("type") == "token":
            full_response += p.get("content", "")
        elif p.get("type") == "done":
            full_response = p.get("full_response", full_response)
            has_table = p.get("has_table", False)
            table_data = p.get("table_data", [])
            table_columns = p.get("table_columns", [])
            sql_query = p.get("sql_query", "") or ""
            break
        elif p.get("type") == "error":
            err = p.get("content", "error"); break

    return {"full_response": full_response, "has_table": has_table,
            "table_data": table_data, "table_columns": table_columns,
            "sql_query": sql_query, "error": err or None,
            "elapsed_sec": time.perf_counter() - start}


def count_md_rows(text: str) -> int:
    if not text: return 0
    lines = [l.strip() for l in text.strip().splitlines() if l.strip().startswith("|") and l.strip().endswith("|")]
    return max(0, len(lines) - 2) if len(lines) > 2 else 0


def evaluate(item: dict, result: dict) -> tuple[bool, list[str]]:
    issues = []
    if result.get("error"):
        issues.append(f"Error: {result['error']}")
        return False, issues

    resp = (result.get("full_response") or "").strip()
    if not resp:
        issues.append("Empty response")

    if any(b in resp.lower() for b in BAD_PHRASES):
        issues.append("Bad phrase (hallucination)")

    for fp in FORBIDDEN_PHRASES:
        if fp.lower() in resp.lower():
            issues.append(f"Forbidden phrase: '{fp}'")
            break

    sql = result.get("sql_query") or ""
    if sql:
        s = sql.upper()
        for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", s):
                issues.append(f"Non-read-only SQL: {kw}")
                break

        # Anti-pattern checks
        if "FACTSALESINVOICE" in s and "FACTSALESDETAIL" in s:
            issues.append("ANTI-PATTERN: Fan-out JOIN FactSalesInvoice + FactSalesDetail")
        if item.get("category") in ("sales", "analytics", "financial", "summary"):
            if "TOTALAMOUNT" in s and "MERCHANDISEAMOUNT" not in s and "FACTSALESINVOICE" in s:
                if not item.get("allow_totalamount"):
                    issues.append("ANTI-PATTERN: Uses TotalAmount instead of MerchandiseAmount for sales")
        if "FACTINVENTORYSNAPSHOT" in s and "DATEKEY" in s:
            issues.append("ANTI-PATTERN: Uses DateKey on FactInventorySnapshot (column doesn't exist)")

    expect_data = item.get("expect_data", True)
    if expect_data:
        has_data = result.get("has_table") or "|" in resp or any(c.isdigit() for c in resp)
        if not has_data:
            issues.append("Expected data but none found")

        min_rows = item.get("min_rows", 0)
        if min_rows > 0:
            actual_rows = len(result.get("table_data") or []) or count_md_rows(resp)
            if actual_rows < min_rows:
                issues.append(f"Expected >= {min_rows} rows, got {actual_rows}")

    if item.get("expect_no_sql") and result.get("sql_query"):
        issues.append("Should not have run SQL")

    if result.get("elapsed_sec", 0) > 300:
        issues.append(f"Too slow: {result['elapsed_sec']:.0f}s")

    if item.get("response_must_contain"):
        for kw in item["response_must_contain"]:
            if kw.lower() not in resp.lower():
                issues.append(f"Missing keyword in response: '{kw}'")

    return len(issues) == 0, issues


# ===== DIAGNOSTIC QUESTIONS =====
DIAGNOSTIC_QUESTIONS = [
    {"id": "D1", "question": "What are the distinct SalesType values in FactSalesInvoice? Show me count per value.",
     "expect_data": True, "purpose": "Check SalesType values"},
    {"id": "D2", "question": "What years of data do we have? Show count of invoices per year from FactSalesInvoice.",
     "expect_data": True, "purpose": "Check year range"},
    {"id": "D3", "question": "What is the total sales of 2025 of each quarter?",
     "expect_data": True, "min_rows": 1, "purpose": "The exact failing question"},
    {"id": "D4", "question": "Show me the distinct SalesType values in FactSalesDetail with count per value.",
     "expect_data": True, "purpose": "Check SalesType in detail table"},
    {"id": "D5", "question": "How many rows are in each fact table? Show table name and row count.",
     "expect_data": True, "purpose": "Data volume overview"},
]

# ===== 50 BUSINESS QUESTIONS =====
BUSINESS_50 = [
    # --- SALES BASICS (1-10) ---
    {"id": 1, "question": "What is the total sales of 2025 of each quarter?",
     "expect_data": True, "min_rows": 1, "category": "sales"},
    {"id": 2, "question": "What is our total revenue to date?",
     "expect_data": True, "category": "sales"},
    {"id": 3, "question": "Who are our top 10 customers by revenue?",
     "expect_data": True, "min_rows": 5, "category": "sales"},
    {"id": 4, "question": "Show me sales by month for 2025.",
     "expect_data": True, "min_rows": 1, "category": "sales"},
    {"id": 5, "question": "Which products have the highest sales amount this year?",
     "expect_data": True, "min_rows": 1, "category": "sales"},
    {"id": 6, "question": "How many customers do we have?",
     "expect_data": True, "category": "sales"},
    {"id": 7, "question": "What is our total profit to date?",
     "expect_data": True, "category": "sales"},
    {"id": 8, "question": "Compare sales in Q1 vs Q4 for 2025.",
     "expect_data": True, "min_rows": 2, "category": "sales"},
    {"id": 9, "question": "What is the total number of sales invoices?",
     "expect_data": True, "category": "sales"},
    {"id": 10, "question": "Show me top 5 products by quantity sold.",
     "expect_data": True, "min_rows": 5, "category": "sales"},

    # --- REGIONAL / WAREHOUSE (11-15) ---
    {"id": 11, "question": "Which warehouses or branches have the highest sales?",
     "expect_data": True, "min_rows": 1, "category": "warehouse"},
    {"id": 12, "question": "Show me total sales by year for the last 3 years.",
     "expect_data": True, "min_rows": 1, "category": "sales"},
    {"id": 13, "question": "How many customers in each region?",
     "expect_data": True, "min_rows": 1, "category": "customer"},
    {"id": 14, "question": "Sales by branch or warehouse for 2025.",
     "expect_data": True, "min_rows": 1, "category": "warehouse"},
    {"id": 15, "question": "List all product categories and their total sales amount.",
     "expect_data": True, "min_rows": 1, "category": "product"},

    # --- PURCHASE (16-20) ---
    {"id": 16, "question": "How many purchase orders do we have?",
     "expect_data": True, "category": "purchase"},
    {"id": 17, "question": "Which vendors do we order from most by purchase amount? Top 10.",
     "expect_data": True, "min_rows": 5, "category": "purchase"},
    {"id": 18, "question": "Purchase orders count by status.",
     "expect_data": True, "min_rows": 1, "category": "purchase"},
    {"id": 19, "question": "Top 5 vendors by total purchase amount.",
     "expect_data": True, "min_rows": 5, "category": "purchase"},
    {"id": 20, "question": "How many purchase orders were placed in 2025?",
     "expect_data": True, "category": "purchase"},

    # --- INVENTORY (21-25) ---
    {"id": 21, "question": "Show me current inventory quantity by warehouse for top 10 products.",
     "expect_data": True, "min_rows": 1, "category": "inventory"},
    {"id": 22, "question": "How many products are discontinued?",
     "expect_data": True, "category": "product"},
    {"id": 23, "question": "What is our total inventory value right now?",
     "expect_data": True, "category": "inventory"},
    {"id": 24, "question": "Which products have the most stock on hand?",
     "expect_data": True, "min_rows": 1, "category": "inventory"},
    {"id": 25, "question": "How many products are below reorder level?",
     "expect_data": True, "category": "inventory"},

    # --- FINANCIAL (26-30) ---
    {"id": 26, "question": "What is total tax collected this year?",
     "expect_data": True, "category": "financial"},
    {"id": 27, "question": "Total shipping charges by year.",
     "expect_data": True, "min_rows": 1, "category": "financial"},
    {"id": 28, "question": "What is total discount given by month in 2025?",
     "expect_data": True, "min_rows": 1, "category": "financial"},
    {"id": 29, "question": "What is total merchandise revenue vs services revenue?",
     "expect_data": True, "category": "financial"},
    {"id": 30, "question": "Sales total by payment term.",
     "expect_data": True, "min_rows": 1, "category": "financial"},

    # --- VENDOR / PAYMENT (31-35) ---
    {"id": 31, "question": "How many vendors do we have?",
     "expect_data": True, "category": "vendor"},
    {"id": 32, "question": "What is total amount paid to vendors this year?",
     "expect_data": True, "category": "vendor"},
    {"id": 33, "question": "Which customers have the largest pending payment balances?",
     "expect_data": True, "min_rows": 1, "category": "payment"},
    {"id": 34, "question": "Show me total customer payments received by month for 2025.",
     "expect_data": True, "min_rows": 1, "category": "payment"},
    {"id": 35, "question": "Top 10 products by profit.",
     "expect_data": True, "min_rows": 5, "category": "product"},

    # --- RETURNS / CREDIT (36-40) ---
    {"id": 36, "question": "How many customer returns do we have in total?",
     "expect_data": True, "category": "returns"},
    {"id": 37, "question": "What is the total value of customer returns by year?",
     "expect_data": True, "min_rows": 1, "category": "returns"},
    {"id": 38, "question": "Which products are returned most frequently?",
     "expect_data": True, "min_rows": 1, "category": "returns"},
    {"id": 39, "question": "How many credit memos have been issued? Show by year.",
     "expect_data": True, "min_rows": 1, "category": "returns"},
    {"id": 40, "question": "Total vendor return amount by vendor. Top 10.",
     "expect_data": True, "min_rows": 1, "category": "returns"},

    # --- ADVANCED ANALYTICS (41-45) ---
    {"id": 41, "question": "Year-over-year revenue comparison: 2024 vs 2025.",
     "expect_data": True, "min_rows": 1, "category": "analytics"},
    {"id": 42, "question": "Which month had the highest sales in 2025?",
     "expect_data": True, "category": "analytics"},
    {"id": 43, "question": "Compare profit by quarter in 2025.",
     "expect_data": True, "min_rows": 1, "category": "analytics"},
    {"id": 44, "question": "What is the average order value this year?",
     "expect_data": True, "category": "analytics"},
    {"id": 45, "question": "Show me top 20 customers by revenue with their total sales amount.",
     "expect_data": True, "min_rows": 15, "category": "analytics"},

    # --- SUMMARY / MIXED (46-48) ---
    {"id": 46, "question": "Give me a summary: total revenue, total profit, customer count, and invoice count for 2025.",
     "expect_data": True, "category": "summary"},
    {"id": 47, "question": "How many invoices were created each month in 2025?",
     "expect_data": True, "min_rows": 1, "category": "sales"},
    {"id": 48, "question": "Customer count by country.",
     "expect_data": True, "min_rows": 1, "category": "customer"},

    # --- NON-SQL (49-50) ---
    {"id": 49, "question": "Hi",
     "expect_data": False, "expect_no_sql": True, "category": "greeting"},
    {"id": 50, "question": "Thanks, that helps.",
     "expect_data": False, "expect_no_sql": True, "category": "greeting"},
]

# ===== CONTEXT-AWARENESS SEQUENCES =====
CONTEXT_SEQUENCES = [
    {
        "id": "CTX1",
        "name": "Sales → break down by month",
        "steps": [
            {"question": "What is the total sales amount in 2025?", "expect_data": True},
            {"question": "Break it down by month.", "expect_data": True, "min_rows": 1,
             "response_must_contain": []},
        ]
    },
    {
        "id": "CTX2",
        "name": "Top customers → show their trend",
        "steps": [
            {"question": "Who are the top 5 customers by revenue?", "expect_data": True, "min_rows": 5},
            {"question": "Show me their year-over-year trend.", "expect_data": True, "min_rows": 1},
        ]
    },
    {
        "id": "CTX3",
        "name": "Total invoices → which year had the most",
        "steps": [
            {"question": "How many total invoices do we have?", "expect_data": True},
            {"question": "Which year had the most?", "expect_data": True},
        ]
    },
    {
        "id": "CTX4",
        "name": "Inventory → which warehouse has the most",
        "steps": [
            {"question": "What is our total inventory value?", "expect_data": True},
            {"question": "Which warehouse has the most?", "expect_data": True},
        ]
    },
    {
        "id": "CTX5",
        "name": "Vendor returns → compare to previous year",
        "steps": [
            {"question": "What is the total vendor returns amount this year?", "expect_data": True},
            {"question": "How does that compare to last year?", "expect_data": True},
        ]
    },
]


def run_diagnostic(token: str, verbose: bool = False) -> list[dict]:
    print("\n" + "=" * 70)
    print("PHASE 1: DIAGNOSTIC (checking data shape)")
    print("=" * 70)
    clear_history(token)
    results = []
    for item in DIAGNOSTIC_QUESTIONS:
        print(f"\n[{item['id']}] {item['question'][:80]}")
        print(f"  Purpose: {item.get('purpose', '')}")
        res = send_chat(token, item["question"])
        ok, issues = evaluate(item, res)
        rec = {
            "id": item["id"], "question": item["question"],
            "passed": ok, "issues": issues,
            "elapsed_sec": round(res.get("elapsed_sec", 0), 1),
            "sql_query": res.get("sql_query", ""),
            "response_preview": (res.get("full_response") or "")[:500],
            "table_data_rows": len(res.get("table_data") or []),
        }
        results.append(rec)
        status = "PASS" if ok else "FAIL"
        print(f"  {status} | {rec['elapsed_sec']}s | rows={rec['table_data_rows']}")
        if issues:
            print(f"  Issues: {'; '.join(issues)}")
        if verbose:
            print(f"  SQL: {rec['sql_query'][:200]}")
            print(f"  Response: {rec['response_preview'][:300]}")
    return results


def run_business_50(token: str, start_from: int = 1, verbose: bool = False) -> list[dict]:
    print("\n" + "=" * 70)
    print("PHASE 2: 50 BUSINESS QUESTIONS")
    print("=" * 70)
    if start_from <= 1:
        clear_history(token)

    results = []
    questions = [q for q in BUSINESS_50 if q["id"] >= start_from]
    passed = 0; failed = 0

    for item in questions:
        print(f"\n[{item['id']}/50] {item['question'][:65]}")
        res = send_chat(token, item["question"])
        ok, issues = evaluate(item, res)
        rec = {
            "id": item["id"], "question": item["question"],
            "category": item.get("category", ""),
            "passed": ok, "issues": issues,
            "elapsed_sec": round(res.get("elapsed_sec", 0), 1),
            "sql_query": res.get("sql_query", ""),
            "response_preview": (res.get("full_response") or "")[:400],
            "table_data_rows": len(res.get("table_data") or []),
            "has_table": res.get("has_table", False),
        }
        results.append(rec)
        if ok:
            passed += 1
            print(f"  PASS | {rec['elapsed_sec']}s | rows={rec['table_data_rows']}")
        else:
            failed += 1
            print(f"  FAIL | {rec['elapsed_sec']}s | {'; '.join(issues)}")
        if verbose and not ok:
            print(f"  SQL: {(rec['sql_query'] or 'none')[:200]}")
            print(f"  Resp: {rec['response_preview'][:250]}")

    total_time = sum(r["elapsed_sec"] for r in results)
    print(f"\n--- Business 50 Summary: {passed} passed, {failed} failed | {total_time:.0f}s total ---")
    return results


def run_context_tests(token: str, verbose: bool = False) -> list[dict]:
    print("\n" + "=" * 70)
    print("PHASE 3: CONTEXT-AWARENESS TESTS")
    print("=" * 70)
    results = []

    for seq in CONTEXT_SEQUENCES:
        print(f"\n--- {seq['id']}: {seq['name']} ---")
        clear_history(token)
        seq_results = []
        seq_ok = True

        for i, step in enumerate(seq["steps"]):
            label = "initial" if i == 0 else "follow-up"
            print(f"  [{label}] {step['question'][:60]}")
            res = send_chat(token, step["question"])
            ok, issues = evaluate(step, res)
            seq_results.append({
                "step": i + 1, "question": step["question"],
                "passed": ok, "issues": issues,
                "elapsed_sec": round(res.get("elapsed_sec", 0), 1),
                "sql_query": res.get("sql_query", ""),
                "response_preview": (res.get("full_response") or "")[:400],
                "table_data_rows": len(res.get("table_data") or []),
            })
            if ok:
                print(f"    PASS | {res.get('elapsed_sec', 0):.1f}s")
            else:
                print(f"    FAIL | {'; '.join(issues)}")
                seq_ok = False
            if verbose and not ok:
                print(f"    SQL: {(res.get('sql_query') or '')[:200]}")

        results.append({
            "id": seq["id"], "name": seq["name"],
            "passed": seq_ok, "steps": seq_results,
        })
        print(f"  Sequence result: {'PASS' if seq_ok else 'FAIL'}")

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print(f"\n--- Context Summary: {passed} passed, {failed} failed ---")
    return results


def main():
    parser = argparse.ArgumentParser(description="Full agent test suite")
    parser.add_argument("--phase", choices=["diag", "full", "context", "all"], default="all")
    parser.add_argument("--from", dest="start_from", type=int, default=1)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", dest="output_json", default="test_results.json")
    parser.add_argument("--url", default=BASE_URL)
    args = parser.parse_args()

    global API
    API = f"{args.url.rstrip('/')}/api"

    print(f"Agent Test Suite | URL={args.url} | phase={args.phase}")
    token = login()
    print("Logged in successfully.\n")

    all_results = {}

    if args.phase in ("diag", "all"):
        diag = run_diagnostic(token, args.verbose)
        all_results["diagnostic"] = diag

    if args.phase in ("full", "all"):
        biz = run_business_50(token, args.start_from, args.verbose)
        all_results["business_50"] = biz

    if args.phase in ("context", "all"):
        ctx = run_context_tests(token, args.verbose)
        all_results["context"] = ctx

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    total_p = 0; total_f = 0
    if "diagnostic" in all_results:
        dp = sum(1 for r in all_results["diagnostic"] if r["passed"])
        df = len(all_results["diagnostic"]) - dp
        total_p += dp; total_f += df
        print(f"  Diagnostic:  {dp} passed, {df} failed")
    if "business_50" in all_results:
        bp = sum(1 for r in all_results["business_50"] if r["passed"])
        bf = len(all_results["business_50"]) - bp
        total_p += bp; total_f += bf
        print(f"  Business 50: {bp} passed, {bf} failed")
    if "context" in all_results:
        cp = sum(1 for r in all_results["context"] if r["passed"])
        cf = len(all_results["context"]) - cp
        total_p += cp; total_f += cf
        print(f"  Context:     {cp} passed, {cf} failed")
    print(f"  TOTAL:       {total_p} passed, {total_f} failed")

    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nDetailed results saved to {args.output_json}")


if __name__ == "__main__":
    main()
