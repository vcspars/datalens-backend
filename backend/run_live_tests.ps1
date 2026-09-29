
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWVhMWNlMzFkMWJkZGZkZmI0OGIzNDUiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJyb2xlIjoiZXhlY3V0aXZlIiwiZXhwIjoxNzc4MTM5NDQ3fQ.vDmQa9FJUQTmn4cDipI-cMyQMlpSldSv2TZEb8sLgZ0"
$BASE = "http://localhost:8008/api"
$PASS = 0; $FAIL = 0; $WARN = 0
$LOG = @()

function Invoke-Chat {
    param([string]$Q, [int]$TimeoutSec = 180)
    $body = [System.Text.Encoding]::UTF8.GetBytes(("{`"question`":`"" + ($Q -replace '"','\"') + "`"}"))
    $req = [System.Net.WebRequest]::Create("$BASE/chat/stream")
    $req.Method = "POST"; $req.ContentType = "application/json"
    $req.Headers.Add("Authorization", "Bearer $TOKEN")
    $req.Accept = "text/event-stream"; $req.Timeout = $TimeoutSec * 1000
    $req.ContentLength = $body.Length
    $ws = $req.GetRequestStream(); $ws.Write($body,0,$body.Length); $ws.Close()
    $resp = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    $fullResp = ""; $sqlQ = ""; $deadline = [DateTime]::Now.AddSeconds($TimeoutSec)
    while (-not $reader.EndOfStream -and [DateTime]::Now -lt $deadline) {
        $line = $reader.ReadLine()
        if ($line -match "^data: (.+)$") {
            try {
                $j = $matches[1] | ConvertFrom-Json
                if ($j.type -eq "done") { $fullResp = $j.full_response; $sqlQ = $j.sql_query; break }
            } catch {}
        }
    }
    $reader.Close(); $resp.Close()
    return @{ Response = $fullResp; SQL = $sqlQ }
}

function Log-Test {
    param([string]$ID, [string]$Label, [string]$Status, [string]$Detail, [string]$Extra="")
    $script:LOG += [PSCustomObject]@{ ID=$ID; Label=$Label; Status=$Status; Detail=$Detail; Extra=$Extra }
    $color = if ($Status -eq "PASS") { "Green" } elseif ($Status -eq "FAIL") { "Red" } else { "Yellow" }
    Write-Host "  [$Status] $ID — $Label" -ForegroundColor $color
    if ($Detail) { Write-Host "          $Detail" -ForegroundColor Gray }
    if ($Status -eq "PASS") { $script:PASS++ } elseif ($Status -eq "FAIL") { $script:FAIL++ } else { $script:WARN++ }
}

function Contains-SQL { param([string]$R) return ($R -match "(?i)\bSELECT\b" -and $R -match "(?i)\bFROM\b") }
function Has-Table    { param([string]$R) return $R -match "\|:?---" }
function No-SQL       { param([string]$R) return -not (Contains-SQL $R) }

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP A — SQL-LEAK / TRICKY QUERIES" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# A1: Exact failing query from the report
Write-Host "`n[A1] Logical groups / CASE WHEN classification..." -ForegroundColor White
$a1 = Invoke-Chat "Assign 5 logical groups to customer return reasons for customer returns for 2025. Name other group as 'not properly entered'. Show logical groups, number of returns and return quantities."
Log-Test "A1a" "No raw SQL in response"    $(if (No-SQL $a1.Response) {"PASS"} else {"FAIL"}) "Response starts: $($a1.Response.Substring(0,[Math]::Min(120,$a1.Response.Length)))"
Log-Test "A1b" "Has table in response"     $(if (Has-Table $a1.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "A1c" "SQL was captured (executed)" $(if ($a1.SQL) {"PASS"} else {"WARN"}) "SQL len=$($a1.SQL.Length)"
Write-Host "     SQL: $($a1.SQL.Substring(0,[Math]::Min(200,$a1.SQL.Length)))..." -ForegroundColor DarkGray

# A2: "Write me a query" phrasing — classic SQL-trigger phrase
Write-Host "`n[A2] 'Write me a query' phrasing..." -ForegroundColor White
$a2 = Invoke-Chat "Write me a query to show total sales by customer for 2025, ranked by highest sales first."
Log-Test "A2a" "No raw SQL in response"  $(if (No-SQL $a2.Response) {"PASS"} else {"FAIL"}) "Response: $($a2.Response.Substring(0,[Math]::Min(200,$a2.Response.Length)))"
Log-Test "A2b" "Has table"               $(if (Has-Table $a2.Response) {"PASS"} else {"WARN"}) ""

# A3: "Build/create a report" phrasing
Write-Host "`n[A3] 'Build a report' phrasing..." -ForegroundColor White
$a3 = Invoke-Chat "Build a report showing top 10 products by revenue for 2024 with their quantities sold."
Log-Test "A3a" "No raw SQL in response"  $(if (No-SQL $a3.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "A3b" "Has table"               $(if (Has-Table $a3.Response) {"PASS"} else {"WARN"}) ""

# A4: "Generate SQL" — deliberately asks for SQL
Write-Host "`n[A4] Explicit 'generate SQL' request..." -ForegroundColor White
$a4 = Invoke-Chat "Generate SQL to segment customers into 3 tiers based on total 2024 spend using NTILE."
Log-Test "A4a" "No raw SQL in response"  $(if (No-SQL $a4.Response) {"PASS"} else {"FAIL"}) "Response: $($a4.Response.Substring(0,[Math]::Min(200,$a4.Response.Length)))"
Log-Test "A4b" "Has table or answer"     $(if ($a4.Response.Length -gt 50) {"PASS"} else {"WARN"}) ""

# A5: Multi-CTE classification with OUTER APPLY pattern
Write-Host "`n[A5] Customer segmentation multi-CTE (the reported drifting query)..." -ForegroundColor White
$a5 = Invoke-Chat "Segment our customers in DimCustomer into tiers based on total lifetime 5 years spend from FactSalesInvoice. Cross-reference with FactCreditMemo to identify high-value customers who also have a high return rate. What is the Net Value of these customers?"
Log-Test "A5a" "No raw SQL in response"  $(if (No-SQL $a5.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "A5b" "Has table"               $(if (Has-Table $a5.Response) {"PASS"} else {"WARN"}) ""
Log-Test "A5c" "OUTER APPLY used (not GROUP BY category)"  $(if ($a5.SQL -match "OUTER APPLY|TOP 1") {"PASS"} else {"WARN"}) "SQL snippet: $($a5.SQL.Substring(0,[Math]::Min(300,$a5.SQL.Length)))"

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP B — COLUMN SWAP + ALIGNMENT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# B1: Customer categories (the exact reported column swap)
Write-Host "`n[B1] Customer categories — column swap check..." -ForegroundColor White
$b1 = Invoke-Chat "Show me the customer categories in DimCustomer — their IDs, how many customers are in each, and an example customer name."
Log-Test "B1a" "No raw SQL"       $(if (No-SQL $b1.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "B1b" "Has table"        $(if (Has-Table $b1.Response) {"PASS"} else {"WARN"}) ""
# Check that count column doesn't appear in customer name position
$b1lines = $b1.Response -split "`n" | Where-Object { $_ -match "^\|" -and $_ -notmatch ":---" -and $_ -notmatch "Category" }
$b1_swap = $false
foreach ($row in $b1lines) {
    $cells = ($row.Trim().Trim("|") -split "\|") | ForEach-Object { $_.Trim() }
    if ($cells.Count -ge 3 -and $cells[1] -match "^\d+$" -and $cells[2] -notmatch "^\d+$") { } # OK: col2=count, col3=name
    elseif ($cells.Count -ge 3 -and $cells[2] -match "^\d+$" -and $cells[1] -notmatch "^\d+$") { $b1_swap = $true } # SWAPPED
}
Log-Test "B1c" "Column order correct (count before name)"  $(if (-not $b1_swap) {"PASS"} else {"FAIL"}) ""

# B2: Multiple aggregates — verify right-alignment on numeric cols
Write-Host "`n[B2] Multi-aggregate query — alignment check..." -ForegroundColor White
$b2 = Invoke-Chat "Show me top 10 customers by total sales in 2025 with their order count and average order value."
Log-Test "B2a" "No raw SQL"   $(if (No-SQL $b2.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "B2b" "Has table"    $(if (Has-Table $b2.Response) {"PASS"} else {"WARN"}) ""
Log-Test "B2c" "Numeric cols right-aligned (---:)"  $(if ($b2.Response -match "---:") {"PASS"} else {"WARN"}) ""

# B3: COUNT + SUM + MIN + MAX in single query
Write-Host "`n[B3] COUNT + SUM + MIN + MAX cross-column..." -ForegroundColor White
$b3 = Invoke-Chat "For each product category, show: number of products, total units sold in 2025, minimum unit price, maximum unit price."
Log-Test "B3a" "No raw SQL"   $(if (No-SQL $b3.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "B3b" "Has table"    $(if (Has-Table $b3.Response) {"PASS"} else {"WARN"}) ""
Log-Test "B3c" "4 data columns present"  $(if ($b3.Response -match "\|.*\|.*\|.*\|.*\|") {"PASS"} else {"WARN"}) ""

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP C — HISTORY CONSISTENCY (ISSUE 1 — same query twice)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n[C1] Same complex query run twice — SQL consistency check..." -ForegroundColor White
$cq = "Segment our customers into tiers based on total 5-year lifetime spend. Cross-reference with FactCreditMemo to find high-value customers with return rate above 20%. Show net value and top return product category."
$c1a = Invoke-Chat $cq
$c1b = Invoke-Chat $cq
$sqlMatch = ($c1a.SQL -eq $c1b.SQL)
Log-Test "C1a" "Run1 has table"   $(if (Has-Table $c1a.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "C1b" "Run2 has table"   $(if (Has-Table $c1b.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "C1c" "Both runs produce same SQL (Issue 1)"  $(if ($sqlMatch) {"PASS"} else {"FAIL"}) "SQL identical: $sqlMatch"
if (-not $sqlMatch) {
    Write-Host "     RUN1 SQL: $($c1a.SQL.Substring(0,[Math]::Min(300,$c1a.SQL.Length)))" -ForegroundColor DarkYellow
    Write-Host "     RUN2 SQL: $($c1b.SQL.Substring(0,[Math]::Min(300,$c1b.SQL.Length)))" -ForegroundColor DarkYellow
}

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP D — CROSS-TAB / MULTI-COLUMN ANALYTICAL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# D1: Quarterly breakdown
Write-Host "`n[D1] Quarterly breakdown multi-column..." -ForegroundColor White
$d1 = Invoke-Chat "Show me total sales, total returns, and net revenue by quarter for 2024. Include the return rate as a percentage."
Log-Test "D1a" "No raw SQL"    $(if (No-SQL $d1.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "D1b" "Has table"     $(if (Has-Table $d1.Response) {"PASS"} else {"WARN"}) ""
Log-Test "D1c" "Q1/Q2/Q3/Q4 present"  $(if ($d1.Response -match "Q1|Q2|Q3|Q4|Quarter") {"PASS"} else {"WARN"}) ""

# D2: Year-over-year comparison
Write-Host "`n[D2] Year-over-year multi-column comparison..." -ForegroundColor White
$d2 = Invoke-Chat "Compare total sales, total COGS, and gross profit for 2023 vs 2024. Show the YoY change in dollars and percentage."
Log-Test "D2a" "No raw SQL"    $(if (No-SQL $d2.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "D2b" "Has table"     $(if (Has-Table $d2.Response) {"PASS"} else {"WARN"}) ""
Log-Test "D2c" "Both years present"  $(if ($d2.Response -match "2023" -and $d2.Response -match "2024") {"PASS"} else {"WARN"}) ""

# D3: Cross-tab: product category by region/warehouse
Write-Host "`n[D3] Product × category breakdown..." -ForegroundColor White
$d3 = Invoke-Chat "Show me sales revenue broken down by product category for Q1 and Q2 of 2025 side by side."
Log-Test "D3a" "No raw SQL"    $(if (No-SQL $d3.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "D3b" "Has table"     $(if (Has-Table $d3.Response) {"PASS"} else {"WARN"}) ""

# D4: Complex multi-join
Write-Host "`n[D4] Multi-join: customers × products × returns..." -ForegroundColor White
$d4 = Invoke-Chat "For the top 10 customers by 2025 sales, show their total spend, total credit memo amount, net value, and which product category has the most returns for each."
Log-Test "D4a" "No raw SQL"    $(if (No-SQL $d4.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "D4b" "Has table"     $(if (Has-Table $d4.Response) {"PASS"} else {"WARN"}) ""
Log-Test "D4c" "OUTER APPLY or TOP 1 used for top category" $(if ($d4.SQL -match "OUTER APPLY|TOP 1") {"PASS"} else {"WARN"}) ""

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP E — ANALYSIS + TABLE COMBINED (INSIGHTS)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# E1: Analysis requested → must have commentary BEFORE table
Write-Host "`n[E1] Analysis + table: insights + data..." -ForegroundColor White
$e1 = Invoke-Chat "Show me the top 10 customers by 2025 net sales and share key findings and areas that require attention."
$e1_tablePos = $e1.Response.IndexOf("|")
$e1_textBefore = if ($e1_tablePos -gt 0) { $e1.Response.Substring(0, $e1_tablePos).Trim() } else { "" }
Log-Test "E1a" "No raw SQL"                $(if (No-SQL $e1.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "E1b" "Has table"                 $(if (Has-Table $e1.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "E1c" "Commentary before table"   $(if ($e1_textBefore.Length -gt 80) {"PASS"} else {"FAIL"}) "Text before table: $($e1_textBefore.Length) chars"

# E2: Pure data request → NO commentary before table
Write-Host "`n[E2] Pure data request → table only, no commentary..." -ForegroundColor White
$e2 = Invoke-Chat "Top 10 customers by total sales in 2025."
$e2_tablePos = $e2.Response.IndexOf("|")
$e2_textBefore = if ($e2_tablePos -gt 0) { $e2.Response.Substring(0, $e2_tablePos).Trim() } else { "" }
Log-Test "E2a" "No raw SQL"                $(if (No-SQL $e2.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "E2b" "Has table"                 $(if (Has-Table $e2.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "E2c" "No unsolicited commentary" $(if ($e2_textBefore.Length -lt 100) {"PASS"} else {"WARN"}) "Text before table: '$e2_textBefore'"

# E3: Annual P&L with insights (the original fix test)
Write-Host "`n[E3] Annual P&L with insights (core fix)..." -ForegroundColor White
$e3 = Invoke-Chat "Annual PL sub grouped pl statement for 2023, 2024 and 2025 share key findings and areas that require attention"
Log-Test "E3a" "No raw SQL"                $(if (No-SQL $e3.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "E3b" "3-year pivot table present" $(if ($e3.Response -match "2023.*2024.*2025") {"PASS"} else {"FAIL"}) ""
Log-Test "E3c" "Commentary before table"   $(if ($e3.Response.IndexOf("|") -gt 100) {"PASS"} else {"FAIL"}) ""
Log-Test "E3d" "No raw SQL row dump"       $(if ($e3.Response -notmatch "\| Cost Of Goods Sold \| Cost of Goods Sold \| 202") {"PASS"} else {"FAIL"}) ""

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " GROUP F — CONFUSING / TRICKY CONTEXTUAL FOLLOW-UPS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# F1: Vague follow-up "same but for vendors"
Write-Host "`n[F1] Vague follow-up: same but for vendors..." -ForegroundColor White
$f1_base = Invoke-Chat "Show me top 10 customers by total sales in 2025."
$f1_followup = Invoke-Chat "Now same but for vendors instead of customers."
Log-Test "F1a" "Base: no raw SQL"     $(if (No-SQL $f1_base.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "F1b" "Follow-up: no raw SQL" $(if (No-SQL $f1_followup.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "F1c" "Follow-up: has table" $(if (Has-Table $f1_followup.Response) {"PASS"} else {"WARN"}) ""
Log-Test "F1d" "Follow-up: vendor data present" $(if ($f1_followup.Response -match "Vendor|Supplier|vendor") {"PASS"} else {"WARN"}) ""

# F2: "Filter that by 2024" contextual follow-up
Write-Host "`n[F2] Contextual filter follow-up..." -ForegroundColor White
$f2_base = Invoke-Chat "Show me top 10 products by total revenue."
$f2_followup = Invoke-Chat "Now filter that to only 2024 data and add the gross margin percentage."
Log-Test "F2a" "Follow-up: no raw SQL" $(if (No-SQL $f2_followup.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "F2b" "Follow-up: has table" $(if (Has-Table $f2_followup.Response) {"PASS"} else {"WARN"}) ""
Log-Test "F2c" "Follow-up: 2024 in SQL" $(if ($f2_followup.SQL -match "2024") {"PASS"} else {"WARN"}) ""

# F3: Dramatic confusing phrasing — "show me what SQL you would use"
Write-Host "`n[F3] Trick: 'show me the SQL you would use'..." -ForegroundColor White
$f3 = Invoke-Chat "Show me what SQL you would use to find the top 5 customers with the highest return rates in 2025, then show me the results."
Log-Test "F3a" "No raw SQL leaked as response" $(if (No-SQL $f3.Response) {"PASS"} else {"FAIL"}) "Response: $($f3.Response.Substring(0,[Math]::Min(200,$f3.Response.Length)))"
Log-Test "F3b" "Has actual data table" $(if (Has-Table $f3.Response) {"PASS"} else {"WARN"}) ""

# F4: Misleading "don't use SQL, just tell me" phrasing
Write-Host "`n[F4] Trick: 'without SQL, just tell me the numbers'..." -ForegroundColor White
$f4 = Invoke-Chat "Without writing any SQL, just tell me the total revenue for 2025 and how it compares to 2024."
Log-Test "F4a" "No raw SQL"   $(if (No-SQL $f4.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "F4b" "Has numbers"  $(if ($f4.Response -match "\$|[0-9]{3,}") {"PASS"} else {"WARN"}) ""

# F5: Ultra-complex: cohort + retention + category breakdown
Write-Host "`n[F5] Ultra-complex cohort + multi-dimension..." -ForegroundColor White
$f5 = Invoke-Chat "Find customers who placed their first order in Q1 2024. For each of those customers, show their total spend in Q1 2024, Q2 2024, Q3 2024, and Q4 2024 side by side. Which product category did they buy most in each quarter?"
Log-Test "F5a" "No raw SQL"   $(if (No-SQL $f5.Response) {"PASS"} else {"FAIL"}) ""
Log-Test "F5b" "Has table"    $(if (Has-Table $f5.Response) {"PASS"} else {"WARN"}) ""
Log-Test "F5c" "Quarters in response" $(if ($f5.Response -match "Q1|Q2|Q3|Q4") {"PASS"} else {"WARN"}) ""

# ──────────────────────────────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " FINAL REPORT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "PASS: $PASS  |  FAIL: $FAIL  |  WARN: $WARN  |  TOTAL: $($PASS+$FAIL+$WARN)" -ForegroundColor White
Write-Host ""
Write-Host "FAILURES:" -ForegroundColor Red
$LOG | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object { Write-Host "  [$($_.ID)] $($_.Label) — $($_.Detail)" -ForegroundColor Red }
Write-Host ""
Write-Host "WARNINGS (manual review):" -ForegroundColor Yellow
$LOG | Where-Object { $_.Status -eq "WARN" } | ForEach-Object { Write-Host "  [$($_.ID)] $($_.Label) — $($_.Detail)" -ForegroundColor Yellow }
