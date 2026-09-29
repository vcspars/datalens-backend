"""
Comprehensive live test suite for DataLens backend at http://localhost:8008
Tests: SQL-leak, column swap, alignment, history consistency, cross-tab, analysis+table, follow-ups.
Usage: python run_live_tests.py
"""
import json, re, time, urllib.request

TOKEN  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWVhMWNlMzFkMWJkZGZkZmI0OGIzNDUiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJyb2xlIjoiZXhlY3V0aXZlIiwiZXhwIjoxNzc4MTQ1ODUyfQ.QrC1EMzyySARvbhLlgqK-DS7gBZETd6OQVvFJW3xE3A"
BASE   = "http://localhost:8008/api/chat/stream"
PASS = FAIL = WARN = 0
LOG  = []

def chat(question: str, timeout: int = 180) -> dict:
    body = json.dumps({"question": question}).encode()
    req  = urllib.request.Request(BASE, data=body,
           headers={"Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"})
    full_response = sql_query = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            deadline = time.time() + timeout
            for raw in resp:
                if time.time() > deadline: break
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        if payload.get("type") == "done":
                            full_response = payload.get("full_response", "")
                            sql_query     = payload.get("sql_query", "")
                            break
                    except Exception:
                        pass
    except Exception as e:
        full_response = f"[REQUEST ERROR: {e}]"
    return {"response": full_response, "sql": sql_query}

def check(tid, label, result, detail="", warn_only=False):
    global PASS, FAIL, WARN
    if result:
        status = "PASS"; PASS += 1; marker = "\033[32m[PASS]\033[0m"
    elif warn_only:
        status = "WARN"; WARN += 1; marker = "\033[33m[WARN]\033[0m"
    else:
        status = "FAIL"; FAIL += 1; marker = "\033[31m[FAIL]\033[0m"
    LOG.append({"id": tid, "label": label, "status": status, "detail": detail})
    print(f"  {marker} {tid:6s} {label}")
    if detail: print(f"         {detail[:180]}")

def has_sql(r):
    u = r.upper()
    return bool(re.search(r'\bSELECT\b', u) and re.search(r'\bFROM\b', u))

def has_table(r):
    return bool(re.search(r'\|\s*:?-{2,}:?\s*\|', r))

def text_before_table(r):
    idx = r.find("|")
    return r[:idx].strip() if idx > 0 else ""

def col_alignments(r):
    for line in r.splitlines():
        s = line.strip()
        if re.match(r'^\|[\s:\-\|]+\|$', s) and '---' in s:
            parts = [p.strip() for p in s.strip('|').split('|') if p.strip()]
            aligns = []
            for p in parts:
                if p.endswith(':') and not p.startswith(':'): aligns.append('right')
                elif p.startswith(':'): aligns.append('left')
                else: aligns.append('left')
            return aligns
    return []

# ─── GROUP A — SQL-LEAK / TRICKY QUERIES ────────────────────────────────────
print("\n" + "="*62)
print(" GROUP A — SQL-LEAK / TRICKY QUERIES")
print("="*62)

print("\n[A1] Logical groups / CASE WHEN (exact reported failing query)...")
a1 = chat("Assign 5 logical groups to customer return reasons for customer returns for 2025. Name other group as 'not properly entered'. Show logical groups, number of returns and return quantities.")
check("A1a", "No raw SQL in response",   not has_sql(a1["response"]))
check("A1b", "Has formatted table",      has_table(a1["response"]))
check("A1c", "SQL captured",             bool(a1["sql"]), warn_only=True)
print(f"         Response: {a1['response'][:250]}")

print("\n[A2] 'Write me a query' phrasing...")
a2 = chat("Write me a query to show total sales by customer for 2025, ranked highest first.")
check("A2a", "No raw SQL in response",  not has_sql(a2["response"]))
check("A2b", "Has table",               has_table(a2["response"]), warn_only=True)

