"""
DB Snapshot Service — pre-fetches business KPI metrics per role at server startup.

On startup (after SQL DB cache is warmed), runs predefined read-only queries for each
role (executive, sales, operations) concurrently via asyncio.gather + ThreadPoolExecutor,
and stores the results in MongoDB (db_snapshots collection, one document per role).

Summary, Report, and Top Questions endpoints then use this pre-fetched real data as
LLM context — making all three role-aware and data-driven with actual numbers.

Query tuple format: (metric_key, human_readable_label, sql, is_ytd)
  is_ytd=True  → SQL returns TWO columns: data_year (INT) and val (NVARCHAR)
                 The actual year comes from YEAR(GETDATE()) inside the SQL itself.
  is_ytd=False → SQL returns ONE column: val (NVARCHAR)
                 Used for current-state metrics (inventory, active counts, etc.)
"""

import time
import asyncio
from datetime import datetime
from typing import Any

print("[DBSnapshot] Module loaded")


# ---------------------------------------------------------------------------
# Predefined queries per role
# Each tuple: (metric_key, human_readable_label, sql, is_ytd)
#
# is_ytd=True  → SELECT YEAR(GETDATE()) AS data_year, FORMAT(...) AS val ...
# is_ytd=False → SELECT FORMAT(...) AS val ...
# ---------------------------------------------------------------------------

_EXECUTIVE_QUERIES: list[tuple[str, str, str, bool]] = [
    (
        "total_revenue_ytd",
        "Total Sales Revenue",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(MerchandiseAmount), 0), 'N2') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "total_invoices_ytd",
        "Total Customer Invoices Issued",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(COUNT(DISTINCT SalesInvoiceNo), 'N0') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "total_profit_ytd",
        "Total Gross Profit",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(ProfitAmount), 0), 'N2') AS val "
        "FROM FactSalesDetail FSD "
        "JOIN DimDate DD ON FSD.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE())",
        True,
    ),
    (
        "total_qty_sold_ytd",
        "Total Units Sold",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(TotalQuantity), 0), 'N0') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "net_profit_margin_ytd",
        "Net Profit Margin %",
        "SELECT YEAR(GETDATE()) AS data_year, "
        "FORMAT(ISNULL(SUM(ProfitAmount) * 100.0 / NULLIF(SUM(SalesAmount), 0), 0), 'N2') AS val "
        "FROM FactSalesDetail FSD "
        "JOIN DimDate DD ON FSD.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE())",
        True,
    ),
    (
        "active_customers",
        "Number of Active Customers",
        "SELECT FORMAT(COUNT(*), 'N0') AS val FROM DimCustomer WHERE Status = 'Active'",
        False,
    ),
    (
        "active_vendors",
        "Number of Active Vendors",
        "SELECT FORMAT(COUNT(*), 'N0') AS val FROM DimVendors WHERE Status = 'Active'",
        False,
    ),
    (
        "inventory_value",
        "Total Inventory Value",
        "SELECT FORMAT(ISNULL(SUM(InventoryValue), 0), 'N2') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "total_stock_on_hand",
        "Total Units in Stock",
        "SELECT FORMAT(ISNULL(SUM(QuantityOnHand), 0), 'N0') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "items_below_reorder",
        "Products Below Reorder Level",
        "SELECT FORMAT(COUNT(*), 'N0') AS val "
        "FROM FactInventorySnapshot FIS "
        "JOIN DimWarehouse DW ON FIS.BranchKey = DW.BranchKey "
        "WHERE FIS.QuantityOnHand < DW.BufferQty AND DW.IsActive = 1",
        False,
    ),
    (
        "customer_returns_ytd",
        "Customer Return Orders Processed",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(COUNT(DISTINCT FCR.CustomerReturnNo), 'N0') AS val "
        "FROM FactCustomerReturn FCR "
        "JOIN DimDate DD ON FCR.CreditDateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE())",
        True,
    ),
    (
        "total_discounts_ytd",
        "Total Discounts Given to Customers",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(DiscountAmount), 0), 'N2') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "vendor_payments_ytd",
        "Total Payments Made to Vendors",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(Amount), 0), 'N2') AS val "
        "FROM FactVendorPayment FVP "
        "JOIN DimDate DD ON FVP.PaymentDateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FVP.VoidDateKey IS NULL",
        True,
    ),
    (
        "purchase_orders_ytd",
        "Total Purchase Orders Placed",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(COUNT(DISTINCT PurchaseOrderNo), 'N0') AS val "
        "FROM FactPurchaseOrder FPO "
        "JOIN DimDate DD ON FPO.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE())",
        True,
    ),
    (
        "pending_customer_payments",
        "Customer Payments Still Outstanding",
        "SELECT FORMAT(ISNULL(SUM(Amount - ISNULL(AppliedAmount, 0)), 0), 'N2') AS val "
        "FROM FactCustomerPayment "
        "WHERE Status NOT IN ('Void','Cancelled','Reversed')",
        False,
    ),
]

