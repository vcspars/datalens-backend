"""
Comprehensive client-scenario tests covering every query type the user listed.
Runs in 3 small batches (pass batch number as arg: 1, 2, or 3).
python run_client_queries.py 1
"""
import json, re, sys, time, urllib.request

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWVhMWNlMzFkMWJkZGZkZmI0OGIzNDUiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJyb2xlIjoiZXhlY3V0aXZlIiwiZXhwIjoxNzc4MTUxMTk2fQ.1V_DXaBcQ96LQdIDTqw5e1-g4fACcglcVrIYmCCpAes"
BASE  = "http://localhost:8008/api/chat/stream"
PASS = FAIL = WARN = 0
LOG  = []
SLOW = 60  # seconds

def chat(q, timeout=270):
    body = json.dumps({"question": q}).encode()
    req  = urllib.request.Request(BASE, data=body,
           headers={"Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"})
    t0 = time.time(); fr = sq = ""; timedout = False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                if time.time()-t0 > timeout: timedout=True; break
                line = raw.decode("utf-8","replace").strip()
                if line.startswith("data: "):
                    try:
                        p = json.loads(line[6:])
                        if p.get("type")=="done": fr=p.get("full_response",""); sq=p.get("sql_query",""); break
                    except: pass
    except Exception as e: fr=f"[ERR:{e}]"
    return {"r":fr,"sql":sq,"s":round(time.time()-t0,1),"to":timedout}

def chk(tid,lbl,ok,d="",w=False):
    global PASS,FAIL,WARN
    if ok:    PASS+=1; c="\033[32m[PASS]\033[0m"
    elif w:   WARN+=1; c="\033[33m[WARN]\033[0m"
    else:     FAIL+=1; c="\033[31m[FAIL]\033[0m"
    s="PASS" if ok else ("WARN" if w else "FAIL")
    LOG.append({"id":tid,"lbl":lbl,"s":s,"d":d})
    print(f"  {c} {tid:6s} {lbl}")
    if d: print(f"         {d[:180]}")

def H(title):
    print(f"\n{'═'*64}\n  {title}\n{'═'*64}")

def T(r):
    s=r["s"]; col="\033[31m" if s>SLOW else ("\033[33m" if s>30 else "\033[32m")
    flag=" ⚠ SLOW" if s>SLOW else (" ⚡moderate" if s>30 else "")
    print(f"  {col}⏱  {s}s{flag}\033[0m")
    if r["to"]: print("  \033[31m[TIMED OUT — query exceeded 270s]\033[0m")

no_sql = lambda r: not(re.search(r'\bSELECT\b',r.upper()) and re.search(r'\bFROM\b',r.upper()))
has_tbl= lambda r: bool(re.search(r'\|\s*:?-{2,}:?\s*\|',r))
has_num= lambda r: bool(re.search(r'\$|[0-9]{3,}',r))
pct    = lambda r: bool(re.search(r'%|\bpercent',r,re.I))
sep_cte= lambda sql: ("SalesActivity" in sql or "PaymentActivity" in sql) and "CustomerActivity" not in sql

BATCH = int(sys.argv[1]) if len(sys.argv)>1 else 0

