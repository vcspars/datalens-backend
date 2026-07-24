"""
Agent Evaluation Harness — Datalens Chat API
============================================
Tests the full pipeline: QuestionResolver → Orchestrator → MCP/SQL agent.

Usage (from backend/):
    python eval_harness.py

Results are written to eval_results.md in the same directory.

Categories tested:
  SIMPLE   — single-fact queries, one tool call expected
  MEDIUM   — multi-dimension queries, potential multi-tool
  HARD     — complex SQL patterns (partition, CTE, financial statements)
  COMPLEX  — follow-up/context chains, ambiguous questions, edge cases
"""

import asyncio
import httpx
import json
import time
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

BASE_URL = "http://localhost:8005/api"
EMAIL = "test@test.com"
PASSWORD = "testtest"
STREAM_TIMEOUT = 180  # seconds per request

# ── Colour helpers (Windows-safe fallback) ──────────────────────────────────
try:
    import colorama; colorama.init()
    GREEN  = "\033[92m"; RED    = "\033[91m"; YELLOW = "\033[93m"
    CYAN   = "\033[96m"; BOLD   = "\033[1m";  RESET  = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class TestCase:
    id: str
    category: str          # SIMPLE / MEDIUM / HARD / COMPLEX
    question: str
    # Expectations — all optional; None means "don't check"
    expect_intent: Optional[str] = "sql"       # "sql" | "simple"
    expect_has_table: Optional[bool] = None    # True / False / None
    expect_keywords: list[str] = field(default_factory=list)   # words that must appear in response
    expect_no_keywords: list[str] = field(default_factory=list) # words that must NOT appear
    prior_question: Optional[str] = None       # if set, ask this first (chain test)
    note: str = ""                             # human-readable hint for the evaluator


@dataclass
class TestResult:
    case: TestCase
    passed: bool
    intent_detected: str = ""
    has_table: bool = False
    table_rows: int = 0
    response_preview: str = ""
    full_response_len: int = 0
    elapsed: float = 0.0
    mcp_tool_used: bool = False        # detected from response metadata
    sql_executed: bool = False
    failure_reason: str = ""
    raw_done_event: dict = field(default_factory=dict)


# ── Test suite ───────────────────────────────────────────────────────────────

