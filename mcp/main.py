"""
SPARS Sales Analytics — FastMCP server.

Exposes 7 sales tools over HTTP/SSE on port 8001.
Connect Claude Desktop to: http://localhost:8001/sse

Run:
    cd backend/mcp
    pip install -r requirements.txt
    python main.py
"""

import logging
import sys
import os

# Allow sibling imports (db, models, tools) when running directly
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from tools import (
    tool_total_sales_by_period,
    tool_sales_by_product,
    tool_sales_by_customer,
    tool_sales_by_region,
    tool_yoy_revenue,
    tool_average_order_value,
    tool_new_vs_repeat_revenue,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── MCP server instance ────────────────────────────────────────────────────────
mcp = FastMCP(
    name="sparslens-sales",
    instructions=(
        "This server provides sales analytics tools for the SPARS business intelligence "
        "system. Use the tools to answer questions about sales by period, product, "
        "customer, region, year-over-year comparisons, average order value, and "
        "new vs repeat customer revenue."
    ),
)


# ── Tool registrations ─────────────────────────────────────────────────────────

@mcp.tool(
    name="total_sales_by_period",
    description=(
        "Returns total sales (TotalSales) and invoice counts (InvoiceCount) "
        "aggregated by week and date for a given calendar year and month name. "
        "Use this to answer daily or weekly sales breakdowns within a specific month."
    ),
)
def total_sales_by_period(year: int, month: str):
    """
    Args:
        year:  Calendar year, e.g. 2024.
        month: Full month name, e.g. 'June'.
    """
    return [row.model_dump() for row in tool_total_sales_by_period(year, month)]


@mcp.tool(
    name="sales_by_product",
    description=(
        "Returns sales revenue (TotalRevenue) and units sold (UnitsSold) "
        "grouped by product category, collection, and item for a given category code. "
        "Use this to analyse product-level performance within a category."
    ),
)
def sales_by_product(category: str):
    """
    Args:
        category: Product category code, e.g. 'PAKIS'.
    """
    return [row.model_dump() for row in tool_sales_by_product(category)]


@mcp.tool(
    name="sales_by_customer",
    description=(
        "Returns total amount spent (TotalSpent), order frequency, and customer tier "
        "for a specific customer ID. Use this to profile an individual customer's "
        "purchasing behaviour."
    ),
)
def sales_by_customer(customer_id: str):
    """
    Args:
        customer_id: Customer identifier string, e.g. '053240'.
    """
    return [row.model_dump() for row in tool_sales_by_customer(customer_id)]


@mcp.tool(
    name="sales_by_region",
    description=(
        "Aggregates revenue (RegionalRevenue) by country, region, and state "
        "for a named region. Use this for geographic sales analysis."
    ),
)
def sales_by_region(region: str):
    """
    Args:
        region: Region name, e.g. 'NORTHEAST'.
    """
    return [row.model_dump() for row in tool_sales_by_region(region)]


@mcp.tool(
    name="yoy_revenue",
    description=(
        "Computes current-year revenue and compares it to the same month of the "
        "prior year, returning the YoY growth percentage. Use this for year-over-year "
        "revenue trend analysis."
    ),
)
def yoy_revenue(year: int, month: str):
    """
    Args:
        year:  Target year, e.g. 2025.
        month: Full month name, e.g. 'November'.
    """
    return [row.model_dump() for row in tool_yoy_revenue(year, month)]


@mcp.tool(
    name="average_order_value",
    description=(
        "Computes the average invoice value (AverageOrderValue) for a given year "
        "and month, excluding cancelled and voided orders. Use this to track AOV trends."
    ),
)
def average_order_value(year: int, month: str):
    """
    Args:
        year:  Target year, e.g. 2025.
        month: Full month name, e.g. 'November'.
    """
    return [row.model_dump() for row in tool_average_order_value(year, month)]


@mcp.tool(
    name="new_vs_repeat_revenue",
    description=(
        "Splits total revenue into NewCustomerRevenue (first-ever purchase) and "
        "RepeatCustomerRevenue for a given year and month. Use this to understand "
        "customer acquisition vs retention revenue contribution."
    ),
)
def new_vs_repeat_revenue(year: int, month: str):
    """
    Args:
        year:  Target year, e.g. 2025.
        month: Full month name, e.g. 'November'.
    """
    return [row.model_dump() for row in tool_new_vs_repeat_revenue(year, month)]


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting SPARS Sales MCP server on http://localhost:8001/sse")
    mcp.run(transport="http", host="0.0.0.0", port=8001, path="/sse")