# ══════════════════════════════════════════════════════════════
# BATCH 1 — Financial, Date Comparisons, Aging, Forecast
# ══════════════════════════════════════════════════════════════
if BATCH in (0,1):

    H("Q1 — Quarterly P&L comparison 2024 vs 2025 + % change")
    r=chat("I need quarterly comparison of PL summary for 2024 and 2025 along with percentage")
    T(r)
    chk("Q1a","No raw SQL",no_sql(r["r"]))
    chk("Q1b","Has table",has_tbl(r["r"]))
    chk("Q1c","Has % values",pct(r["r"]))
    chk("Q1d","Both years present","2024" in r["r"] and "2025" in r["r"])
    chk("Q1e","Quarters present",bool(re.search(r'Q[1-4]|Quarter',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q2 — Jan 2026 vs Jan 2025 — monthly sales + % change")
    r=chat("Monthly sales for January 2026, along with a comparison to January 2025, including the percentage increase or decrease.")
    T(r)
    chk("Q2a","No raw SQL",no_sql(r["r"]))
    chk("Q2b","Has table",has_tbl(r["r"]))
    chk("Q2c","Has % values",pct(r["r"]))
    chk("Q2d","2026 in SQL","2026" in r["sql"])
    chk("Q2e","2025 in SQL","2025" in r["sql"])
    print(f"  Preview: {r['r'][:250]}")

    H("Q3 — Jan 2026 vs Jan 2025 — performance card")
    r=chat("Monthly sales for January 2026, along with a comparison to January 2025, including the percentage increase or decrease. Prepare a performance card.")
    T(r)
    chk("Q3a","No raw SQL",no_sql(r["r"]))
    chk("Q3b","Has table",has_tbl(r["r"]))
    chk("Q3c","Has % and both years",pct(r["r"]) and "2026" in r["r"] and "2025" in r["r"])
    print(f"  Preview: {r['r'][:280]}")

    H("Q4 — Customer balance aging (Active/Sleeping/Doubtful/Bad Debt) — VARIANT 1: balances")
    r=chat("Summarize customer balances based on their sales and payment history. Active Customer that have sales and payments in last 12 months, Sleeping Customers that were active in 13-24 months, doubtful that were active in 25-36 months, and bad debts that were due older than 36 months")
    T(r)
    chk("Q4a","No raw SQL",no_sql(r["r"]))
    chk("Q4b","Has table",has_tbl(r["r"]))
    chk("Q4c","Active present",bool(re.search(r'[Aa]ctive',r["r"])))
    chk("Q4d","Sleeping present",bool(re.search(r'[Ss]leeping',r["r"])))
    chk("Q4e","Doubtful present",bool(re.search(r'[Dd]oubtful',r["r"])))
    chk("Q4f","Bad debt present",bool(re.search(r'[Bb]ad.{0,5}[Dd]ebt',r["r"])))
    chk("Q4g","Uses separate CTEs (not cross-join)",sep_cte(r["sql"]))
    print(f"  CTE check — SalesActivity: {'SalesActivity' in r['sql']}, CustomerActivity (bad): {'CustomerActivity' in r['sql']}")
    print(f"  Preview: {r['r'][:280]}")

    H("Q5 — Customer CLOSING balances aging — VARIANT 2 (the previously slow query)")
    r=chat("Summarize customer current closing balances based on their sales and payment history. Active Customer that have sales and payments in last 12 months, Sleeping Customers that were active in 13-24 months, doubtful that were active in 25-36 months, and bad debts that were due older than 36 months")
    T(r)
    chk("Q5a","No raw SQL",no_sql(r["r"]))
    chk("Q5b","Has table",has_tbl(r["r"]))
    chk("Q5c","Active present",bool(re.search(r'[Aa]ctive',r["r"])))
    chk("Q5d","Bad debt present",bool(re.search(r'[Bb]ad.{0,5}[Dd]ebt',r["r"])))
    chk("Q5e","Uses separate CTEs (not cross-join)",sep_cte(r["sql"]))
    chk("Q5f","Completed in time (not timed out)",not r["to"])
    if r["s"]>SLOW: print(f"  \033[31m  ⚠ Still slow: {r['s']}s — AP9 may not have fixed it\033[0m")
    else:           print(f"  ✅ Fast enough: {r['s']}s")
    print(f"  CTE check — SalesActivity: {'SalesActivity' in r['sql']}, CustomerActivity (bad): {'CustomerActivity' in r['sql']}")

    H("Q6 — 2025 forecast based on 2024 actuals + variance + %")
    r=chat("Based on monthly sales for 2024, please project forecast monthly sales for 2025 and also compare the forecast of 2025 with actual numbers and variance in amount and %")
    T(r)
    chk("Q6a","No raw SQL",no_sql(r["r"]))
    chk("Q6b","Has table",has_tbl(r["r"]))
    chk("Q6c","Forecast present",bool(re.search(r'[Ff]orecast|[Pp]rojected?',r["r"])))
    chk("Q6d","Variance present",bool(re.search(r'[Vv]ariance',r["r"])))
    chk("Q6e","Has % values",pct(r["r"]))
    print(f"  Preview: {r['r'][:280]}")

# ══════════════════════════════════════════════════════════════
# BATCH 2 — What-If, ABC, Margins, Specific Customers, Cohort
# ══════════════════════════════════════════════════════════════
if BATCH in (0,2):

    H("Q7 — Monthly 2025 profit + What-If: Qty +10%, Price +5%")
    r=chat("Monthly sales of 2025 with quantity and profit, what could be profit if Quantity increase by 10% and Sales Prices by 5%, show profit before and after the increase")
    T(r)
    chk("Q7a","No raw SQL",no_sql(r["r"]))
    chk("Q7b","Has table",has_tbl(r["r"]))
    chk("Q7c","Before/After present",bool(re.search(r'[Bb]efore|[Aa]fter|[Cc]urrent|[Pp]rojected?',r["r"])))
    chk("Q7d","Profit present",bool(re.search(r'[Pp]rofit',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q8 — ABC Analysis of inventory items (value + quantity)")
    r=chat("Prepare an ABC Analysis summary of items on hand, value and quantity")
    T(r)
    chk("Q8a","No raw SQL",no_sql(r["r"]))
    chk("Q8b","Has table",has_tbl(r["r"]))
    chk("Q8c","A/B/C categories present",bool(re.search(r'\bA\b.*\bB\b.*\bC\b|ABC',r["r"])))
    chk("Q8d","Value/Qty present",bool(re.search(r'[Vv]alue|[Qq]uantity|[Qq]ty',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q9 — Jan 2025: Gross Sales, Net Sales, Gross Margin + %")
    r=chat("what is gross sales, net sales, gross margin and % margin for january 2025")
    T(r)
    chk("Q9a","No raw SQL",no_sql(r["r"]))
    chk("Q9b","Has table or values",has_tbl(r["r"]) or has_num(r["r"]))
    chk("Q9c","Gross sales present",bool(re.search(r'[Gg]ross.{0,6}[Ss]ales',r["r"])))
    chk("Q9d","Margin present",bool(re.search(r'[Mm]argin',r["r"])))
    chk("Q9e","% value present",pct(r["r"]))
    print(f"  Preview: {r['r'][:280]}")

    H("Q10 — 2026 vs 2025 monthly for TJ Maxx, Marshalls, Mackenzie, Williams Sonoma")
    r=chat("Provide monthly sales for 2026 vs 2025 for TJ Maxx, Marshalls, Mackenzie Childs, and Williams Sonoma. Calculate the gap to reach 2025 monthly averages and project annual recovery value.")
    T(r)
    chk("Q10a","No raw SQL",no_sql(r["r"]))
    chk("Q10b","Has table",has_tbl(r["r"]))
    chk("Q10c","Customer names found",bool(re.search(r'TJ Maxx|Marshalls|Mackenzie|Williams Sonoma',r["r"],re.I)))
    chk("Q10d","Gap/recovery present",bool(re.search(r'[Gg]ap|[Rr]ecovery|[Aa]verage',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q11 — Follow-up: top 10 customers highest variance March 2025")
    r=chat("Do the same analysis by customers for same periods and list top 10 customers with highest variance in march 2025")
    T(r)
    chk("Q11a","No raw SQL",no_sql(r["r"]))
    chk("Q11b","Has table",has_tbl(r["r"]))
    chk("Q11c","Variance present",bool(re.search(r'[Vv]ariance',r["r"])))
    chk("Q11d","March/2025",bool(re.search(r'[Mm]arch|2025',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q12 — Annual sales by customer price categories 2026")
    r=chat("Aggregate annual sales by customer price categories in 2026")
    T(r)
    chk("Q12a","No raw SQL",no_sql(r["r"]))
    chk("Q12b","Has table",has_tbl(r["r"]))
    chk("Q12c","2026 in SQL","2026" in r["sql"])
    chk("Q12d","Category present",bool(re.search(r'[Cc]ategor|[Pp]rice',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

# ══════════════════════════════════════════════════════════════
# BATCH 3 — Outstanding Balances, Backorders, Customer Tiers, Cohort
# ══════════════════════════════════════════════════════════════
if BATCH in (0,3):

    H("Q13 — Highest outstanding balances + contributing factors")
    r=chat("Which customers have the highest outstanding balances, and what is contributing to these unpaid amounts?")
    T(r)
    chk("Q13a","No raw SQL",no_sql(r["r"]))
    chk("Q13b","Has table",has_tbl(r["r"]),w=True)
    chk("Q13c","Has amounts",has_num(r["r"]))
    chk("Q13d","Customer context",bool(re.search(r'[Cc]ustomer|[Aa]ccount',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q14 — Outstanding balances + payment behavior patterns")
    r=chat("Which customers have the highest outstanding balances, and what patterns exist in their payment behavior?")
    T(r)
    chk("Q14a","No raw SQL",no_sql(r["r"]))
    chk("Q14b","Has table",has_tbl(r["r"]),w=True)
    chk("Q14c","Payment/balance context",bool(re.search(r'[Pp]ayment|[Bb]alance',r["r"])))
    chk("Q14d","Has amounts",has_num(r["r"]))
    print(f"  Preview: {r['r'][:280]}")

    H("Q15 — Backorder reasons + most affected products/warehouses")
    r=chat("What are the main reasons for backorders, and which products or warehouses are most affected?")
    T(r)
    chk("Q15a","No raw SQL",no_sql(r["r"]))
    chk("Q15b","Has data",has_tbl(r["r"]) or len(r["r"])>200,w=True)
    chk("Q15c","Backorder context",bool(re.search(r'[Bb]ackorder|[Bb]ack.?order',r["r"])))
    print(f"  Preview: {r['r'][:280]}")

    H("Q16 — Customer tiers (5-yr) + credit memos + net value + return category")
    r=chat("Segment our customers in DimCustomer into tiers based on total lifetime 5 years data only spend from FactSalesInvoice. Cross-reference with FactCreditMemo to identify high-value customers who also have a high return rate. What is the Net Value of these customers, and is there a specific DimProduct category driving these returns?")
    T(r)
    chk("Q16a","No raw SQL",no_sql(r["r"]))
    chk("Q16b","Has table",has_tbl(r["r"]))
    chk("Q16c","Net value present",bool(re.search(r'[Nn]et.?[Vv]alue|NetValue',r["r"])))
    chk("Q16d","Category present",bool(re.search(r'[Cc]ategor',r["r"])))
    chk("Q16e","5-yr = GETDATE()-4","GETDATE())-4" in r["sql"] or "GETDATE()) - 4" in r["sql"])
    snippet=r["sql"][r["sql"].find("BETWEEN"):r["sql"].find("BETWEEN")+65] if "BETWEEN" in r["sql"] else r["sql"][:80]
    print(f"  BETWEEN clause: {snippet}")
    print(f"  Preview: {r['r'][:280]}")

    H("Q17 — SAME Q16 again — SQL consistency + no cross-join")
    r2=chat("Segment our customers in DimCustomer into tiers based on total lifetime 5 years data only spend from FactSalesInvoice. Cross-reference with FactCreditMemo to identify high-value customers who also have a high return rate. What is the Net Value of these customers, and is there a specific DimProduct category driving these returns?")
    T(r2)
    chk("Q17a","Run 2 no raw SQL",no_sql(r2["r"]))
    chk("Q17b","Run 2 has table",has_tbl(r2["r"]))
    chk("Q17c","5-yr = GETDATE()-4","GETDATE())-4" in r2["sql"] or "GETDATE()) - 4" in r2["sql"])
    chk("Q17d","SQL matches run 1",r["sql"].strip()==r2["sql"].strip(),w=True)

    H("Q18 — 'Without SQL tell me the numbers' trick")
    r=chat("Without writing any SQL, just tell me total revenue for 2025 vs 2024.")
    T(r)
    chk("Q18a","No raw SQL",no_sql(r["r"]))
    chk("Q18b","Has numbers",has_num(r["r"]))
    chk("Q18c","Both years",  "2025" in r["r"] and "2024" in r["r"])
    print(f"  Preview: {r['r'][:200]}")

    H("Q19 — 'Generate SQL' phrasing (was leaking SQL before fix)")
    r=chat("Generate SQL to find top 10 customers by net sales for 2025.")
    T(r)
    chk("Q19a","No raw SQL in response",no_sql(r["r"]))
    chk("Q19b","Has table or data",has_tbl(r["r"]) or has_num(r["r"]))
    print(f"  Preview: {r['r'][:250]}")

# ══════════════════════════════════════════════════════════════
print(f"\n{'═'*64}")
print(f"  FINAL: {PASS} PASS | {FAIL} FAIL | {WARN} WARN | {PASS+FAIL+WARN} TOTAL")
print(f"{'═'*64}")
fails=[x for x in LOG if x["s"]=="FAIL"]
warns=[x for x in LOG if x["s"]=="WARN"]
if fails:
    print("\n\033[31mFAILURES:\033[0m")
    for f in fails: print(f"  [{f['id']}] {f['lbl']}" + (f"\n       {f['d'][:160]}" if f['d'] else ""))
else:
    print("\n\033[32mAll hard checks passed!\033[0m")
if warns:
    print("\n\033[33mWARNINGS:\033[0m")
    for w in warns: print(f"  [{w['id']}] {w['lbl']}")
print()