_SALES_QUERIES: list[tuple[str, str, str, bool]] = [
    (
        "total_revenue_ytd",
        "Total Sales Revenue",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(MerchandiseAmount), 0), 'N2') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "total_invoices_ytd",
        "Total Customer Invoices Issued",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(COUNT(DISTINCT SalesInvoiceNo), 'N0') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "total_qty_sold_ytd",
        "Total Units Sold",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(TotalQuantity), 0), 'N0') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "total_discounts_ytd",
        "Total Discounts Given to Customers",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(ISNULL(SUM(DiscountAmount), 0), 'N2') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed')",
        True,
    ),
    (
        "active_customers",
        "Number of Active Customers",
        "SELECT FORMAT(COUNT(*), 'N0') AS val FROM DimCustomer WHERE Status = 'Active'",
        False,
    ),
    (
        "customer_returns_ytd",
        "Customer Return Orders Processed",
        "SELECT YEAR(GETDATE()) AS data_year, FORMAT(COUNT(DISTINCT FCR.CustomerReturnNo), 'N0') AS val "
        "FROM FactCustomerReturn FCR "
        "JOIN DimDate DD ON FCR.CreditDateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE())",
        True,
    ),
    (
        "inventory_value",
        "Total Inventory Value",
        "SELECT FORMAT(ISNULL(SUM(InventoryValue), 0), 'N2') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "items_below_reorder",
        "Products Below Reorder Level",
        "SELECT FORMAT(COUNT(*), 'N0') AS val "
        "FROM FactInventorySnapshot FIS "
        "JOIN DimWarehouse DW ON FIS.BranchKey = DW.BranchKey "
        "WHERE FIS.QuantityOnHand < DW.BufferQty AND DW.IsActive = 1",
        False,
    ),
    (
        "pending_customer_payments",
        "Customer Payments Still Outstanding",
        "SELECT FORMAT(ISNULL(SUM(Amount - ISNULL(AppliedAmount, 0)), 0), 'N2') AS val "
        "FROM FactCustomerPayment "
        "WHERE Status NOT IN ('Void','Cancelled','Reversed')",
        False,
    ),
    (
        "top5_customers_revenue",
        "Top 5 Customers by Revenue",
        "SELECT YEAR(GETDATE()) AS data_year, "
        "DC.CustomerName + ': $' + FORMAT(SUM(FSI.MerchandiseAmount), 'N2') AS val "
        "FROM FactSalesInvoice FSI "
        "JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey "
        "JOIN DimDate DD ON FSI.DateKey = DD.DateKey "
        "WHERE DD.Year = YEAR(GETDATE()) "
        "AND FSI.Status NOT IN ('Void','Cancelled','Reversed') "
        "GROUP BY DC.CustomerName "
        "ORDER BY SUM(FSI.MerchandiseAmount) DESC",
        True,
    ),
]