print("\n[A3] 'Build a report' phrasing...")
a3 = chat("Build a report showing top 10 products by revenue for 2024 with quantities sold.")
check("A3a", "No raw SQL in response",  not has_sql(a3["response"]))
check("A3b", "Has table",               has_table(a3["response"]), warn_only=True)

print("\n[A4] Explicit 'generate SQL' phrasing (was empty/leaked SQL before fix)...")
a4 = chat("Generate SQL to segment customers into 3 tiers based on total 2024 spend using NTILE.")
check("A4a", "No raw SQL in response",  not has_sql(a4["response"]))
check("A4b", "Has table or real data",  has_table(a4["response"]) or len(a4["response"]) > 100)
print(f"         Response preview: {a4['response'][:300]}")

print("\n[A5] Multi-CTE segmentation + cross-reference...")
a5 = chat("Segment our customers into tiers based on total lifetime 5 years spend. Cross-reference with FactCreditMemo to identify high-value customers with a high return rate. What is the Net Value of these customers?")
check("A5a", "No raw SQL in response",  not has_sql(a5["response"]))
check("A5b", "Has table",               has_table(a5["response"]), warn_only=True)

print("\n[A6] 'Show me the SQL you would use, then show results' trick...")
a6 = chat("Show me what SQL you would use to find the top 5 customers with highest return rates in 2025, then show me the actual results.")
check("A6a", "No raw SQL leaked",  not has_sql(a6["response"]))
check("A6b", "Has actual data",    has_table(a6["response"]) or len(a6["response"]) > 100, warn_only=True)
print(f"         Response: {a6['response'][:200]}")

print("\n[A7] 'Without SQL just tell me numbers' trick...")
a7 = chat("Without writing any SQL, just tell me the total revenue for 2025 and how it compares to 2024.")
check("A7a", "No raw SQL",   not has_sql(a7["response"]))
check("A7b", "Has numbers",  bool(re.search(r'\$|[0-9]{4,}', a7["response"])), warn_only=True)
print(f"         Response: {a7['response'][:200]}")

# ─── GROUP B — COLUMN SWAP + ALIGNMENT ──────────────────────────────────────
print("\n" + "="*62)
print(" GROUP B — COLUMN SWAP + ALIGNMENT")
print("="*62)

print("\n[B1] Customer categories — column order check...")
b1 = chat("Show me the customer categories in DimCustomer — their IDs, how many customers are in each, and an example customer name.")
check("B1a", "No raw SQL",  not has_sql(b1["response"]))
check("B1b", "Has table",   has_table(b1["response"]), warn_only=True)
b1_rows = [l.strip() for l in b1["response"].splitlines()
           if l.strip().startswith("|") and "---" not in l and "Category" not in l and l.count("|") >= 4]
swap_found = any(
    re.match(r'^\d+$', cells[2]) and not re.match(r'^\d+$', cells[1]) and re.match(r'^\d+$', cells[0])
    for row in b1_rows[:3]
    for cells in [[c.strip() for c in row.strip("|").split("|")]]
    if len(cells) >= 3
)
check("B1c", "Column order correct (no count/name swap)", not swap_found)
print(f"         First data rows: {b1_rows[:2]}")

print("\n[B2] Multi-aggregate numeric right-alignment...")
b2 = chat("Show me top 10 customers by total sales in 2025 with their order count and average order value.")
check("B2a", "No raw SQL",                     not has_sql(b2["response"]))
check("B2b", "Has table",                      has_table(b2["response"]), warn_only=True)
aligns_b2 = col_alignments(b2["response"])
check("B2c", "Numeric cols right-aligned",     any(a == "right" for a in aligns_b2), warn_only=True)
print(f"         Alignments: {aligns_b2}")

