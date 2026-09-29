"""
Hardcoded unit tests for _extract_sql_col_names, _build_markdown_table,
and _fix_response_table_pipes.
Run with: python test_pipe_fns.py
"""
import re, sys

# ── Functions under test (copied verbatim from langchain_agent.py) ──────────

def _extract_sql_col_names(sql: str):
    if not sql:
        return []
    upper = sql.upper()
    depth = 0; last_select_pos = -1; i = 0
    while i < len(sql):
        c = sql[i]
        if c == "(": depth += 1
        elif c == ")":
            if depth > 0: depth -= 1
        elif depth == 0 and upper[i:i+6] == "SELECT": last_select_pos = i
        i += 1
    if last_select_pos == -1: return []
    depth = 0; from_pos = -1; i = last_select_pos + 6
    while i < len(sql):
        c = sql[i]
        if c == "(": depth += 1
        elif c == ")":
            if depth > 0: depth -= 1
        elif depth == 0 and upper[i:i+5] in (" FROM", "\tFROM", "\nFROM"):
            from_pos = i; break
        i += 1
    if from_pos == -1: return []
    select_clause = sql[last_select_pos + 6:from_pos].strip()
    select_clause = re.sub(r"^TOP\s+\d+\s+", "", select_clause, flags=re.IGNORECASE).strip()
    items = []; depth = 0; current = ""
    for char in select_clause:
        if char == "(": depth += 1; current += char
        elif char == ")": depth -= 1; current += char
        elif char == "," and depth == 0: items.append(current.strip()); current = ""
        else: current += char
    if current.strip(): items.append(current.strip())
    names = []
    for item in items:
        item = item.strip()
        as_match = re.search(r"\bAS\b\s+([`\"\[]?[\w]+[`\"\]]?)\s*$", item, re.IGNORECASE)
        if as_match:
            names.append(as_match.group(1).strip("`\"[]"))
        else:
            parts = item.split()
            if parts:
                last = parts[-1].strip("`\"[]")
                if "." in last: last = last.split(".")[-1]
                names.append(last if last and last != "*" else f"Col{len(names)+1}")
    return names


def _is_numeric(col, data):
    for r in data:
        v = str(r.get(col, "")).strip().lstrip("-").replace(",", "").replace(".", "", 1)
        if v and not v.isdigit(): return False
    return bool(data)


def _build_markdown_table(columns, data):
    if not columns or not data: return ""
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "|" + "|".join("---:" if _is_numeric(c, data) else ":---" for c in columns) + "|"
    rows = []
    for row in data:
        cells = [str(row.get(c, "")).replace("|", "\\|") for c in columns]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep] + rows)


def _fix_response_table_pipes(response, captured_cols, captured_data):
    if not captured_data or not captured_cols: return response
    lines = response.splitlines(); result = []; i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            block = []
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("|") and s.endswith("|"): block.append(lines[i]); i += 1
                else: break
            hdr = block[0].strip().strip("|")
            header_cells = [c.strip() for c in hdr.split("|") if c.strip()]
            if len(header_cells) == len(captured_cols) and len(block) >= 2:
                lm_data_row_count = len(block) - 2
                if lm_data_row_count > len(captured_data):
                    result.extend(block)
                else:
                    def _is_num_col(col):
                        for r in captured_data:
                            v = str(r.get(col, "")).strip().lstrip("-").replace(",", "").replace(".", "", 1)
                            if v and not v.isdigit(): return False
                        return bool(captured_data)
                    sep_parts = ["---:" if _is_num_col(col) else ":---" for col in captured_cols]
                    result.append("| " + " | ".join(str(c) for c in captured_cols) + " |")
                    result.append("| " + " | ".join(sep_parts) + " |")
                    for row in captured_data:
                        cells = [str(row.get(col, "")).replace("|", "\\|") for col in captured_cols]
                        result.append("| " + " | ".join(cells) + " |")
            else:
                result.extend(block)
        else:
            result.append(lines[i]); i += 1
    return "\n".join(result)


# ── Test runner ──────────────────────────────────────────────────────────────

PASS = FAIL = 0

