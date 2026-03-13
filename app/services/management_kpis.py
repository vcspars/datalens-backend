"""
Management KPI fetcher for summary and report endpoints.
Runs read-only SQL queries in parallel and returns a text block for LLM context.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from app.services.sql_utils import is_read_only_sql

print("[ManagementKPIs] Module loaded")

# Module-level executor for parallel query execution (reused across calls)
_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="kpi_")
    return _EXECUTOR


def _parse_single_value(out) -> str:
    """Extract a single displayable value from db.run() output (e.g. '123', '1,234.56', '(123,)')."""
    if out is None:
        return "(unavailable)"
    s = str(out).strip()
    if not s:
        return "(unavailable)"
    # Single number on its own
    if s.isdigit():
        return s
    # Last line often has the value (header on first line)
    lines = [line.strip() for line in s.splitlines() if line.strip()]
    for line in reversed(lines):
        # Strip parentheses and commas (e.g. "(123,)" or "Decimal('123.45')")
        cleaned = re.sub(r"^\(|\)$", "", line).strip()
        for part in re.split(r"[\s,]+", cleaned):
            part = re.sub(r"^['\"]|['\"]$", "", part)
            if part.replace(".", "").replace("-", "").isdigit():
                return part
    # Try first number found anywhere
    for part in re.sub(r"[\s,()]+", " ", s).split():
        if part.replace(".", "").replace("-", "").isdigit():
            return part
    return "(unavailable)"


def _format_number(val: str) -> str:
    """Format a numeric string with thousands separators if it looks like a number."""
    if val in ("(unavailable)", "(data unavailable)", ""):
        return val
    try:
        f = float(val)
        if f == int(f):
            return f"{int(f):,}"
        return f"{f:,.2f}"
    except ValueError:
        return val


# Read-only SELECT queries for management KPIs. Each returns one row, one or two columns.
# Keys are display names in the context block.
# Global / all-time KPIs (no year filter — general business overview)
KPI_QUERIES = [
    (
        "Total Revenue",
        "SELECT ISNULL(SUM(FSD.SalesAmount), 0) AS TotalRevenue FROM FactSalesDetail FSD "
        "WHERE FSD.SalesType = 'S'",
    ),
    (
        "Total Profit",
        "SELECT ISNULL(SUM(FSD.ProfitAmount), 0) AS TotalProfit FROM FactSalesDetail FSD "
        "WHERE FSD.SalesType = 'S'",
    ),
    (
        "Total Purchases",
        "SELECT ISNULL(SUM(FPO.TotalAmount), 0) AS TotalPurchases FROM FactPurchaseOrder FPO "
        "WHERE FPO.POStatus NOT IN ('Void', 'Cancel')",
    ),
    (
        "Inventory Value (latest snapshot)",
        "SELECT ISNULL(SUM(FIS.InventoryValue), 0) AS InventoryValue FROM FactInventorySnapshot FIS "
        "WHERE FIS.DateKey = (SELECT MAX(DateKey) FROM FactInventorySnapshot)",
    ),
    (
        "Active Customers",
        "SELECT COUNT(DISTINCT FSI.CustomerKey) AS CustomerCount FROM FactSalesInvoice FSI "
        "WHERE FSI.SalesType = 'S'",
    ),
    (
        "Active Vendors",
        "SELECT COUNT(DISTINCT FPO.VendorKey) AS VendorCount FROM FactPurchaseOrder FPO "
        "WHERE FPO.POStatus NOT IN ('Void', 'Cancel')",
    ),
    (
        "Total Invoices",
        "SELECT COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount FROM FactSalesInvoice FSI "
        "WHERE FSI.SalesType = 'S'",
    ),
    (
        "Total Quantity Sold",
        "SELECT ISNULL(SUM(FSD.Quantity), 0) AS TotalQty FROM FactSalesDetail FSD "
        "WHERE FSD.SalesType = 'S'",
    ),
    (
        "Items Below Reorder Level (count)",
        "SELECT COUNT(*) AS BelowReorder FROM FactInventorySnapshot FIS "
        "JOIN DimWarehouse DW ON FIS.BranchKey = DW.BranchKey "
        "WHERE FIS.DateKey = (SELECT MAX(DateKey) FROM FactInventorySnapshot) AND FIS.QuantityOnHand < ISNULL(DW.BufferQty, 999999)",
    ),
    (
        "Purchase Orders On-Time Rate %",
        "SELECT ISNULL(SUM(CASE WHEN DD_Complete.FullDate <= DD_Due.FullDate THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 0) AS OnTimePct "
        "FROM FactPurchaseOrder FPO "
        "JOIN DimDate DD_Due ON FPO.DueDateKey = DD_Due.DateKey JOIN DimDate DD_Complete ON FPO.CompletionDateKey = DD_Complete.DateKey "
        "WHERE FPO.POStatus IN ('Closed', 'Partially Shipped')",
    ),
]


def _run_one_kpi(db, name: str, sql: str) -> tuple[str, str]:
    """Run a single KPI query and return (name, value_string). Thread-safe if db.run is connection-pooled."""
    if not is_read_only_sql(sql):
        return (name, "(data unavailable)")
    try:
        out = db.run(sql)
        raw = _parse_single_value(out)
        return (name, _format_number(raw))
    except Exception as e:
        print(f"[ManagementKPIs] KPI '{name}' failed: {e}")
        return (name, "(data unavailable)")


def fetch_management_kpis_sync() -> str:
    """
    Run all management KPI queries in parallel and return a single text block for use as items_context.
    Uses the shared LangChain SQLDatabase (read-only). Safe to call from a thread (e.g. run_in_executor).
    """
    from app.services.langchain_agent import _get_sql_db_with_retry

    db = _get_sql_db_with_retry(max_retries=2)
    results: dict[str, str] = {}
    executor = _get_executor()
    future_to_name = {executor.submit(_run_one_kpi, db, name, sql): name for name, sql in KPI_QUERIES}
    for future in as_completed(future_to_name):
        try:
            name, value = future.result()
            results[name] = value
        except Exception as e:
            name = future_to_name[future]
            print(f"[ManagementKPIs] Future for '{name}' failed: {e}")
            results[name] = "(data unavailable)"

    # Derive Net Profit Margin if we have revenue and profit
    rev = results.get("Total Revenue", "")
    profit = results.get("Total Profit", "")
    try:
        r = float(rev.replace(",", ""))
        p = float(profit.replace(",", ""))
        if r and r > 0:
            pct = (p / r) * 100
            results["Net Profit Margin %"] = f"{pct:.1f}%"
        else:
            results["Net Profit Margin %"] = "(unavailable)"
    except (ValueError, TypeError):
        results["Net Profit Margin %"] = "(unavailable)"

    lines = ["Management KPIs (use these numbers only; do not invent values):", ""]
    for name, value in results.items():
        lines.append(f"  {name}: {value}")
    return "\n".join(lines)


async def fetch_management_kpis() -> str:
    """Async wrapper: run fetch_management_kpis_sync in a thread so the event loop is not blocked."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_management_kpis_sync)
