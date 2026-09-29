"""
Comprehensive test: all provided questions + all 6 financial statement templates
in multiple formats + contextual follow-ups.
Backend: http://localhost:8005
"""
import requests, json, time, sys, os

# Force UTF-8 output so Unicode characters (−, ×, etc.) don't crash cp1252
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = 'http://localhost:8008'
CREDS = {'email': 'test@test.com', 'password': 'testtest'}
OUT   = os.path.join(os.path.dirname(__file__), 'test_results.txt')

# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def login():
    r = requests.post(f'{BASE}/api/auth/login', json=CREDS, timeout=30)
    r.raise_for_status()
    return r.json()['access_token']

def ask(token, question, section_label='', log_fh=None):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    label   = section_label or question[:80]
    sep     = '=' * 80
    out     = f'\n{sep}\n{label}\nQ: {question}\n{sep}\n'
    print(out, flush=True)
    if log_fh: log_fh.write(out); log_fh.flush()

    try:
        r = requests.post(f'{BASE}/api/chat/stream', headers=headers,
                          json={'question': question}, stream=True, timeout=180)
        full_response = sql_query = ''
        for line in r.iter_lines():
            if not line: continue
            if isinstance(line, bytes): line = line.decode('utf-8', errors='replace')
            if not line.startswith('data: '): continue
            try:
                payload = json.loads(line[6:])
                t = payload.get('type')
                if t == 'done':
                    full_response = payload.get('full_response', '')
                    sql_query     = payload.get('sql_query', '')
                elif t == 'error':
                    err = f'[ERROR EVENT]: {payload.get("content","")}'
                    print(err, flush=True)
                    if log_fh: log_fh.write(err+'\n'); log_fh.flush()
            except Exception: pass
    except Exception as ex:
        err = f'[REQUEST EXCEPTION]: {ex}'
        print(err, flush=True)
        if log_fh: log_fh.write(err+'\n'); log_fh.flush()
        return

    result = (
        f'SQL:\n{sql_query if sql_query else "(none)"}\n\n'
        f'RESPONSE:\n{full_response if full_response else "(empty)"}\n'
    )
    print(result, flush=True)
    if log_fh: log_fh.write(result); log_fh.flush()
    time.sleep(4)   # small pause between requests

# ─────────────────────────────────────────────────────────────────────────────
# question lists
# ─────────────────────────────────────────────────────────────────────────────