def check(label, got, expected):
    global PASS, FAIL
    if got == expected:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}")
        print(f"         Expected : {repr(expected)}")
        print(f"         Got      : {repr(got)}")
        FAIL += 1

# ═══════════════════════════════════════════════════════════════════════════
print("\n══════════════════════════════════════════")
print(" GROUP 1 — _extract_sql_col_names")
print("══════════════════════════════════════════")

check("1A Simple aliases",
    _extract_sql_col_names("SELECT Category, COUNT(*) AS CustomerCount, MIN(CustomerName) AS ExampleCustomer FROM DimCustomer GROUP BY Category"),
    ["Category", "CustomerCount", "ExampleCustomer"])

check("1B TOP N stripped",
    _extract_sql_col_names("SELECT TOP 40 Category, COUNT(*) AS CustomerCount FROM DimCustomer GROUP BY Category ORDER BY Category"),
    ["Category", "CustomerCount"])

check("1C Table-prefix columns",
    _extract_sql_col_names("SELECT TOP 40 DC.CustomerID, DC.CustomerName, SUM(FSI.Amount) AS TotalSales FROM DimCustomer DC JOIN FactSalesInvoice FSI ON DC.CustomerKey=FSI.CustomerKey GROUP BY DC.CustomerID, DC.CustomerName"),
    ["CustomerID", "CustomerName", "TotalSales"])

check("1D CTE — final outer SELECT",
    _extract_sql_col_names(
        "WITH CustomerSpend AS (\n"
        "    SELECT CustomerKey, SUM(Amount) AS Spend FROM FactSalesInvoice GROUP BY CustomerKey\n"
        ")\n"
        "SELECT TOP 40 DC.CustomerName, CS.Spend AS TotalSpend, CS.Spend * 0.1 AS Commission\n"
        "FROM CustomerSpend CS JOIN DimCustomer DC ON CS.CustomerKey=DC.CustomerKey"),
    ["CustomerName", "TotalSpend", "Commission"])

check("1E Multi-CTE",
    _extract_sql_col_names(
        "WITH A AS (SELECT X FROM T1), B AS (SELECT Y FROM T2)\n"
        "SELECT TOP 10 A.X AS ColA, B.Y AS ColB FROM A JOIN B ON A.id=B.id"),
    ["ColA", "ColB"])

check("1F Bare columns no alias",
    _extract_sql_col_names("SELECT CustomerID, CustomerName FROM DimCustomer"),
    ["CustomerID", "CustomerName"])

check("1G CASE WHEN with alias",
    _extract_sql_col_names(
        "SELECT TOP 40 DC.CustomerID, "
        "SUM(CASE WHEN DD.Year=2025 THEN FSI.Amount ELSE 0 END) AS Sales2025, "
        "COUNT(*) AS TxCount "
        "FROM DimCustomer DC JOIN FactSalesInvoice FSI ON DC.CustomerKey=FSI.CustomerKey "
        "JOIN DimDate DD ON FSI.DateKey=DD.DateKey GROUP BY DC.CustomerID"),
    ["CustomerID", "Sales2025", "TxCount"])

check("1H Logical groups CTE (customer return scenario)",
    _extract_sql_col_names(
        "WITH UniqueReasons AS (SELECT FCRD.ReturnReason, COUNT(*) AS ReturnCount FROM FactCustomerReturnDetail FCRD GROUP BY FCRD.ReturnReason),\n"
        "LogicalGroups AS (SELECT CASE WHEN ReturnReason LIKE '%DEFECT%' THEN 'Defective' ELSE 'Other' END AS LogicalGroup, SUM(ReturnCount) AS NumberOfReturns FROM UniqueReasons GROUP BY CASE WHEN ReturnReason LIKE '%DEFECT%' THEN 'Defective' ELSE 'Other' END)\n"
        "SELECT TOP 40 LogicalGroup, NumberOfReturns, TotalReturnQty FROM LogicalGroups WHERE TotalReturnQty > 0 ORDER BY TotalReturnQty DESC"),
    ["LogicalGroup", "NumberOfReturns", "TotalReturnQty"])

check("1I Empty string", _extract_sql_col_names(""), [])
check("1J No FROM clause", _extract_sql_col_names("SELECT 1+1"), [])