_OPERATIONS_QUERIES: list[tuple[str, str, str, bool]] = [
    (
        "total_stock_on_hand",
        "Total Units in Stock",
        "SELECT FORMAT(ISNULL(SUM(QuantityOnHand), 0), 'N0') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "inventory_value",
        "Total Inventory Value",
        "SELECT FORMAT(ISNULL(SUM(InventoryValue), 0), 'N2') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "available_qty",
        "Total Available Units (After Reservations and Picking)",
        "SELECT FORMAT(ISNULL(SUM(QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0)), 0), 'N0') AS val "
        "FROM FactInventorySnapshot",
        False,
    ),
    (
        "items_below_reorder",
        "Products Below Reorder Level",
        "SELECT FORMAT(COUNT(*), 'N0') AS val "
        "FROM FactInventorySnapshot FIS "
        "JOIN DimWarehouse DW ON FIS.BranchKey = DW.BranchKey "
        "WHERE FIS.QuantityOnHand < DW.BufferQty AND DW.IsActive = 1",
        False,
    ),
    (
        "items_zero_stock",
        "Products Currently Out of Stock",
        "SELECT FORMAT(COUNT(*), 'N0') AS val "
        "FROM FactInventorySnapshot "
        "WHERE QuantityOnHand <= 0",
        False,
    ),
    (
        "active_warehouses",
        "Number of Active Warehouses",
        "SELECT FORMAT(COUNT(*), 'N0') AS val FROM DimWarehouse WHERE IsActive = 1",
        False,
    ),
    (
        "backorder_count",
        "Total Open Backorder Records",
        "SELECT FORMAT(COUNT(*), 'N0') AS val "
        "FROM DimSalesOrderDetail_Log "
        "WHERE BackOrder = 'Yes'",
        False,
    ),
    (
        "picking_qty",
        "Units Currently Being Picked for Outbound Shipments",
        "SELECT FORMAT(ISNULL(SUM(PickingQuantity), 0), 'N0') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "reserved_qty",
        "Units Reserved Against Open Sales Orders",
        "SELECT FORMAT(ISNULL(SUM(SalesOrderQuantity), 0), 'N0') AS val FROM FactInventorySnapshot",
        False,
    ),
    (
        "damaged_qty",
        "Units Flagged as Damaged in Warehouse",
        "SELECT FORMAT(ISNULL(SUM(DamagedQuantity), 0), 'N0') AS val FROM FactInventorySnapshot",
        False,
    ),
]

ROLE_QUERIES: dict[str, list[tuple[str, str, str, bool]]] = {
    "executive": _EXECUTIVE_QUERIES,
    "sales": _SALES_QUERIES,
    "operations": _OPERATIONS_QUERIES,
}


# ---------------------------------------------------------------------------
# Plain-English schema summaries per role (no table/column names)
# Used by the Top Questions LLM so it knows what questions are answerable
# ---------------------------------------------------------------------------

_ROLE_SCHEMA_SUMMARIES: dict[str, str] = {
    "executive": (
        "The business data covers the following areas:\n"
        "- Sales & Revenue: invoices, revenue amounts, discounts, tax, quantities sold — broken down by date, customer, and warehouse\n"
        "- Profitability: product-level gross profit, unit cost versus unit price per line item\n"
        "- Customer Analytics: customer profiles, categories, regions, payment terms, credit limits\n"
        "- Vendor Analytics: vendor profiles, types, regions, payment terms\n"
        "- Purchases & Procurement: purchase orders, received quantities, costs, on-time delivery tracking\n"
        "- Inventory: current stock levels, inventory values, reorder monitoring across all warehouses\n"
        "- Customer Returns: return reasons, quantities returned, credit memo processing\n"
        "- Vendor Returns: amounts and quantities returned to vendors\n"
        "- Customer Payments: payments received, applied amounts, outstanding balances\n"
        "- Vendor Payments: payments made to vendors, applied amounts\n"
        "- Backorders: open backorder history by product and customer\n"
        "- Sales Commissions: sales rep commission invoices and payments\n"
        "- Warehouse Operations: multi-warehouse management across locations"
    ),
    "sales": (
        "The business data available for sales covers:\n"
        "- Sales & Revenue: invoices, revenue, discounts, quantities sold — by date and customer\n"
        "- Customer Analytics: customer profiles, regions, categories, payment terms\n"
        "- Inventory: current stock levels and reorder monitoring\n"
        "- Customer Returns: return quantities, reasons, and trends\n"
        "- Customer Payments: payment status and outstanding balances\n"
        "- Backorders: open backorder history by product and customer\n"
        "- Product Catalog: product categories, pricing, and availability"
    ),
    "operations": (
        "The business data available for operations covers:\n"
        "- Inventory Levels: stock on hand, available quantities (after picking and reservations), inventory values\n"
        "- Reorder Monitoring: products below safety stock levels across warehouses\n"
        "- Warehouse Operations: picking activity, reserved quantities, damaged stock, active warehouses\n"
        "- Backorders: open backorder history by product"
    ),
}


