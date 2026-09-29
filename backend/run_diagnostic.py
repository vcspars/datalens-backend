"""
Targeted diagnostic: re-run only the failing cases with full response dumps.
"""
import json, re, time, urllib.request

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWVhMWNlMzFkMWJkZGZkZmI0OGIzNDUiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJyb2xlIjoiZXhlY3V0aXZlIiwiZXhwIjoxNzc4MTM5NDQ3fQ.vDmQa9FJUQTmn4cDipI-cMyQMlpSldSv2TZEb8sLgZ0"
BASE  = "http://localhost:8008/api/chat/stream"

def chat(q, timeout=180):
    body = json.dumps({"question": q}).encode()
    req  = urllib.request.Request(BASE, data=body,
           headers={"Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"})
    full_response = sql_query = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
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
        full_response = f"[ERROR: {e}]"
    return {"response": full_response, "sql": sql_query}

def sep_fmt(r):
    """Find the actual separator row in the response and show its format."""
    for line in r.splitlines():
        s = line.strip()
        if '---' in s and s.count('|') >= 2:
            return f"SEPARATOR ROW: '{s}'"
    return "NO separator row found"

def show(label, r):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  FULL RESPONSE ({len(r['response'])} chars):")
    print(r['response'])
    print(f"\n  SQL ({len(r['sql'])} chars): {r['sql'][:400]}")
    print(f"\n  {sep_fmt(r['response'])}")

# ─── A1: Logical groups (was FAIL on has_table) ─────────────────────────────
print("\n>>> A1 RE-RUN: Logical groups / return reasons")
a1 = chat("Assign 5 logical groups to customer return reasons for customer returns for 2025. Name other group as 'not properly entered'. Show logical groups, number of returns and return quantities.")
show("A1 — Logical groups (checking for table presence)", a1)

# ─── E1: Top customers + insights (was FAIL on has_table) ───────────────────
print("\n>>> E1 RE-RUN: Top customers with key findings")
e1 = chat("Show me the top 10 customers by 2025 net sales and share key findings and areas that require attention.")
show("E1 — Top customers + insights (checking for table presence)", e1)

# ─── E2: Pure top 10 customers (was FAIL on has_table) ──────────────────────
print("\n>>> E2 RE-RUN: Pure top 10 customers (no insights)")
e2 = chat("Top 10 customers by total sales in 2025.")
show("E2 — Pure top 10 customers (checking for table presence)", e2)

# ─── C1: Same query twice (SQL consistency check) ───────────────────────────
print("\n>>> C1 RE-RUN: Same complex query twice (Issue 1)")
cq = "Segment customers into tiers based on total 5-year lifetime spend. Cross-reference with FactCreditMemo to find high-value customers with return rate above 20%. Show net value and top return product category."
r1 = chat(cq)
r2 = chat(cq)
print(f"\n{'='*70}")
print("  C1 — Run 1 SQL (500 chars):")
print(r1['sql'][:500])
print(f"\n  C1 — Run 2 SQL (500 chars):")
print(r2['sql'][:500])
print(f"\n  FULL SQL IDENTICAL: {r1['sql'].strip() == r2['sql'].strip()}")
if r1['sql'].strip() != r2['sql'].strip():
    # Find first diff position
    for i, (a, b) in enumerate(zip(r1['sql'], r2['sql'])):
        if a != b:
            print(f"  First difference at char {i}:")
            print(f"    RUN1: ...{r1['sql'][max(0,i-40):i+80]}...")
            print(f"    RUN2: ...{r2['sql'][max(0,i-40):i+80]}...")
            break
print(f"\n  Run1 has_table: {'|' in r1['response'] and '---' in r1['response']}")
print(f"  Run2 has_table: {'|' in r2['response'] and '---' in r2['response']}")
print(f"  Run1 separator: {sep_fmt(r1['response'])}")
print(f"  Run2 separator: {sep_fmt(r2['response'])}")