# ═══════════════════════════════════════════════════════════════════════════
print("\n══════════════════════════════════════════")
print(" GROUP 2 — _build_markdown_table alignment")
print("══════════════════════════════════════════")

cols = ["Name", "City"]
data = [{"Name": "Alice", "City": "Nashville"}]
check("2A All text → left-aligned", "|:---|:---|" in _build_markdown_table(cols, data), True)

cols = ["Amount", "Qty"]
data = [{"Amount": "1234.56", "Qty": "10"}]
check("2B All numeric → right-aligned", "|---:|---:|" in _build_markdown_table(cols, data), True)

cols = ["CustomerName", "TotalSales", "Region"]
data = [{"CustomerName": "Acme", "TotalSales": "50000.00", "Region": "South"},
        {"CustomerName": "Beta", "TotalSales": "30000.00", "Region": "North"}]
check("2C Mixed separator", _build_markdown_table(cols, data).splitlines()[1], "|:---|---:|:---|")

cols = ["Account", "Balance"]
data = [{"Account": "Cash", "Balance": "-15000.00"}, {"Account": "Loan", "Balance": "-5000.00"}]
check("2D Negative numbers → right-aligned", "|:---|---:|" in _build_markdown_table(cols, data), True)

cols = ["Revenue"]
data = [{"Revenue": "1,234,567.89"}, {"Revenue": "999,000.00"}]
check("2E Comma-formatted numbers → right-aligned", "|---:|" in _build_markdown_table(cols, data), True)

check("2F Empty data returns empty string", _build_markdown_table(["Col"], []), "")

cols = ["Description", "Amount"]
data = [{"Description": "Sales|Returns", "Amount": "100.00"}]
check("2G Pipe in cell escaped", "Sales\\|Returns" in _build_markdown_table(cols, data), True)

cols = ["Category", "CustomerCount", "ExampleCustomer"]
data = [{"Category": "1", "CustomerCount": "2988", "ExampleCustomer": "Create With Love"},
        {"Category": "12", "CustomerCount": "47", "ExampleCustomer": "ABINGDON RUG OUTLET"}]
t = _build_markdown_table(cols, data).splitlines()
check("2H Category table — header correct", t[0], "| Category | CustomerCount | ExampleCustomer |")
# Category values ("1","12") are all-digit so function right-aligns them too — correct
check("2H Category table — separator (num|num|text)", t[1], "|---:|---:|:---|")
check("2H Category table — first data row", t[2], "| 1 | 2988 | Create With Love |")

# ═══════════════════════════════════════════════════════════════════════════
print("\n══════════════════════════════════════════")
print(" GROUP 3 — _fix_response_table_pipes")
print("══════════════════════════════════════════")

# 3A: Column swap — AI wrong header order, SQL data correct → fix overwrites
ai_table = ("| Category ID | Example Customer Name | Customer Count |\n"
            "|:---|:---|---:|\n"
            "| 1 | 2988 | Create With Love |\n"
            "| 12 | 47 | ABINGDON RUG OUTLET |")
cols = ["Category", "CustomerCount", "ExampleCustomer"]
data = [{"Category": "1", "CustomerCount": "2988", "ExampleCustomer": "Create With Love"},
        {"Category": "12", "CustomerCount": "47", "ExampleCustomer": "ABINGDON RUG OUTLET"}]
f = _fix_response_table_pipes(ai_table, cols, data).splitlines()
check("3A Header uses real SQL names", f[0], "| Category | CustomerCount | ExampleCustomer |")
check("3A Numeric col right-aligned", "---:" in f[1], True)
check("3A Text col left-aligned", ":---" in f[1], True)
check("3A Data row 1 correct", f[2], "| 1 | 2988 | Create With Love |")
check("3A Data row 2 correct", f[3], "| 12 | 47 | ABINGDON RUG OUTLET |")

# 3B: Financial statement — more LLM rows than SQL rows → preserve entirely
ai_fin = ("| Description | Amount ($) |\n"
          "|:---|---:|\n"
          "| Gross Sales | 1000.00 |\n"
          "| Returns | -100.00 |\n"
          "| **Total Sales** | 900.00 |\n"
          "| Net Profit | 200.00 |")