def get_schema_summary_for_role(role: str) -> str:
    """Return a plain-English data scope description for the given role.

    Used as context for the Top Questions LLM so it generates questions that
    are actually answerable from the data available to that role.
    """
    summary = _ROLE_SCHEMA_SUMMARIES.get(role, _ROLE_SCHEMA_SUMMARIES["executive"])
    print(f"[DBSnapshot] get_schema_summary_for_role | role={role!r} | len={len(summary)}")
    return summary


# ---------------------------------------------------------------------------
# Result parser
# ---------------------------------------------------------------------------

def _parse_metric_result(raw: str, is_ytd: bool) -> dict[str, Any]:
    """Parse a SQLDatabase.run() result string into a structured metric dict.

    For is_ytd=True queries the SQL returns TWO columns: data_year (INT) and
    val (NVARCHAR).  The year is extracted directly from the first column of the
    result — no Python datetime heuristics are used.

    For is_ytd=False queries the SQL returns ONE column: val (NVARCHAR).

    Returns {"value": str, "year": int | None}.
    """
    import ast as _ast

    if not raw:
        return {"value": "N/A", "year": None}

    s = raw.strip()
    year: int | None = None
    value = "N/A"

    # --- Attempt list-of-tuples / tuple literal: [(year, val), ...] or [(val,)]
    if s.startswith("[") or (s.startswith("(") and s.endswith(")")):
        try:
            data = _ast.literal_eval(s)
            if isinstance(data, tuple):
                rows: list = [data]
            elif isinstance(data, list):
                rows = data
            else:
                rows = []

            if rows:
                val_lines: list[str] = []
                for row in rows:
                    if not isinstance(row, (list, tuple)):
                        val_lines.append(str(row).strip())
                        continue
                    if is_ytd and len(row) >= 2:
                        try:
                            year = int(row[0])
                        except (ValueError, TypeError):
                            pass
                        val_lines.append(str(row[1]).strip() if row[1] is not None else "")
                    elif not is_ytd and len(row) >= 1:
                        val_lines.append(str(row[0]).strip() if row[0] is not None else "")
                    else:
                        val_lines.append(str(row[-1]).strip() if row else "")
                value = "\n".join(v for v in val_lines if v) or "N/A"
                print(
                    f"[DBSnapshot] _parse_metric_result(tuple) | is_ytd={is_ytd} | year={year} | value={value!r:.60}"
                )
                return {"value": value, "year": year}
        except (ValueError, SyntaxError):
            pass  # fall through to text-based parsing

    # --- Text / tabular fallback
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return {"value": "N/A", "year": None}

    # Drop known column-header lines
    _HEADER_TOKENS = {"val", "value", "cnt", "count", "result", "(no results)"}
    first_lower = lines[0].lower()
    if first_lower in _HEADER_TOKENS or (is_ytd and "data_year" in first_lower):
        lines = lines[1:]

    if not lines:
        return {"value": "N/A", "year": None}

    if is_ytd:
        # Each data line: "<year_int> <value>"
        val_lines = []
        for line in lines:
            parts = line.split(None, 1)
            if len(parts) >= 2:
                try:
                    year = int(parts[0].replace(",", ""))
                except ValueError:
                    pass
                val_lines.append(parts[1].strip())
            elif parts:
                val_lines.append(parts[0].strip())
        value = "\n".join(v for v in val_lines if v) or "N/A"
    else:
        value = "\n".join(lines) or "N/A"

    print(
        f"[DBSnapshot] _parse_metric_result(text) | is_ytd={is_ytd} | year={year} | value={value!r:.60}"
    )
    return {"value": value, "year": year}


