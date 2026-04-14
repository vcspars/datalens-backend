"""
Pydantic response models — one per MCP tool.
All fields are Optional to gracefully handle NULL values from SQL Server.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Tool 1: Total Sales by Day/Week/Month/Year ────────────────────────────────
class SalesByPeriodRow(BaseModel):
    Year: Optional[int] = None
    MonthName: Optional[str] = None
    WeekNumber: Optional[int] = None
    SalesDate: Optional[str] = None       # serialised from date
    TotalSales: Optional[float] = None
    InvoiceCount: Optional[int] = None


# ── Tool 2: Sales by Product, Collection, and Category ───────────────────────
class SalesByProductRow(BaseModel):
    Category: Optional[str] = None
    Collection: Optional[str] = None
    Product: Optional[str] = None
    ProductName: Optional[str] = None
    TotalRevenue: Optional[float] = None
    UnitsSold: Optional[float] = None


# ── Tool 3: Sales by Customer and Customer Tier ───────────────────────────────
class SalesByCustomerRow(BaseModel):
    CustomerTier: Optional[str] = None
    CustomerName: Optional[str] = None
    CustomerID: Optional[str] = None
    TotalSpent: Optional[float] = None
    OrderFrequency: Optional[int] = None


# ── Tool 4: Sales by Region and Territory ─────────────────────────────────────
class SalesByRegionRow(BaseModel):
    Country: Optional[str] = None
    RegionName: Optional[str] = None
    State: Optional[str] = None
    RegionalRevenue: Optional[float] = None


# ── Tool 5: Revenue vs. Same Period Last Year (YoY) ───────────────────────────
class YoYRevenueRow(BaseModel):
    MonthName: Optional[str] = None
    CurrentYear: Optional[int] = None
    CurrentYearRevenue: Optional[float] = None
    LastYearRevenue: Optional[float] = None
    YoY_Growth_Percentage: Optional[float] = None


# ── Tool 6: Average Order Value (AOV) ─────────────────────────────────────────
class AOVRow(BaseModel):
    Year: Optional[int] = None
    MonthName: Optional[str] = None
    AverageOrderValue: Optional[float] = None


# ── Tool 7: New vs. Repeat Customer Revenue ───────────────────────────────────
class NewVsRepeatRow(BaseModel):
    Year: Optional[int] = None
    MonthName: Optional[str] = None
    NewCustomerRevenue: Optional[float] = None
    RepeatCustomerRevenue: Optional[float] = None