cols_fin = ["Description", "Amount"]
data_fin = [{"Description": "Gross Sales", "Amount": "1000.00"},
            {"Description": "Returns", "Amount": "-100.00"}]  # 2 SQL rows < 4 LLM rows
check("3B Financial statement preserved unchanged",
    _fix_response_table_pipes(ai_fin, cols_fin, data_fin), ai_fin)

# 3C: Pipe inside a cell value → escaped
ai_p = "| Product | Notes |\n|:---|:---|\n| Rug | Old value |"
cols_p = ["Product", "Notes"]
data_p = [{"Product": "Rug", "Notes": "Color: Red|Blue"}]
check("3C Pipe in cell escaped", "Red\\|Blue" in _fix_response_table_pipes(ai_p, cols_p, data_p), True)

# 3D: Column count mismatch → table left untouched
ai_m = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
check("3D Column mismatch — table unchanged",
    _fix_response_table_pipes(ai_m, ["X", "Y"], [{"X": "10", "Y": "20"}]), ai_m)

# 3E: Non-table text preserved around fixed table
response = "Here are the results:\n\n| Name | Sales |\n|:---|---:|\n| Acme | 5000 |\n\nEnd of report."
cols_t = ["Name", "Sales"]
data_t = [{"Name": "Acme Corp", "Sales": "5000"}]
fixed = _fix_response_table_pipes(response, cols_t, data_t)
check("3E Text before preserved", fixed.startswith("Here are the results:"), True)
check("3E Text after preserved", fixed.strip().endswith("End of report."), True)
check("3E Cell updated from captured data", "Acme Corp" in fixed, True)

# 3F: Empty captured data → response unchanged
check("3F Empty captured data — no change",
    _fix_response_table_pipes("| A |\n|---|\n| 1 |", ["A"], []), "| A |\n|---|\n| 1 |")

# 3G: Multiple tables in one response — only the matching one rebuilt
response_multi = ("| Name | Sales |\n|:---|---:|\n| Old | 0 |\n\n"
                  "Some text.\n\n"
                  "| Product | Qty | Price |\n|:---|---:|---:|\n| Widget | 10 | 5 |")
cols_g = ["Name", "Sales"]
data_g = [{"Name": "Acme", "Sales": "9999"}]
fixed_g = _fix_response_table_pipes(response_multi, cols_g, data_g)
check("3G Multi-table — first table rebuilt", "Acme" in fixed_g, True)
check("3G Multi-table — second table untouched (col mismatch)", "Widget" in fixed_g, True)

# ═══════════════════════════════════════════════════════════════════════════
print("\n══════════════════════════════════════════")
print(" GROUP 4 — layout combinations (text/table ordering)")
print("══════════════════════════════════════════")

cols_s = ["Name", "Revenue"]
data_s = [{"Name": "Acme", "Revenue": "5000"}, {"Name": "Beta", "Revenue": "3000"}]

# 4A: Text ONLY — no table → unchanged
resp = "Here is a summary with no table at all."
check("4A Text only — unchanged", _fix_response_table_pipes(resp, cols_s, data_s), resp)

# 4B: Table ONLY — rebuilt correctly
resp = "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |"
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
lines = fixed.splitlines()
check("4B Table only — header correct", lines[0], "| Name | Revenue |")
check("4B Table only — row 1 correct", lines[2], "| Acme | 5000 |")
check("4B Table only — row 2 correct", lines[3], "| Beta | 3000 |")

# 4C: Text BEFORE table
resp = "Here are the results:\n\n| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |"
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4C Text before — text preserved", fixed.startswith("Here are the results:"), True)
check("4C Text before — data updated", "Acme" in fixed, True)

# 4D: Text AFTER table
resp = "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |\n\nEnd of report."
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4D Text after — text preserved", fixed.strip().endswith("End of report."), True)
check("4D Text after — data updated", "Acme" in fixed, True)