print("\n[B3] COUNT + SUM + MIN + MAX — 4+ columns, alignment check...")
b3 = chat("For each product category show: number of products, total units sold in 2025, minimum unit price, maximum unit price.")
check("B3a", "No raw SQL",         not has_sql(b3["response"]))
check("B3b", "Has table",          has_table(b3["response"]), warn_only=True)
aligns_b3 = col_alignments(b3["response"])
check("B3c", "4+ columns present", len(aligns_b3) >= 4, warn_only=True)

# ─── GROUP C — HISTORY CONSISTENCY (Issue 1) ────────────────────────────────
print("\n" + "="*62)
print(" GROUP C — HISTORY CONSISTENCY (same query twice)")
print("="*62)

print("\n[C1] Same complex query run TWICE — SQL must be identical...")
cq = "Segment customers into tiers based on total 5-year lifetime spend. Cross-reference with FactCreditMemo to find high-value customers with return rate above 20%. Show net value and top return product category."
c1a = chat(cq)
c1b = chat(cq)
check("C1a", "Run 1 has table",    has_table(c1a["response"]))
check("C1b", "Run 2 has table",    has_table(c1b["response"]))
sql_match = (c1a["sql"].strip() == c1b["sql"].strip())
check("C1c", "Both runs produce identical SQL",  sql_match)
if not sql_match:
    for i, (a, b) in enumerate(zip(c1a["sql"], c1b["sql"])):
        if a != b:
            print(f"         First diff at char {i}:")
            print(f"           RUN1: ...{c1a['sql'][max(0,i-40):i+80]}...")
            print(f"           RUN2: ...{c1b['sql'][max(0,i-40):i+80]}...")
            break
else:
    print(f"         SQL identical: YES (len={len(c1a['sql'])})")

print("\n[C2] Simpler query twice — basic consistency check...")
sq = "Top 10 customers by total sales in 2025 with order count and average order value."
s1 = chat(sq); s2 = chat(sq)
check("C2a", "Run 1 has table",   has_table(s1["response"]))
check("C2b", "Run 2 has table",   has_table(s2["response"]))
check("C2c", "Identical SQL",     s1["sql"].strip() == s2["sql"].strip())
if s1["sql"].strip() != s2["sql"].strip():
    for i, (a, b) in enumerate(zip(s1["sql"], s2["sql"])):
        if a != b:
            print(f"         Diff at char {i}: '{s1['sql'][i-20:i+30]}' vs '{s2['sql'][i-20:i+30]}'")
            break

# ─── GROUP D — CROSS-TAB / MULTI-COLUMN ANALYTICAL ──────────────────────────
print("\n" + "="*62)
print(" GROUP D — CROSS-TAB / MULTI-COLUMN ANALYTICAL")
print("="*62)

print("\n[D1] Quarterly breakdown 2024 (sales + returns + net + rate)...")
d1 = chat("Show me total sales, total returns, and net revenue by quarter for 2024. Include the return rate as a percentage.")
check("D1a", "No raw SQL",       not has_sql(d1["response"]))
check("D1b", "Has table",        has_table(d1["response"]), warn_only=True)
check("D1c", "Quarters present", bool(re.search(r'Q[1-4]|Quarter', d1["response"])), warn_only=True)

print("\n[D2] Year-over-year 2023 vs 2024 with change % ...")
d2 = chat("Compare total sales, total COGS, and gross profit for 2023 vs 2024. Show YoY change in dollars and percentage.")
check("D2a", "No raw SQL",         not has_sql(d2["response"]))
check("D2b", "Has table",          has_table(d2["response"]), warn_only=True)
check("D2c", "Both years present", "2023" in d2["response"] and "2024" in d2["response"], warn_only=True)

print("\n[D3] Product category × Q1 vs Q2 2025 side by side...")
d3 = chat("Show me sales revenue broken down by product category for Q1 and Q2 of 2025 side by side.")
check("D3a", "No raw SQL",  not has_sql(d3["response"]))
check("D3b", "Has table",   has_table(d3["response"]), warn_only=True)