# ---------------------------------------------------------------------------
# Synchronous query runner (called inside ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _run_role_queries_sync(role: str, queries: list[tuple[str, str, str, bool]]) -> list[dict[str, Any]]:
    """Run all predefined SQL queries for a role synchronously.

    Designed to be called from asyncio.get_event_loop().run_in_executor().
    Each query is wrapped in its own try/except so a single failure does not
    abort the rest.

    Each query tuple is (key, label, sql, is_ytd).  For is_ytd queries the SQL
    returns two columns (data_year, val) and the year is stored in the metric
    document alongside the value — no Python datetime manipulation is used.

    Returns a list of metric dicts: {key, label, value, year}.
    """
    from app.services.langchain_agent import _get_sql_db_with_retry

    print(f"[DBSnapshot][{role}] Acquiring SQL DB connection...")
    try:
        db = _get_sql_db_with_retry(max_retries=1)
        print(f"[DBSnapshot][{role}] SQL DB connection acquired")
    except Exception as e:
        print(f"[DBSnapshot][{role}] DB connection FAILED: {e}")
        return [{"key": k, "label": lbl, "value": "N/A", "year": None} for k, lbl, _, _ytd in queries]

    metrics: list[dict[str, Any]] = []
    succeeded = 0

    for key, label, sql, is_ytd in queries:
        t_q = time.time()
        try:
            raw = db.run(sql)
            parsed = _parse_metric_result(str(raw) if raw is not None else "", is_ytd)
            elapsed_q = time.time() - t_q
            print(
                f"[DBSnapshot][{role}] Query '{key}' OK | "
                f"year={parsed['year']} | value={parsed['value']!r:.60} | {elapsed_q:.2f}s"
            )
            metrics.append({
                "key": key,
                "label": label,
                "value": parsed["value"],
                "year": parsed["year"],
            })
            succeeded += 1
        except Exception as e:
            elapsed_q = time.time() - t_q
            print(
                f"[DBSnapshot][{role}] Query '{key}' FAILED after {elapsed_q:.2f}s | "
                f"{type(e).__name__}: {e}"
            )
            metrics.append({"key": key, "label": label, "value": "N/A", "year": None})

    print(f"[DBSnapshot][{role}] Queries done | {succeeded}/{len(queries)} succeeded")
    return metrics


# ---------------------------------------------------------------------------
# Async orchestration
# ---------------------------------------------------------------------------

async def run_role_snapshot(role: str) -> list[dict[str, Any]]:
    """Run all predefined queries for one role and save results to MongoDB.

    Queries are run synchronously in a thread pool so they don't block the
    event loop. MongoDB save is async.

    Returns the list of metric dicts (regardless of whether MongoDB save succeeded).
    """
    t_role = time.time()
    queries = ROLE_QUERIES.get(role, [])
    print(f"[DBSnapshot][{role}] Starting snapshot | {len(queries)} queries")

    loop = asyncio.get_event_loop()
    metrics: list[dict[str, Any]] = await loop.run_in_executor(
        None,
        lambda: _run_role_queries_sync(role, queries),
    )

    elapsed = time.time() - t_role
    succeeded = sum(1 for m in metrics if m.get("value") not in ("N/A", None, ""))
    print(f"[DBSnapshot][{role}] All queries complete | {succeeded}/{len(queries)} succeeded | {elapsed:.1f}s total")

    # Persist to MongoDB
    try:
        from app.database import get_database
        db = get_database()
        if db is None:
            print(f"[DBSnapshot][{role}] WARNING: MongoDB not ready, snapshot not saved")
        else:
            doc = {
                "role": role,
                "fetched_at": datetime.utcnow(),
                "metrics": metrics,
            }
            await db.db_snapshots.update_one(
                {"role": role},
                {"$set": doc},
                upsert=True,
            )
            print(f"[DBSnapshot][{role}] Saved to MongoDB | {len(metrics)} metrics")
    except Exception as e:
        print(f"[DBSnapshot][{role}] MongoDB save FAILED: {type(e).__name__}: {e}")

    return metrics


