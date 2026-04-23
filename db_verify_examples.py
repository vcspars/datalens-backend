"""Verify the corrected few-shot SQL examples produce the right shape of data."""
import pyodbc

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=VCSSQL02;DATABASE=TestStarSchema;'
    'UID=DEVUser;PWD=DEVUser;TrustServerCertificate=yes;'
)
cur = conn.cursor()

def run(title, sql):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"  Columns: {cols}")
    print(f"  Row count: {len(rows)}")
    print('-' * 80)
    for r in rows[:30]:
        print(' | '.join(str(v) if v is not None else 'NULL' for v in r))
    if len(rows) > 30:
        print(f"  ... {len(rows)-30} more rows ...")

# Example 1 - Main Grouped (FIXED)
run("Example 1 — BS Main Grouped (latest month)",
    """SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END AS [Section],
    CM.BalanceSheet_MainGroups            AS [Line Item],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END) AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_MainGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_MainGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups
ORDER BY [Section], [Line Item]""")

# Example 2 - Sub Grouped (FIXED)
run("Example 2 — BS Sub Grouped (latest month)",
    """SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END AS [Section],
    CM.BalanceSheet_MainGroups            AS [Sub Group],
    CM.BalanceSheet_SubGroups             AS [Line Item],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END) AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_SubGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_SubGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups
ORDER BY [Section], [Sub Group], [Line Item]""")

# Example 3 - Detailed (unchanged, verify it still works)
run("Example 3 — BS Detailed (latest month, first 10 rows)",
    """SELECT TOP 10
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END AS [Section],
    CM.BalanceSheet_MainGroups            AS [Sub Group],
    CM.BalanceSheet_SubGroups             AS [Detail Group],
    CM.BalanceSheet_Details               AS [Account],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END) AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_Details IS NOT NULL
  AND LEN(CM.BalanceSheet_Details) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups, CM.BalanceSheet_Details
ORDER BY [Section], [Sub Group], [Detail Group], [Account]""")

# P&L Examples verify
run("Example 4 — P&L Main Grouped (latest month)",
    """SELECT
    CM.PLStatementMainGroups AS [Group],
    SUM(FAM.YTD_Net * -1)    AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.PLStatementMainGroups IS NOT NULL
  AND LEN(CM.PLStatementMainGroups) > 0
GROUP BY CM.PLStatementMainGroups
ORDER BY CM.PLStatementMainGroups""")

conn.close()
print("\nAll examples verified successfully.")