print("\n[D4] Top 10 customers: spend + returns + top return category (multi-join)...")
d4 = chat("For the top 10 customers by 2025 sales, show their total spend, total credit memo amount, net value, and which product category has the most returns for each.")
check("D4a", "No raw SQL",  not has_sql(d4["response"]))
check("D4b", "Has table",   has_table(d4["response"]), warn_only=True)
check("D4c", "OUTER APPLY or TOP 1 in SQL", bool(re.search(r'OUTER APPLY|TOP 1', d4["sql"], re.IGNORECASE)), warn_only=True)

# ─── GROUP E — "5-YEAR" DATE RANGE CONSISTENCY ───────────────────────────────
print("\n" + "="*62)
print(" GROUP E — 5-YEAR DATE RANGE (Issue 2 fix)")
print("="*62)

print("\n[E1] '5 years' → should use YEAR(GETDATE())-4 (not -5)...")
e1a = chat("Show me total sales per year for the last 5 years.")
e1b = chat("Show me total sales per year for the last 5 years.")
e1c = chat("Show me total sales per year for the last 5 years.")
uses_minus4_a = "GETDATE())-4" in e1a["sql"] or "GETDATE()) - 4" in e1a["sql"]
uses_minus4_b = "GETDATE())-4" in e1b["sql"] or "GETDATE()) - 4" in e1b["sql"]
uses_minus4_c = "GETDATE())-4" in e1c["sql"] or "GETDATE()) - 4" in e1c["sql"]
check("E1a", "Run 1: uses YEAR(GETDATE())-4 for 5 years",  uses_minus4_a)
check("E1b", "Run 2: uses YEAR(GETDATE())-4 for 5 years",  uses_minus4_b)
check("E1c", "Run 3: uses YEAR(GETDATE())-4 for 5 years",  uses_minus4_c)
print(f"         Run1 SQL snippet: {e1a['sql'][e1a['sql'].find('BETWEEN'):e1a['sql'].find('BETWEEN')+60] if 'BETWEEN' in e1a['sql'] else e1a['sql'][:80]}")
print(f"         Run2 SQL snippet: {e1b['sql'][e1b['sql'].find('BETWEEN'):e1b['sql'].find('BETWEEN')+60] if 'BETWEEN' in e1b['sql'] else e1b['sql'][:80]}")
print(f"         Run3 SQL snippet: {e1c['sql'][e1c['sql'].find('BETWEEN'):e1c['sql'].find('BETWEEN')+60] if 'BETWEEN' in e1c['sql'] else e1c['sql'][:80]}")

print("\n[E2] 'Last 3 years' → should use YEAR(GETDATE())-2...")
e2 = chat("Show total revenue per year for the last 3 years.")
uses_minus2 = "GETDATE())-2" in e2["sql"] or "GETDATE()) - 2" in e2["sql"]
check("E2a", "Uses YEAR(GETDATE())-2 for 3 years", uses_minus2)
print(f"         SQL snippet: {e2['sql'][e2['sql'].find('BETWEEN'):e2['sql'].find('BETWEEN')+60] if 'BETWEEN' in e2['sql'] else e2['sql'][:80]}")

# ─── GROUP F — ANALYSIS + TABLE COMBINED ────────────────────────────────────
print("\n" + "="*62)
print(" GROUP F — ANALYSIS + TABLE COMBINED (INSIGHTS)")
print("="*62)

print("\n[F1] Insights requested — commentary BEFORE table...")
f1 = chat("Show me the top 10 customers by 2025 net sales and share key findings and areas that require attention.")
tb_f1 = text_before_table(f1["response"])
check("F1a", "No raw SQL",                    not has_sql(f1["response"]))
check("F1b", "Has table",                     has_table(f1["response"]))
check("F1c", "Commentary before table >80c",  len(tb_f1) > 80)
print(f"         Text before table ({len(tb_f1)} chars): {tb_f1[:160]}")