TEST_CASES: list[TestCase] = [

    # ── SIMPLE ──────────────────────────────────────────────────────────────
    TestCase(
        id="S01",
        category="SIMPLE",
        question="What are the top 5 customers by total sales?",
        expect_has_table=True,
        expect_keywords=["customer"],
        note="Basic top-N customer query — should hit MCP or SQL in one shot",
    ),
    TestCase(
        id="S02",
        category="SIMPLE",
        question="How many products do we have?",
        expect_has_table=None,   # count may come back as 1-row table or inline prose — both valid
        expect_keywords=[],
        note="Single count — agent may return inline prose or a 1-row table, both are acceptable",
    ),
    TestCase(
        id="S03",
        category="SIMPLE",
        question="Show me the list of warehouses",
        expect_has_table=True,
        note="Simple dimension lookup",
    ),
    TestCase(
        id="S04",
        category="SIMPLE",
        question="Hello, how are you?",
        expect_intent="simple",
        expect_has_table=False,
        note="Greeting — must route to simple chat, NOT sql agent",
    ),
    TestCase(
        id="S05",
        category="SIMPLE",
        question="What is gross profit?",
        expect_intent="simple",
        expect_has_table=False,
        note="Advisory/definition question — must stay simple, no DB call",
    ),

    # ── MEDIUM ──────────────────────────────────────────────────────────────
    TestCase(
        id="M01",
        category="MEDIUM",
        question="Show total sales by month for the current year",
        expect_has_table=True,
        expect_keywords=["month"],
        note="Time-series grouping — should use TOP 40 + GROUP BY month",
    ),
    TestCase(
        id="M02",
        category="MEDIUM",
        question="Who are the top 10 vendors by purchase volume?",
        expect_has_table=True,
        expect_keywords=["vendor"],
        note="Vendor dimension — likely an MCP tool exists for this",
    ),
    TestCase(
        id="M03",
        category="MEDIUM",
        question="Show me overdue accounts with their outstanding balance",
        expect_has_table=True,
        expect_keywords=["balance", "overdue"],
        note="Receivables query — MCP tool likely available",
    ),
    TestCase(
        id="M04",
        category="MEDIUM",
        question="What is the average order value by customer tier?",
        expect_has_table=True,
        expect_keywords=["tier"],
        note="Grouped average — requires GROUP BY + AVG with NULLIF guard",
    ),
    TestCase(
        id="M05",
        category="MEDIUM",
        question="Show revenue year over year comparison",
        expect_has_table=True,
        note="YoY — may use MCP revenue_yoy_comparison tool directly",
    ),

    # ── HARD ────────────────────────────────────────────────────────────────
    TestCase(
        id="H01",
        category="HARD",
        question="Show me the top 5 customers per ABC category by revenue",
        expect_has_table=True,
        expect_keywords=["A", "B", "C"],
        expect_no_keywords=["SELECT TOP", "FROM Fact", "JOIN Dim"],   # SQL code in response, not English words
        note="PARTITION BY + ABC Pareto CTE — complex SQL pattern",
    ),
    TestCase(
        id="H02",
        category="HARD",
        question="Give me the P&L income statement for the current period",
        expect_has_table=True,
        expect_keywords=["Sales", "Gross Profit"],
        expect_no_keywords=["SELECT", "FROM"],
        note="Financial statement LEVEL 1 — must restructure into P&L template",
    ),
    TestCase(
        id="H03",
        category="HARD",
        question="Show the balance sheet grouped by sub group",
        expect_has_table=True,
        expect_keywords=["Total"],
        expect_no_keywords=["SELECT"],
        note="Balance sheet LEVEL 2 — 4-col SQL result must be restructured",
    ),
    TestCase(
        id="H04",
        category="HARD",
        question="Which customers are in the top 20% by revenue?",
        expect_has_table=True,
        note="PERCENT_RANK direction rule — must use <= not >= for top %",
    ),
    TestCase(
        id="H05",
        category="HARD",
        question="Show me gross profit by month with % margin",
        expect_has_table=True,
        expect_keywords=["%", "margin"],
        note="Percentage calc — must use ROUND(100.0 * ... / NULLIF(...))",
    ),

    # ── COMPLEX / CHAIN ─────────────────────────────────────────────────────
    TestCase(
        id="C01",
        category="COMPLEX",
        question="Show me the top 10 customers by total revenue",
        prior_question=None,
        expect_has_table=True,
        note="Chain setup — ask this first, then C02 is a follow-up",
    ),
    TestCase(
        id="C02",
        category="COMPLEX",
        question="Now show the same but only for this year",
        prior_question="Show me the top 10 customers by total revenue",
        expect_has_table=True,
        expect_keywords=["customer"],
        note="Follow-up — resolver must rewrite into self-contained question",
    ),
    TestCase(
        id="C03",
        category="COMPLEX",
        question="What was the total sales last month and how does it compare to the month before?",
        expect_has_table=True,
        note="Multi-period comparison — may need two SQL queries or one CTE",
    ),
    TestCase(
        id="C04",
        category="COMPLEX",
        question="Show me top 3 products per warehouse",
        expect_has_table=True,
        note="TOP-N per group via PARTITION BY WarehouseKey only",
    ),
    TestCase(
        id="C05",
        category="COMPLEX",
        question="Which sales rep has the highest commission rate and how much did they earn this year?",
        expect_has_table=True,
        note="Multi-fact: commission rate + earnings — may need two joins or subquery",
    ),
    TestCase(
        id="C06",
        category="COMPLEX",
        question="asdfghjkl random nonsense 1234",
        expect_has_table=False,
        note="Garbage input — should handle gracefully, no crash",
    ),
    TestCase(
        id="C07",
        category="COMPLEX",
        question="Show me all data",
        expect_has_table=None,        # either a clarification (no table) or a default dataset (table) is acceptable
        expect_keywords=[],           # don't enforce specific words — just check it doesn't crash
        expect_no_keywords=["SELECT TOP", "FROM Fact", "JOIN Dim"],
        note="Extremely vague — agent may ask for clarification OR return a default dataset, both are acceptable; must not crash or leak SQL",
    ),
    TestCase(
        id="C08",
        category="COMPLEX",
        question="Show me inventory value by ABC category",
        expect_has_table=True,
        expect_keywords=["A", "B", "C"],
        note="ABC classification summary — must use 2-stage CTE (classify then aggregate)",
    ),
]


