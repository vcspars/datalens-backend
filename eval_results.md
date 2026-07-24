# Agent Evaluation Report
**Generated:** 2026-07-17 09:21:45  
**Total:** 23  |  **Passed:** 23  |  **Failed:** 0  
**Pass rate:** 100.0%

---

## SIMPLE (5/5 passed)

| ID | Question | Pass | Time | Table | Rows | SQL | Failure |
|:---|:---------|:----:|-----:|:-----:|-----:|:---:|:--------|
| S01 | What are the top 5 customers by total sales? | ✓ | 24.7s | Y | 5 | Y |  |
| S02 | How many products do we have? | ✓ | 11.6s | Y | 1 | Y |  |
| S03 | Show me the list of warehouses | ✓ | 19.4s | Y | 20 | N |  |
| S04 | Hello, how are you? | ✓ | 4.9s | N | 0 | N |  |
| S05 | What is gross profit? | ✓ | 9.3s | N | 0 | N |  |

## MEDIUM (5/5 passed)

| ID | Question | Pass | Time | Table | Rows | SQL | Failure |
|:---|:---------|:----:|-----:|:-----:|-----:|:---:|:--------|
| M01 | Show total sales by month for the current year | ✓ | 10.4s | Y | 12 | N |  |
| M02 | Who are the top 10 vendors by purchase volume? | ✓ | 12.8s | Y | 10 | N |  |
| M03 | Show me overdue accounts with their outstanding balance | ✓ | 60.8s | Y | 40 | Y |  |
| M04 | What is the average order value by customer tier? | ✓ | 15.4s | Y | 6 | Y |  |
| M05 | Show revenue year over year comparison | ✓ | 14.8s | Y | 5 | Y |  |

## HARD (5/5 passed)

| ID | Question | Pass | Time | Table | Rows | SQL | Failure |
|:---|:---------|:----:|-----:|:-----:|-----:|:---:|:--------|
| H01 | Show me the top 5 customers per ABC category by revenue | ✓ | 21.6s | Y | 15 | Y |  |
| H02 | Give me the P&L income statement for the current period | ✓ | 14.5s | Y | 13 | Y |  |
| H03 | Show the balance sheet grouped by sub group | ✓ | 31.3s | Y | 61 | Y |  |
| H04 | Which customers are in the top 20% by revenue? | ✓ | 36.4s | Y | 40 | Y |  |
| H05 | Show me gross profit by month with % margin | ✓ | 11.7s | Y | 12 | N |  |

## COMPLEX (8/8 passed)

| ID | Question | Pass | Time | Table | Rows | SQL | Failure |
|:---|:---------|:----:|-----:|:-----:|-----:|:---:|:--------|
| C01 | Show me the top 10 customers by total revenue | ✓ | 16.2s | Y | 10 | Y |  |
| C02 | Now show the same but only for this year | ✓ | 23.2s | Y | 10 | Y |  |
| C03 | What was the total sales last month and how does it compare … | ✓ | 9.9s | Y | 2 | N |  |
| C04 | Show me top 3 products per warehouse | ✓ | 99.1s | Y | 40 | Y |  |
| C05 | Which sales rep has the highest commission rate and how much… | ✓ | 11.0s | Y | 1 | N |  |
| C06 | asdfghjkl random nonsense 1234 | ✓ | 3.3s | N | 0 | N |  |
| C07 | Show me all data | ✓ | 6.4s | N | 0 | N |  |
| C08 | Show me inventory value by ABC category | ✓ | 12.9s | Y | 3 | Y |  |

---

## Issues & Suggested Fixes

*(Populated manually after reviewing failures above)*

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | *(fill in)* | High/Med/Low | *(fill in)* |