# 4E: Text BEFORE and AFTER table
resp = "Summary paragraph.\n\n| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |\n\nFooter note."
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4E Text before+after — before preserved", "Summary paragraph." in fixed, True)
check("4E Text before+after — after preserved", "Footer note." in fixed, True)
check("4E Text before+after — data updated", "Acme" in fixed, True)

# 4F: Multiple paragraphs of text, then table, then more text
resp = ("Line one.\nLine two.\n\nLine three.\n\n"
        "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |\n\n"
        "Closing remarks.\nMore closing.")
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4F Multi-para text before — preserved", "Line one." in fixed and "Line three." in fixed, True)
check("4F Multi-para text after — preserved", "Closing remarks." in fixed, True)
check("4F Multi-para — data updated", "Beta" in fixed, True)

# 4G: TWO tables in response — first matches, second doesn't (col count differs)
cols_first = ["Product", "Qty"]
data_first = [{"Product": "Widget", "Qty": "99"}]
resp = ("| Product | Qty |\n|:---|---:|\n| Old | 0 |\n\n"
        "Some text in the middle.\n\n"
        "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |")
fixed = _fix_response_table_pipes(resp, cols_first, data_first)
check("4G Two tables — first rebuilt", "Widget" in fixed, True)
check("4G Two tables — second unchanged (col mismatch)", "| A | B | C |" in fixed, True)
check("4G Two tables — middle text preserved", "Some text in the middle." in fixed, True)

# 4H: TWO tables — first doesn't match (col count), second matches
cols_second = ["A", "B", "C"]
data_second = [{"A": "X", "B": "Y", "C": "Z"}]
resp = ("| Product | Qty |\n|:---|---:|\n| Old | 0 |\n\n"
        "Middle text.\n\n"
        "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |")
fixed = _fix_response_table_pipes(resp, cols_second, data_second)
check("4H Two tables — first unchanged (col mismatch)", "| Product | Qty |" in fixed, True)
check("4H Two tables — second rebuilt", "| X | Y | Z |" in fixed, True)

# 4I: Table immediately followed by text on next line (no blank line gap)
resp = "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |\nFooter with no blank line."
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4I No blank line after table — footer preserved", "Footer with no blank line." in fixed, True)
check("4I No blank line after table — data updated", "Acme" in fixed, True)

# 4J: Bullet-point analysis BEFORE table (the insights use-case)
resp = ("Key findings:\n"
        "- Revenue declined 10%\n"
        "- Payroll is the largest cost\n\n"
        "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |")
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4J Bullet analysis before — preserved", "- Revenue declined 10%" in fixed, True)
check("4J Bullet analysis before — table data updated", "Acme" in fixed, True)

# 4K: Bold headers in text (financial statement narrative style)
resp = ("**Sales Performance**\nGross sales were strong.\n\n"
        "| Name | Revenue |\n|:---|---:|\n| Old | 0 |\n| Old2 | 0 |\n\n"
        "**Conclusion**\nOverall positive.")
fixed = _fix_response_table_pipes(resp, cols_s, data_s)
check("4K Bold headers in text — preserved", "**Sales Performance**" in fixed, True)
check("4K Bold headers in text — conclusion preserved", "**Conclusion**" in fixed, True)
check("4K Bold headers in text — data updated", "Acme" in fixed, True)

# 4L: Table with a pipe character in a cell value — cross-column safety
cols_l = ["Description", "Category", "Amount"]
data_l = [{"Description": "A|B split", "Category": "Sales", "Amount": "1000"},
          {"Description": "Normal", "Category": "COGS", "Amount": "500"}]
resp = "| Description | Category | Amount |\n|:---|:---|---:|\n| Old | Old | 0 |\n| Old2 | Old2 | 0 |"
fixed = _fix_response_table_pipes(resp, cols_l, data_l)
check("4L Pipe in first-col cell — escaped", "A\\|B split" in fixed, True)
check("4L Pipe in first-col cell — second row intact", "Normal" in fixed, True)
check("4L Pipe in first-col cell — amount column present", "1000" in fixed, True)

# ═══════════════════════════════════════════════════════════════════════════
print(f"\n══════════════════════════════════════════")
print(f" RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests")
print(f"══════════════════════════════════════════\n")
sys.exit(0 if FAIL == 0 else 1)