# ── HTTP helpers ─────────────────────────────────────────────────────────────

async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{BASE_URL}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()["access_token"]


async def stream_chat(
    client: httpx.AsyncClient,
    token: str,
    question: str,
) -> tuple[dict, float]:
    """
    Stream one chat request. Returns (done_event_dict, elapsed_seconds).
    done_event carries: has_table, table_data, tables, full_response, sql_query.
    """
    t0 = time.time()
    done_event: dict = {}
    async with client.stream(
        "POST",
        f"{BASE_URL}/chat/stream",
        json={"question": question},
        headers={"Authorization": f"Bearer {token}"},
        timeout=STREAM_TIMEOUT,
    ) as resp:
        if resp.status_code != 200:
            text = await resp.aread()
            return {"type": "error", "content": f"HTTP {resp.status_code}: {text[:200]}"}, time.time() - t0
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "done":
                done_event = evt
                break
            if evt.get("type") == "error":
                done_event = {"type": "error", "content": evt.get("content", "unknown error")}
                break
    return done_event, time.time() - t0


# Cache the last assistant response so chain tests can reference it
_last_done_event: dict = {}


async def stream_chat_for_chain(
    client: httpx.AsyncClient,
    token: str,
    question: str,
    prior_done: dict,
) -> tuple[dict, float]:
    """
    For follow-up chain tests: build a minimal chat_history from the prior
    turn's done event and send it alongside the new question so the
    QuestionResolver can rewrite the follow-up into a self-contained question.

    NOTE: the /chat/stream endpoint does NOT accept chat_history as a body
    parameter — history is loaded from MongoDB per session. So we simply send
    the prior question first (warming the DB session), then immediately send
    the follow-up. The resolver will find the history in MongoDB automatically.
    """
    return await stream_chat(client, token, question)


# ── Assertion helpers ────────────────────────────────────────────────────────