PROVIDED_QUESTIONS = [
    "Do the same analysis by customers for same periods and list top 10 customers with highest variance in march 2025",
    "Monthly sales of 2025 with quantity and profit, what could be profit if Quantity increase by 10% and Sales Prices by 5%, show profit before and after the increase",
    "Aggregate annual sales by customer price categories in 2026",
    "Top 10 sales return reasons, quantities and total returns, for the year 2025.",
    "Prepare an ABC Analysis summary of items on hand , value and quantity",
    "provide list of top 5 items in each ABC categories",
    "How ABC categories are assigned to items for ABC Analysis, what is rationale",
    "monthly sales of january 2026 and its comparison with 2025 , also % increase or decease is required",
    "Monthly sales for January 2026, along with a comparison to January 2025, including the percentage increase or decrease. prepare  a performance card",
    "Provide monthly sales for 2026 vs 2025 for TJ Maxx, Marshalls, Mackenzie Childs, and Williams Sonoma. Calculate the gap to reach 2025 monthly averages and project annual recovery value.",
    "Provide monthly sales for 2026 vs 2025 for top 3 customers on sales basis. Calculate the gap to reach 2025 monthly averages and project annual recovery value.",
    "Analyze sales data for Quince from July to November (historical years). Estimate additional revenue if inventory is fully stocked during peak months and provide expected revenue uplift range.",
    "Calculate total monthly revenue loss across all major accounts based on latest available month vs same month last year. Provide per-account loss and overall loss per month.",
    "Monthly payments by types of payments for 2025",
    "prepare grouped balance sheet as of december 2025",
    "prepare grouped balance sheet as of december 2025, also create group totals as per template of grouped balance sheet",
    "prepare grouped balance sheet as of december 2025, also create group totals as per template of grouped balance sheet, show the totals in grid",
    "Top 10 sales return reasons, quantities and total returns, for the year 2025.",
    "Assign 5 logical groups to customer return reasons for customer returns for 2025. and name other group as not properly entered. show logical groups and no of returns and return quantities",
    "TOP 10 CUSTOMERS BY SALES AMOUNT IN 2025 ALSO ADD THEIR FORECASTED SALES FOR 2026 AND AVERAGE MONTHLY SALES",
    "prepare grouped income statement for december 2025",
    "prepare sub grouped balance sheet as on december 2025 and december 2024 in crosstab columns",
    "sub grouped income statement for 1ST QUARTER OF 2025",
    "Show us the actual sales for march 2024 , foretasted sales march 2025 and actual sales march 2025, what are reasons of major variance?",
    "grouped balance sheet as of december 2024",
    "prepare grouped balance sheet as on june 2025 and july 2025 in crosstab columns",
    "please share balance sheet templates",
    "prepare grouped balance sheet for december 2024 as per grouped template",
    "prepare sub grouped balance sheet as on june 2025 as per sub grouped template",
    "sub grouped pl statement for 2025",
    "grouped pl statement for 2024",
    "grouped pl statement for 2024 using template",
    "sub grouped pl statement for 2024 as per sub grouped template",
    "grouped balance sheet as of december 2024 , grouped template",
    "MAIN grouped balance sheet as of december 2024 , mAIN grouped template",
    "grouped balance as on november 2024",
    "grouped income statement for december 2024",
    "grouped pl statement for december 2024",
    "sub grouped balance sheet as on november 2024",
    "detailed balance sheet as on december 2023",
    "grouped P&L Statement  or income statement for 2023",
    "grouped pl statement for january 2026",
    "sub grouped PL Statement for january 2025 as per template",
    "grouped pl statement for january 2026 as per template",
    "detailed pl statement as per template",
    "Total profit and total sales by top 2 customers for 2026",
    "grouped balance sheet as of december 2024",
    "Prepare an ABC Analysis summary of items on hand , value and quantity, RETURN OUTPUT IN Categories, Quantities and Inventory values",
    "analyze sales frequency of 2025 and categories customer bases on their periodic frequency , return, periodic frequency, no of customers, no sales invoices, sales amounts etc.",
    "Analyze customer payment habits for the 2024 and 2025. Categories based on the how much time they usually take to make payments, What is best time to proceed collections",
    "what are payment types in the system",
]

