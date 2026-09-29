"""
Deep-dive on Issue 1: Run the same complex query 5 times with NO session history
and compare the full SQL output to understand remaining non-determinism.
Also check A4 (empty response issue).
"""
import json, re, time, urllib.request

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWVhMWNlMzFkMWJkZGZkZmI0OGIzNDUiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJyb2xlIjoiZXhlY3V0aXZlIiwiZXhwIjoxNzc4MTQxMzUyfQ.p4cqnh93lhcgcEUKI4rwdQFEssd8TmxrKSeo9R2Mlso"
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

# ─── TEST 1: Same query 5 times, compare SQL ────────────────────────────────
print("="*70)
print("TEST 1: Same complex query x5 — comparing SQL across all runs")
print("="*70)

cq = "Segment customers into tiers based on total 5-year lifetime spend. Cross-reference with FactCreditMemo to find high-value customers with return rate above 20%. Show net value and top return product category."

runs = []
for i in range(5):
    print(f"  Run {i+1}/5 ...", end=" ", flush=True)
    r = chat(cq)
    runs.append(r["sql"])
    print(f"SQL={len(r['sql'])} chars")

print()
baseline = runs[0]
all_same = all(s == baseline for s in runs)
print(f"All 5 SQLs identical: {all_same}")
print(f"SQL lengths: {[len(s) for s in runs]}")

for i, sql in enumerate(runs):
    if sql != baseline:
        for j, (a, b) in enumerate(zip(baseline, sql)):
            if a != b:
                print(f"\n  Run {i+1} first differs at char {j}:")
                print(f"    BASE: ...{baseline[max(0,j-50):j+100]}...")
                print(f"    RUN{i+1}: ...{sql[max(0,j-50):j+100]}...")
                break
        if len(sql) != len(baseline):
            print(f"  Run {i+1} length differs: baseline={len(baseline)}, this={len(sql)}")

print()
print("Structural equivalence (same CTEs and JOINs, just name differences):")
def normalize_cte_names(sql):
    """Replace CTE names with generic CTE1, CTE2 etc. to check structural equality."""
    cte_names = re.findall(r'(\w+)\s+AS\s*\(', sql, re.IGNORECASE)
    # Only top-level CTE names (after WITH or comma at same level)
    top_ctes = re.findall(r'(?:WITH|,)\s*(\w+)\s+AS\s*\(', sql, re.IGNORECASE)
    normalized = sql
    for i, name in enumerate(top_ctes):
        normalized = re.sub(r'\b' + re.escape(name) + r'\b', f'CTE{i+1}', normalized)
    # Also normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

norm_baseline = normalize_cte_names(baseline)
all_structurally_same = all(normalize_cte_names(s) == norm_baseline for s in runs)
print(f"All 5 SQLs structurally identical (ignoring CTE names + whitespace): {all_structurally_same}")

# ─── TEST 2: Simpler query 3 times ──────────────────────────────────────────
print()
print("="*70)
print("TEST 2: Simpler query x3 — verifying determinism for common queries")
print("="*70)

sq = "Top 10 customers by total sales in 2025 with their order count and average order value."
sruns = []
for i in range(3):
    print(f"  Run {i+1}/3 ...", end=" ", flush=True)
    r = chat(sq)
    sruns.append(r["sql"])
    print(f"SQL={len(r['sql'])} chars")

all_same_s = all(s == sruns[0] for s in sruns)
print(f"All 3 simple SQLs identical: {all_same_s}")
if not all_same_s:
    for i, sql in enumerate(sruns):
        if sql != sruns[0]:
            for j, (a, b) in enumerate(zip(sruns[0], sql)):
                if a != b:
                    print(f"  Run {i+1} first differs at char {j}: '{sruns[0][j-20:j+30]}' vs '{sql[j-20:j+30]}'")
                    break

# ─── TEST 3: A4 — "Generate SQL" empty response investigation ───────────────
print()
print("="*70)
print("TEST 3: A4 — 'Generate SQL' phrasing (was empty response)")
print("="*70)
a4 = chat("Generate SQL to segment customers into 3 tiers based on total 2024 spend using NTILE.")
print(f"Response ({len(a4['response'])} chars): {a4['response'][:400]}")
print(f"SQL ({len(a4['sql'])} chars): {a4['sql'][:200]}")