print("\n[F2] Pure data request — table with minimal preamble...")
f2 = chat("Top 10 customers by total sales in 2025.")
tb_f2 = text_before_table(f2["response"])
check("F2a", "No raw SQL",             not has_sql(f2["response"]))
check("F2b", "Has table",              has_table(f2["response"]))
check("F2c", "No unsolicited essay",   len(tb_f2) < 150, warn_only=True)

print("\n[F3] Annual P&L 3-year pivot + insights (core regression)...")
f3 = chat("Annual PL sub grouped pl statement for 2023, 2024 and 2025 share key findings and areas that require attention")
check("F3a", "No raw SQL",              not has_sql(f3["response"]))
check("F3b", "3-year pivot header",     bool(re.search(r'2023.*2024.*2025', f3["response"])))
check("F3c", "Commentary before table", len(text_before_table(f3["response"])) > 80)
check("F3d", "No raw SQL row dump",     "| Cost Of Goods Sold | Cost of Goods Sold | 202" not in f3["response"])

print("\n[F4] Pure financial statement — no unsolicited commentary...")
f4 = chat("P&L sub grouped for March 2025")
check("F4a", "No raw SQL",  not has_sql(f4["response"]))
check("F4b", "Has table",   has_table(f4["response"]))

# ─── GROUP G — CONTEXTUAL FOLLOW-UPS ────────────────────────────────────────
print("\n" + "="*62)
print(" GROUP G — CONTEXTUAL FOLLOW-UPS")
print("="*62)

print("\n[G1] 'Same but for vendors' follow-up...")
chat("Show me top 10 customers by total sales in 2025.")
g1 = chat("Now same but for vendors instead of customers.")
check("G1a", "No raw SQL",     not has_sql(g1["response"]))
check("G1b", "Has table",      has_table(g1["response"]), warn_only=True)
check("G1c", "Vendor context", bool(re.search(r'[Vv]endor|[Ss]upplier', g1["response"])), warn_only=True)

print("\n[G2] 'Filter to 2024 + add margin' follow-up...")
chat("Show me top 10 products by total revenue.")
g2 = chat("Now filter that to only 2024 data and add the gross margin percentage.")
check("G2a", "No raw SQL",       not has_sql(g2["response"]))
check("G2b", "Has table",        has_table(g2["response"]), warn_only=True)
check("G2c", "2024 in SQL",      "2024" in g2["sql"], warn_only=True)

print("\n[G3] Ultra-complex cohort + quarterly breakdown...")
g3 = chat("Find customers who placed their first order in Q1 2024. Show their total spend in Q1, Q2, Q3, Q4 of 2024 side by side. Which product category did they buy most in Q4?")
check("G3a", "No raw SQL",         not has_sql(g3["response"]))
check("G3b", "Has table",          has_table(g3["response"]), warn_only=True)
check("G3c", "Quarter refs present", bool(re.search(r'Q[1-4]|Quarter', g3["response"])), warn_only=True)

# ─── FINAL REPORT ─────────────────────────────────────────────────────────────
print("\n" + "="*62)
print(f" FINAL: {PASS} PASS | {FAIL} FAIL | {WARN} WARN | {PASS+FAIL+WARN} TOTAL")
print("="*62)
failures = [x for x in LOG if x["status"] == "FAIL"]
warnings = [x for x in LOG if x["status"] == "WARN"]
if failures:
    print("\n\033[31mFAILURES:\033[0m")
    for f in failures:
        print(f"  [{f['id']}] {f['label']}")
        if f["detail"]: print(f"       {f['detail'][:160]}")
else:
    print("\n\033[32mAll hard checks passed!\033[0m")
if warnings:
    print("\n\033[33mWARNINGS (manual review):\033[0m")
    for w in warnings:
        print(f"  [{w['id']}] {w['label']}")
        if w["detail"]: print(f"       {w['detail'][:160]}")
print()