FINANCIAL_STATEMENT_TESTS = [
    # ── Balance Sheet: Single month, various phrasings ──────────────────────
    ("BS-Main-Jun2024",  "Show me the main grouped balance sheet for June 2024"),
    ("BS-Main-Dec2024",  "Balance sheet main grouped as of December 2024"),
    ("BS-Main-Mar2025",  "Give me the grouped balance sheet for March 2025"),
    ("BS-Sub-Jun2024",   "Show the sub grouped balance sheet for June 2024"),
    ("BS-Sub-Sep2024",   "Sub grouped balance sheet as of September 2024"),
    ("BS-Sub-Jan2025",   "Prepare sub grouped balance sheet for January 2025 as per template"),
    ("BS-Det-Jun2024",   "Show the detailed balance sheet for June 2024"),
    ("BS-Det-Dec2023",   "Detailed balance sheet as of December 2023"),
    ("BS-Det-Aug2024",   "Full detailed balance sheet for August 2024"),

    # ── Balance Sheet: Year-end / full year phrasings ────────────────────────
    ("BS-Main-2024YE",   "Balance sheet as of year end 2024"),
    ("BS-Sub-2023YE",    "Sub grouped balance sheet at the end of 2023"),

    # ── Balance Sheet: Multi-month side-by-side ──────────────────────────────
    ("BS-Main-Multi1",   "Prepare main grouped balance sheet for June 2024 and July 2024 in side-by-side columns"),
    ("BS-Sub-Multi1",    "Sub grouped balance sheet as on November 2024 and December 2024 side by side"),
    ("BS-Det-Multi1",    "Detailed balance sheet for April 2024 and May 2024 in separate columns"),
    ("BS-Main-Multi2",   "Compare main grouped balance sheet for December 2024 vs December 2023"),
    ("BS-Sub-Multi2",    "Sub grouped balance sheet for June 2025 and July 2025 in crosstab columns"),

    # ── Balance Sheet: Context follow-ups ────────────────────────────────────
    ("BS-Follow1",       "Now show the sub grouped version of the same balance sheet"),
    ("BS-Follow2",       "Drill down into the detailed balance sheet from this"),
    ("BS-Follow3",       "What is the working capital based on the above balance sheet?"),
    ("BS-Follow4",       "Which section has the highest value and why is it significant?"),

    # ── P&L / Income Statement: Single month ────────────────────────────────
    ("PL-Main-Jun2024",  "Show me the grouped P&L statement for June 2024"),
    ("PL-Main-Dec2024",  "Grouped income statement for December 2024 as per template"),
    ("PL-Main-Jan2025",  "Grouped P&L for January 2025"),
    ("PL-Main-Dec2023",  "Grouped P&L statement or income statement for December 2023"),
    ("PL-Sub-Jun2024",   "Sub grouped P&L statement for June 2024 as per template"),
    ("PL-Sub-Jan2025",   "Sub grouped income statement for January 2025 as per template"),
    ("PL-Sub-Q12025",    "Sub grouped P&L for the first quarter of 2025 (Jan-Mar 2025)"),
    ("PL-Det-Jun2024",   "Detailed P&L statement for June 2024 as per detailed template"),
    ("PL-Det-Jan2025",   "Detailed income statement for January 2025"),
    ("PL-Det-Dec2024",   "Full detailed P&L for December 2024 as per template"),

    # ── P&L: Full year queries ───────────────────────────────────────────────
    ("PL-Main-2024",     "Grouped P&L statement for full year 2024"),
    ("PL-Main-2025",     "Grouped income statement for 2025"),
    ("PL-Sub-2024",      "Sub grouped P&L for 2024"),
    ("PL-Sub-2023",      "Sub grouped P&L statement for 2023 as per sub grouped template"),

    # ── P&L: Multi-month / range queries ────────────────────────────────────
    ("PL-Main-Multi1",   "Grouped P&L for January 2025 and February 2025 side by side"),
    ("PL-Main-Multi2",   "Compare grouped P&L for June 2024 vs June 2025"),
    ("PL-Sub-Multi1",    "Sub grouped income statement for January and February 2025 in crosstab"),
    ("PL-Det-Multi1",    "Detailed P&L for October 2024 and November 2024 in two columns"),

    # ── P&L: Context follow-ups ──────────────────────────────────────────────
    ("PL-Follow1",       "What is the gross profit margin based on the above P&L?"),
    ("PL-Follow2",       "Which expense category is the highest and what is its percentage of total sales?"),
    ("PL-Follow3",       "Now show me the sub grouped version"),
    ("PL-Follow4",       "Drill into the detailed P&L from this"),
    ("PL-Follow5",       "Compare this result with the previous month"),

    # ── Cross-statement context ───────────────────────────────────────────────
    ("Cross1",           "Now give me the grouped balance sheet for the same period"),
    ("Cross2",           "What is the relationship between the net profit from the P&L and the stockholder equity in the balance sheet?"),
    ("Cross3",           "Show me the sub grouped balance sheet and sub grouped P&L for December 2024 together"),
]

# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f'Logging to: {OUT}', flush=True)
    token = login()
    print(f'Logged in OK (executive role)', flush=True)

    with open(OUT, 'w', encoding='utf-8', errors='replace') as fh:
        fh.write('COMPREHENSIVE TEST RESULTS\n')
        fh.write('=' * 80 + '\n\n')

        # ── PART 1: provided questions ────────────────────────────────────────
        fh.write('\n\n' + '#' * 80 + '\n')
        fh.write('PART 1 — PROVIDED QUESTIONS LIST\n')
        fh.write('#' * 80 + '\n\n')
        print('\n' + '#'*60 + '\nPART 1: PROVIDED QUESTIONS LIST\n' + '#'*60, flush=True)

        for i, q in enumerate(PROVIDED_QUESTIONS, 1):
            ask(token, q, section_label=f'[P1-{i:02d}] {q[:70]}', log_fh=fh)

        # ── PART 2: financial statements ──────────────────────────────────────
        fh.write('\n\n' + '#' * 80 + '\n')
        fh.write('PART 2 — ALL 6 FINANCIAL STATEMENT TEMPLATES (COMPREHENSIVE)\n')
        fh.write('#' * 80 + '\n\n')
        print('\n' + '#'*60 + '\nPART 2: FINANCIAL STATEMENTS\n' + '#'*60, flush=True)

        for (label, q) in FINANCIAL_STATEMENT_TESTS:
            ask(token, q, section_label=f'[{label}] {q[:70]}', log_fh=fh)

        fh.write('\n\nALL TESTS COMPLETE\n')
    print('\nALL TESTS COMPLETE — results in test_results.txt', flush=True)
