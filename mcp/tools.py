"""
Business logic for all 7 MCP sales tools.

Each function:
  1. Accepts validated input parameters.
  2. Executes the corresponding parameterised SQL query via pyodbc.
  3. Returns typed rows using the Pydantic models.
"""

import logging
from datetime import date
from typing import Optional

from db import execute_query
from models import (
    SalesByPeriodRow,
    SalesByProductRow,
    SalesByCustomerRow,
    SalesByRegionRow,
    YoYRevenueRow,
    AOVRow,
    NewVsRepeatRow,
)

logger = logging.getLogger(__name__)


# ── Serialisation helper ───────────────────────────────────────────────────────

def _serialize_row(row: dict) -> dict:
    """Convert non-JSON-serialisable values (date, Decimal, …) to plain types."""
    out = {}
    for k, v in row.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        else:
            try:
                out[k] = float(v) if v is not None and hasattr(v, "__float__") else v
            except (TypeError, ValueError):
                out[k] = v
    return out


# ── Tool 1 — Total Sales by Day/Week/Month/Year ────────────────────────────────

def tool_total_sales_by_period(year: int, month: str) -> list[SalesByPeriodRow]:
    """
    Return total sales and invoice counts aggregated by week and date for a
    given calendar year and month.

    Args:
        year:  Calendar year (e.g. 2024).
        month: Full month name (e.g. 'June').
    """
    sql = """
        SELECT
            d.Year,
            d.MonthName,
            DATEPART(WEEK, d.FullDate) AS WeekNumber,
            d.FullDate                 AS SalesDate,
            SUM(fsi.TotalAmount)       AS TotalSales,
            COUNT(fsi.SalesInvoiceNo)  AS InvoiceCount
        FROM FactSalesInvoice fsi
        INNER JOIN DimDate d ON fsi.DateKey = d.DateKey
        WHERE d.Year = ? AND d.MonthName = ?
        GROUP BY
            d.Year,
            d.MonthName,
            DATEPART(WEEK, d.FullDate),
            d.FullDate
        HAVING d.Year >= 2000
        ORDER BY d.Year, d.MonthName, WeekNumber, SalesDate;
    """
    logger.info(f"[tool_total_sales_by_period] year={year}, month={month}")
    rows = execute_query(sql, (year, month))
    return [SalesByPeriodRow(**_serialize_row(r)) for r in rows]


# ── Tool 2 — Sales by Product, Collection, and Category ───────────────────────

def tool_sales_by_product(category: str) -> list[SalesByProductRow]:
    """
    Return sales revenue and units sold grouped by product category,
    collection, and item for a given category code.

    Args:
        category: Product category code (e.g. 'PAKIS').
    """
    sql = """
        SELECT
            p.Category,
            p.Collection,
            p.ItemID   AS Product,
            p.ItemName AS ProductName,
            SUM(fsd.SalesAmount) AS TotalRevenue,
            SUM(fsd.Quantity)    AS UnitsSold
        FROM FactSalesDetail fsd
        JOIN DimProduct p ON fsd.ProductKey = p.ProductKey
        WHERE p.Category = ?
        GROUP BY p.Category, p.Collection, p.ItemName, p.ItemID
        ORDER BY TotalRevenue DESC;
    """
    logger.info(f"[tool_sales_by_product] category={category}")
    rows = execute_query(sql, (category,))
    return [SalesByProductRow(**_serialize_row(r)) for r in rows]


# ── Tool 3 — Sales by Customer and Customer Tier ──────────────────────────────

def tool_sales_by_customer(customer_id: str) -> list[SalesByCustomerRow]:
    """
    Return total spent and order frequency for a specific customer,
    including their customer tier information.

    Args:
        customer_id: Customer identifier (e.g. '053240').
    """
    sql = """
        SELECT
            DPC.Description        AS [Customer Tier],
            c.CustomerName,
            c.CustomerID,
            SUM(fsi.TotalAmount)       AS TotalSpent,
            COUNT(fsi.SalesInvoiceNo)  AS OrderFrequency
        FROM FactSalesInvoice fsi
        JOIN DimCustomer c        ON fsi.CustomerKey = c.CustomerKey
        JOIN DimPriceCategory DPC ON c.Category = DPC.CategoryNo
        WHERE c.CustomerID = ?
        GROUP BY DPC.Description, c.CustomerName, c.CustomerID
        ORDER BY TotalSpent DESC;
    """
    logger.info(f"[tool_sales_by_customer] customer_id={customer_id}")
    rows = execute_query(sql, (customer_id,))
    clean = []
    for r in rows:
        r = _serialize_row(r)
        r["CustomerTier"] = r.pop("Customer Tier", None)
        clean.append(r)
    return [SalesByCustomerRow(**r) for r in clean]


# ── Tool 4 — Sales by Region and Territory ────────────────────────────────────