def check_result(case: TestCase, done: dict, elapsed: float) -> TestResult:
    full_response = done.get("full_response", "")
    has_table = bool(done.get("has_table"))
    tables = done.get("tables") or []
    sql_query = done.get("sql_query") or ""
    first_table_rows = len(tables[0]["data"]) if tables and tables[0].get("data") else 0

    failures = []

    if done.get("type") == "error":
        failures.append(f"API returned error: {done.get('content')}")

    if case.expect_has_table is True and not has_table:
        failures.append("Expected a table but got none")
    if case.expect_has_table is False and has_table:
        failures.append("Expected NO table but got one")

    combined_text = (full_response + " " + json.dumps(tables)).lower()
    for kw in case.expect_keywords:
        if kw.lower() not in combined_text:
            failures.append(f"Expected keyword missing: '{kw}'")
    for kw in case.expect_no_keywords:
        if kw.lower() in combined_text:
            failures.append(f"Forbidden keyword present: '{kw}'")

    if not full_response and done.get("type") != "error":
        failures.append("full_response is empty")

    return TestResult(
        case=case,
        passed=len(failures) == 0,
        has_table=has_table,
        table_rows=first_table_rows,
        response_preview=full_response[:200].replace("\n", " "),
        full_response_len=len(full_response),
        elapsed=elapsed,
        sql_executed=bool(sql_query),
        raw_done_event=done,
        failure_reason="; ".join(failures) if failures else "",
    )


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(results: list[TestResult]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    lines = [
        "# Agent Evaluation Report",
        f"**Generated:** {now}  ",
        f"**Total:** {total}  |  **Passed:** {passed}  |  **Failed:** {failed}  ",
        f"**Pass rate:** {100 * passed / total:.1f}%",
        "",
        "---",
        "",
    ]

    categories = ["SIMPLE", "MEDIUM", "HARD", "COMPLEX"]
    for cat in categories:
        cat_results = [r for r in results if r.case.category == cat]
        if not cat_results:
            continue
        cat_pass = sum(1 for r in cat_results if r.passed)
        lines.append(f"## {cat} ({cat_pass}/{len(cat_results)} passed)")
        lines.append("")
        lines.append("| ID | Question | Pass | Time | Table | Rows | SQL | Failure |")
        lines.append("|:---|:---------|:----:|-----:|:-----:|-----:|:---:|:--------|")
        for r in cat_results:
            status = "✓" if r.passed else "✗"
            table_yn = "Y" if r.has_table else "N"
            sql_yn = "Y" if r.sql_executed else "N"
            q_short = r.case.question[:60] + ("…" if len(r.case.question) > 60 else "")
            fail = r.failure_reason[:80] if r.failure_reason else ""
            lines.append(
                f"| {r.case.id} | {q_short} | {status} | {r.elapsed:.1f}s "
                f"| {table_yn} | {r.table_rows} | {sql_yn} | {fail} |"
            )
        lines.append("")

    # Detailed failures section
    failures = [r for r in results if not r.passed]
    if failures:
        lines.append("---")
        lines.append("")
        lines.append("## Failure Details")
        lines.append("")
        for r in failures:
            lines.append(f"### {r.case.id} — {r.case.question}")
            lines.append(f"**Category:** {r.case.category}  ")
            lines.append(f"**Note:** {r.case.note}  ")
            lines.append(f"**Failure:** {r.failure_reason}  ")
            lines.append(f"**Response preview:** {r.response_preview}  ")
            lines.append(f"**Elapsed:** {r.elapsed:.1f}s  ")
            lines.append("")

    # Issues / improvement suggestions
    lines.append("---")
    lines.append("")
    lines.append("## Issues & Suggested Fixes")
    lines.append("")
    lines.append("*(Populated manually after reviewing failures above)*")
    lines.append("")
    lines.append("| # | Issue | Severity | Fix |")
    lines.append("|---|-------|----------|-----|")
    lines.append("| 1 | *(fill in)* | High/Med/Low | *(fill in)* |")
    lines.append("")

    return "\n".join(lines)


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_all():
    results: list[TestResult] = []

    print(f"\n{BOLD}{CYAN}=== Datalens Agent Evaluation Harness ==={RESET}")
    print(f"Server : {BASE_URL}")
    print(f"Cases  : {len(TEST_CASES)}")
    print(f"Timeout: {STREAM_TIMEOUT}s per request\n")

    async with httpx.AsyncClient() as client:
        # Authenticate
        print("Authenticating...", end=" ", flush=True)
        try:
            token = await get_token(client)
            print(f"{GREEN}OK{RESET}")
        except Exception as e:
            print(f"{RED}FAILED: {e}{RESET}")
            return

        # Run each test case sequentially (preserves conversation context for chain tests)
        for i, case in enumerate(TEST_CASES, 1):
            prefix = f"[{i:02d}/{len(TEST_CASES)}] {case.id} {case.category:<8}"
            q_display = case.question[:65] + ("…" if len(case.question) > 65 else "")
            print(f"{prefix} {q_display}", end="  ", flush=True)

            # For chain tests, send prior question first and wait for it to
            # complete so MongoDB has the history entry before the follow-up.
            prior_done: dict = {}
            if case.prior_question:
                try:
                    prior_done, _ = await stream_chat(client, token, case.prior_question)
                    await asyncio.sleep(2)  # let server settle + MongoDB commit before follow-up
                except Exception as pe:
                    print(f"\n  (prior_question failed: {pe})", end="  ", flush=True)

            try:
                if case.prior_question:
                    done, elapsed = await stream_chat_for_chain(client, token, case.question, prior_done)
                else:
                    done, elapsed = await stream_chat(client, token, case.question)
                result = check_result(case, done, elapsed)
            except Exception as exc:
                result = TestResult(
                    case=case,
                    passed=False,
                    elapsed=0,
                    failure_reason=f"Exception: {exc}",
                )

            results.append(result)
            status_str = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
            table_str = f"table={result.table_rows}rows" if result.has_table else "no-table"
            print(f"{status_str}  {result.elapsed:.1f}s  {table_str}", end="")
            if not result.passed:
                print(f"  {YELLOW}{result.failure_reason[:80]}{RESET}", end="")
            print()

    # Summary
    passed = sum(1 for r in results if r.passed)
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Results: {passed}/{len(results)} passed ({100*passed/len(results):.1f}%){RESET}")
    print(f"{'='*60}{RESET}\n")

    # Write report
    report = build_report(results)
    report_path = "eval_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to: {report_path}\n")

    return results


if __name__ == "__main__":
    asyncio.run(run_all())