async def run_all_snapshots() -> None:
    """Run snapshots for all three roles concurrently and persist to MongoDB.

    Called as a background asyncio.Task from main.py lifespan after the SQL DB
    cache is warmed. Does not block server startup.
    """
    t_total = time.time()
    print("[DBSnapshot] Starting snapshot runner for all roles (executive, sales, operations)...")

    results = await asyncio.gather(
        run_role_snapshot("executive"),
        run_role_snapshot("sales"),
        run_role_snapshot("operations"),
        return_exceptions=True,
    )

    roles = ["executive", "sales", "operations"]
    for role, result in zip(roles, results):
        if isinstance(result, Exception):
            print(f"[DBSnapshot][{role}] ERROR during snapshot: {type(result).__name__}: {result}")
        else:
            n_ok = sum(1 for m in result if m.get("value") not in ("N/A", None, ""))
            print(f"[DBSnapshot][{role}] Snapshot complete | {n_ok}/{len(result)} metrics OK")

    elapsed = time.time() - t_total
    print(f"[DBSnapshot] All roles complete | total elapsed={elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Context formatters (used by chat routes)
# ---------------------------------------------------------------------------

async def get_snapshot_context(role: str) -> str:
    """Read the latest snapshot from MongoDB for a role and format as a
    human-readable bullet list for injection into LLM prompts.

    The year shown next to each metric is taken directly from the 'year' field
    stored in the metric document, which itself came from YEAR(GETDATE()) in the
    SQL query result.  No Python datetime manipulation or string replacement is
    performed to derive the year — it is purely data-driven.

    Returns an empty string if no snapshot is available (first run before
    background task completes, or DB connection issues).
    """
    print(f"[DBSnapshot] get_snapshot_context called | role={role!r}")
    try:
        from app.database import get_database
        db = get_database()
        if db is None:
            print(f"[DBSnapshot] MongoDB not available for role={role!r}")
            return ""

        doc = await db.db_snapshots.find_one({"role": role})
        if not doc:
            print(f"[DBSnapshot] No snapshot document found for role={role!r}")
            return ""

        metrics: list[dict] = doc.get("metrics", [])
        fetched_at = doc.get("fetched_at")
        fetch_time_str = (
            fetched_at.strftime("%B %d, %Y at %I:%M %p")
            if isinstance(fetched_at, datetime)
            else "recently"
        )

        lines = [f"Live Business Data Snapshot (captured {fetch_time_str}):"]
        for m in metrics:
            label = (m.get("label") or "").strip()
            value = (m.get("value") or "N/A").strip()
            # Year comes from the SQL result column data_year — None for current-state metrics
            metric_year: int | None = m.get("year")
            if not label or not value or value == "N/A":
                continue
            # Append the year from the data in parentheses only when the metric is year-scoped
            year_tag = f" ({metric_year})" if metric_year else ""
            # Multi-line values (e.g. top 5 customers) — indent sub-lines
            if "\n" in value:
                lines.append(f"  - {label}{year_tag}:")
                for sub in value.splitlines():
                    if sub.strip():
                        lines.append(f"      * {sub.strip()}")
            else:
                lines.append(f"  - {label}{year_tag}: {value}")

        result = "\n".join(lines)
        print(
            f"[DBSnapshot] Snapshot context built | role={role!r} | "
            f"metrics={len(metrics)} | chars={len(result)}"
        )
        return result

    except Exception as e:
        print(f"[DBSnapshot] get_snapshot_context error | role={role!r} | {type(e).__name__}: {e}")
        return ""