def tool_sales_by_region(region: str) -> list[SalesByRegionRow]:
    """
    Aggregate revenue by geographic hierarchy (country, region, state)
    for a named region.

    Args:
        region: Region name (e.g. 'NORTHEAST').
    """
    sql = """
        SELECT
            c.Country,
            r.RegionName,
            c.State,
            SUM(fsi.TotalAmount) AS RegionalRevenue
        FROM FactSalesInvoice fsi
        JOIN DimCustomer c ON fsi.CustomerKey = c.CustomerKey
        JOIN DimRegion r   ON c.Region = r.regionNo
        WHERE r.RegionName = ?
        GROUP BY c.Country, r.RegionName, c.State
        ORDER BY RegionalRevenue DESC;
    """
    logger.info(f"[tool_sales_by_region] region={region}")
    rows = execute_query(sql, (region,))
    return [SalesByRegionRow(**_serialize_row(r)) for r in rows]


# ── Tool 5 — Revenue vs. Same Period Last Year (YoY) ──────────────────────────

def tool_yoy_revenue(year: int, month: str) -> list[YoYRevenueRow]:
    """
    Compute revenue for the given year/month and compare it to the same
    month in the prior year, returning the YoY growth percentage.

    Args:
        year:  The target year (e.g. 2025).
        month: Full month name (e.g. 'November').
    """
    sql = """
        WITH RevenueSamePeriod AS (
            SELECT
                d.MonthName,
                d.Year AS CurrentYear,
                SUM(fsi.TotalAmount) AS CurrentYearRevenue,
                LAG(SUM(fsi.TotalAmount), 1)
                    OVER (PARTITION BY d.MonthName ORDER BY d.Year)
                    AS LastYearRevenue
            FROM FactSalesInvoice fsi
            JOIN DimDate d ON fsi.DateKey = d.DateKey
            GROUP BY d.Year, d.MonthName
        )
        SELECT
            *,
            (CurrentYearRevenue - LastYearRevenue) * 100.0
                / NULLIF(LastYearRevenue, 0) AS YoY_Growth_Percentage
        FROM RevenueSamePeriod
        WHERE CurrentYear = ? AND MonthName = ?;
    """
    logger.info(f"[tool_yoy_revenue] year={year}, month={month}")
    rows = execute_query(sql, (year, month))
    return [YoYRevenueRow(**_serialize_row(r)) for r in rows]


# ── Tool 6 — Average Order Value (AOV) ────────────────────────────────────────

def tool_average_order_value(year: int, month: str) -> list[AOVRow]:
    """
    Compute the average order value (mean invoice amount) for a given
    year and month, excluding cancelled and voided orders.

    Args:
        year:  Target year (e.g. 2025).
        month: Full month name (e.g. 'November').
    """
    sql = """
        SELECT
            d.Year,
            d.MonthName,
            AVG(fso.TotalAmount) AS AverageOrderValue
        FROM FactSalesOrders fso
        JOIN DimDate d ON fso.OrderDateKey = d.DateKey
        WHERE fso.Status NOT IN ('Cancel', 'Void')
          AND d.Year      = ?
          AND d.MonthName = ?
        GROUP BY d.Year, d.MonthName, d.Month
        ORDER BY d.Year DESC, d.Month DESC;
    """
    logger.info(f"[tool_average_order_value] year={year}, month={month}")
    rows = execute_query(sql, (year, month))
    return [AOVRow(**_serialize_row(r)) for r in rows]


# ── Tool 7 — New vs. Repeat Customer Revenue ──────────────────────────────────

def tool_new_vs_repeat_revenue(year: int, month: str) -> list[NewVsRepeatRow]:
    """
    Split revenue into new-customer revenue (first purchase ever) and
    repeat-customer revenue for the specified year and month.

    Args:
        year:  Target year (e.g. 2025).
        month: Full month name (e.g. 'November').
    """
    sql = """
        WITH CustomerFirstPurchase AS (
            SELECT
                CustomerKey,
                MIN(DateKey) AS FirstPurchaseDateKey
            FROM FactSalesInvoice
            GROUP BY CustomerKey
        )
        SELECT
            d.Year,
            d.MonthName,
            SUM(CASE WHEN fsi.DateKey = cfp.FirstPurchaseDateKey
                     THEN fsi.TotalAmount ELSE 0 END) AS NewCustomerRevenue,
            SUM(CASE WHEN fsi.DateKey > cfp.FirstPurchaseDateKey
                     THEN fsi.TotalAmount ELSE 0 END) AS RepeatCustomerRevenue
        FROM FactSalesInvoice fsi
        JOIN DimDate d                 ON fsi.DateKey = d.DateKey
        JOIN CustomerFirstPurchase cfp ON fsi.CustomerKey = cfp.CustomerKey
        WHERE d.Year = ? AND d.MonthName = ?
        GROUP BY d.Year, d.MonthName
        ORDER BY d.Year DESC;
    """
    logger.info(f"[tool_new_vs_repeat_revenue] year={year}, month={month}")
    rows = execute_query(sql, (year, month))
    return [NewVsRepeatRow(**_serialize_row(r)) for r in rows]
