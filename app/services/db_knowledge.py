"""
Shared database knowledge for LangChain and Vanna agents.
Source: "Star Schema Documentation for Data Lens" — VISIONARY COMPUTER SOLUTIONS (PVT) LTD
Database: StarScemaSPARS
Schema: dbo

All column lists are verified against the live database.
The two documented analytics views (VW_SalesByWarehouse, VW_SalesMonthly) may or may not exist
in the database; agents should fall back to querying base tables when the views are unavailable.
"""

# ---------------------------------------------------------------------------
# Official view DDLs (from documentation; use if the view exists in the DB)
# ---------------------------------------------------------------------------

VIEW_SALES_BY_WAREHOUSE = """
CREATE VIEW VW_SalesByWarehouse AS
SELECT
    DW.WarehouseID,
    DW.BranchName,
    DW.City AS WarehouseCity,
    DW.State AS WarehouseState,
    DD.Year,
    DD.MonthName,
    COUNT(DISTINCT FSD.SalesInvoiceNo) AS TotalOrders,
    SUM(FSD.Quantity) AS TotalQuantitySold,
    SUM(FSD.SalesAmount) AS TotalSalesAmount,
    SUM(FSD.ProfitAmount) AS TotalProfit,
    SUM(ISNULL(FSD.ShippingCharges, 0)) AS TotalShipping
FROM FactSalesDetail FSD
LEFT JOIN DimWarehouse DW ON FSD.BranchKey = DW.BranchKey
LEFT JOIN DimDate DD ON FSD.DateKey = DD.DateKey
GROUP BY DW.WarehouseID, DW.BranchName, DW.City, DW.State, DD.Year, DD.MonthName;
"""

VIEW_SALES_MONTHLY = """
CREATE OR ALTER VIEW VW_SalesMonthly AS
SELECT
    DD.Year,
    DD.Month,
    DD.MonthName,
    DD.Quarter,
    COUNT(DISTINCT FSI.SalesInvoiceNo) AS TotalInvoices,
    COUNT(DISTINCT FSI.CustomerKey) AS CustomersCount,
    SUM(FSI.TotalQuantity) AS TotalQuantitySold,
    SUM(FSI.TotalAmount) AS TotalSalesAmount,
    SUM(FSI.TaxAmount) AS TotalTaxCollected,
    SUM(FSI.DiscountAmount) AS TotalDiscountGiven,
    SUM(FSI.MerchandiseAmount) AS MerchandiseRevenue,
    SUM(FSI.ServicesAmount) AS ServicesRevenue,
    AVG(FSI.TotalAmount) AS AvgOrderValue
FROM FactSalesInvoice FSI
LEFT JOIN DimDate DD ON FSI.DateKey = DD.DateKey
GROUP BY DD.Year, DD.Month, DD.MonthName, DD.Quarter;
"""

ALL_VIEW_DDLS: list[str] = [
    VIEW_SALES_BY_WAREHOUSE,
    VIEW_SALES_MONTHLY,
]

# ---------------------------------------------------------------------------
# Full schema documentation (verified live column lists from the database)
# ---------------------------------------------------------------------------

BUSINESS_DOCUMENTATION = """
=== STAR SCHEMA: StarScemaSPARS ===
Designed for Sales, Purchase, Inventory, Profitability, and Customer/Vendor analytics.

This application has read-only database access: NEVER generate CREATE, ALTER, DROP, INSERT,
UPDATE, or DELETE. Execute only SELECT (or WITH ... SELECT) queries.

--- DIMENSION TABLES ---

DimCustomer  — Customer master data for sales and receivable analytics.
  CustomerKey, CustomerID, CustomerCode, CustomerName, CustomerType, Category, Class,
  City, State, Country, Region, Province, Phone, Email, PriceCategory, PaymentTerm,
  SalesDiscount, TaxRate, CreditLimit, Status, IsDropShipOnly, IsSpecialPricing,
  CreatedDate, ModifiedDate

DimDate  — Time dimension used by all fact tables.
  DateKey, FullDate, Year, Quarter, Month, MonthName
  NOTE: Join fact tables to DimDate using DateKey. Use Year, Month, Quarter, MonthName for filtering.

DimProduct  — Product master data for inventory and sales analysis.
  ProductKey, ItemID, ItemCode, ItemName, Category, Collection, Design,
  DesignDescription, Color, ColorDescription, Size, SizeDescription, Brand,
  Country, Vendor, MaterialType, Shape, Weight, Area, Volume,
  IsDiscontinued, Status, SETItem, CreatedDate, ModifiedDate

DimVendors  — Vendor/supplier master data for procurement analytics.
  VendorKey, VendorID, VendorName, VendorType, Category, Class, Region, Status,
  City, State, Country, PaymentTerm, PaymentPriority, TaxRate, CreditLimit,
  FurnitureVendor, DesignerRate, InTransitDays

DimWarehouse  — Warehouse and branch locations.
  BranchKey, WarehouseID, BranchName, City, State, Country, ZIP, Address, Phone, Email,
  ManagerID, StoreType, BusinessDivisionID, BufferQty, TaxID, TimeZoneHours,
  IsActive, WHSStatus, CreatedDate, ModifiedDate
  NOTE: Use BufferQty as the minimum reorder/safety-stock threshold per branch.

DimInvoiceAddresses  — Shipping destination reference per invoice.
  AddressesKey, EDICustomerID, CustomerVendorCode, SalesInvoiceNo,
  S_City, S_State, S_ZIP, S_Country (ship-to address),
  B_City, B_State, B_ZIP, B_Country (bill-to address),
  S_FirstName, S_LastName, S_Address1, S_Address2,
  B_FirstName, B_LastName, B_Address1, B_Address2,
  EffectiveDate, EndDate, IsCurrent
  NOTE: S_ prefix = ship-to; B_ prefix = bill-to. Use S_State/S_City for delivery analytics.

--- FACT TABLES ---

FactSalesInvoice  — Invoice-header level metrics.
  SalesInvoiceKey, SalesInvoiceNo, DateKey, OrderDateKey, CustomerKey, AddressesKey,
  BranchKey, SalesmanKey, PriceCategoryKey, PaymentTermKey,
  SalesType, InvoiceType, Status,
  TotalQuantity, TotalAmount, TaxAmount, ShippingCharges, HandlingCharges,
  ServiceCharges, MerchandiseAmount, ServicesAmount, AppliedAmount,
  AdjustmentAmount, DiscountAmount, TotalWeight
  NOTE: SalesType filter: 'S' = Sales, 'C'/'M' = Credit, 'D' = Debit.
        InvoiceType and Status give further classification.

FactSalesDetail  — Invoice line-level sales details.
  SalesKey, SalesInvoiceNo, InvoiceLineNumber, DateKey, OrderDateKey,
  ProductKey, CustomerKey, BranchKey,
  SalesType, ItemType,
  Quantity, ShippedQuantity, ReturnQuantity,
  UnitPrice, UnitCost, DiscountAmount, SalesAmount, TaxAmount, ShippingCharges,
  ProfitAmount
  NOTE: ProfitAmount = SalesAmount - (UnitCost * Quantity). Use for profitability analysis.

FactPurchaseOrder  — Purchase order header metrics.
  PurchaseOrderKey, PurchaseOrderNo, VendorKey, DateKey, DueDateKey,
  CancelDateKey, CompletionDateKey, WarehouseKey, CustomerKey,
  TotalQty, TotalAmount, TotalTax, InTransitQty, ReceivedQty,
  PaymentDiscount, SalesDiscount, FreightTerm,
  POStatus, DropShipment
  NOTE: POStatus values: Open, Closed, Partially Shipped, Void, New, Cancel.
        DueDateKey = expected receipt date; CompletionDateKey = actual completion date.
        On-time = CompletionDateKey <= DueDateKey. Delayed = CompletionDateKey > DueDateKey.
        Join DueDateKey and CompletionDateKey to DimDate to get Year/Month for date comparisons.

FactPurchaseDetail  — Purchase order line-level details.
  PurchaseLineKey, PurchaseOrderNo, Line_No, VendorKey, ProductKey,
  DateKey, DueDateKey, WarehouseKey, CustomerKey,
  OrderQty, UnitCost, LineAmount, TaxAmount, DiscountPercent,
  InTransitQty, ReceivedQty, Area, Length, ReceivedLength, SQFTCost

FactInventorySnapshot  — Point-in-time inventory position per product per warehouse.
  InventorySnapshotKey, DateKey, ProductKey, BranchKey,
  QuantityOnHand, InventoryValue,
  PickingQuantity, SalesOrderQuantity, DamagedQuantity,
  ShowRoomQuantity, MissingBinQuantity,
  AverageCost, OriginalCost
  NOTE: To find current inventory, use the snapshot with the latest DateKey.
        AvailableQty = QuantityOnHand - PickingQuantity - SalesOrderQuantity.
        Reorder needed when QuantityOnHand < DimWarehouse.BufferQty.

--- ANALYTICS VIEWS (may or may not exist in the database) ---

If the following views exist, prefer them; otherwise query base tables directly:

VW_SalesByWarehouse  — Sales, quantity, profit, and shipping by warehouse and month.
  Columns: WarehouseID, BranchName, WarehouseCity, WarehouseState,
           Year, MonthName, TotalOrders, TotalQuantitySold,
           TotalSalesAmount, TotalProfit, TotalShipping
  Base: FactSalesDetail + DimWarehouse (BranchKey) + DimDate (DateKey)

VW_SalesMonthly  — Monthly sales overview across all invoices.
  Columns: Year, Month, MonthName, Quarter,
           TotalInvoices, CustomersCount, TotalQuantitySold, TotalSalesAmount,
           TotalTaxCollected, TotalDiscountGiven, MerchandiseRevenue,
           ServicesRevenue, AvgOrderValue
  Base: FactSalesInvoice + DimDate (DateKey)

--- QUERY GUIDELINES ---

1. Always use base tables (joining with DimDate and dimension tables) if the views are not available.
2. For time-based filtering: JOIN to DimDate on DateKey and filter on Year, Month, Quarter, MonthName.
3. For current period: use YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
4. For last N months: DimDate.DateKey IN (SELECT DateKey FROM DimDate WHERE FullDate >= DATEADD(MONTH, -N, GETDATE())).
5. For fiscal year comparisons, use DimDate.Year directly.
6. For purchase on-time analysis: join FactPurchaseOrder to DimDate twice (once on DateKey, once on DueDateKey) and compare.
7. For inventory reorder: compare FactInventorySnapshot.QuantityOnHand against DimWarehouse.BufferQty.
8. For profitability: use FactSalesDetail.ProfitAmount or (SalesAmount - UnitCost * Quantity).
9. Generate only a single SELECT (or WITH ... SELECT) statement per query. Do NOT use DECLARE or T-SQL variables; use inline expressions such as YEAR(GETDATE()), DATEADD(), DATEPART() instead.
10. Never use schema-qualified names like dbo.TableName unless needed; just use the table/view name directly.
11. Limit large result sets with TOP N or aggregate appropriately.

--- COMMON QUERY PATTERNS ---

Sales by month (base table):
  SELECT DD.Year, DD.Month, DD.MonthName, DD.Quarter,
         COUNT(DISTINCT FSI.SalesInvoiceNo) AS TotalInvoices,
         SUM(FSI.TotalAmount) AS TotalSalesAmount
  FROM FactSalesInvoice FSI
  JOIN DimDate DD ON FSI.DateKey = DD.DateKey
  GROUP BY DD.Year, DD.Month, DD.MonthName, DD.Quarter

Top N products by revenue:
  SELECT TOP 10 DP.ItemName, DP.Category,
         SUM(FSD.SalesAmount) AS TotalRevenue,
         SUM(FSD.Quantity) AS TotalQty
  FROM FactSalesDetail FSD
  JOIN DimProduct DP ON FSD.ProductKey = DP.ProductKey
  JOIN DimDate DD ON FSD.DateKey = DD.DateKey
  WHERE DD.Year = YEAR(GETDATE())
  GROUP BY DP.ItemName, DP.Category
  ORDER BY TotalRevenue DESC

Current inventory below reorder level:
  SELECT DP.ItemName, DP.Category, DW.BranchName,
         FIS.QuantityOnHand, DW.BufferQty
  FROM FactInventorySnapshot FIS
  JOIN DimProduct DP ON FIS.ProductKey = DP.ProductKey
  JOIN DimWarehouse DW ON FIS.BranchKey = DW.BranchKey
  WHERE FIS.DateKey = (SELECT MAX(DateKey) FROM FactInventorySnapshot)
    AND FIS.QuantityOnHand < DW.BufferQty

Purchase on-time rate by vendor:
  SELECT DV.VendorName,
         COUNT(*) AS TotalPOs,
         SUM(CASE WHEN DD_Complete.FullDate <= DD_Due.FullDate THEN 1 ELSE 0 END) AS OnTimePOs,
         SUM(CASE WHEN DD_Complete.FullDate > DD_Due.FullDate THEN 1 ELSE 0 END) AS DelayedPOs
  FROM FactPurchaseOrder FPO
  JOIN DimVendors DV ON FPO.VendorKey = DV.VendorKey
  JOIN DimDate DD_Due ON FPO.DueDateKey = DD_Due.DateKey
  JOIN DimDate DD_Complete ON FPO.CompletionDateKey = DD_Complete.DateKey
  WHERE FPO.POStatus IN ('Closed', 'Completed')
  GROUP BY DV.VendorName
"""


def get_system_prompt() -> str:
    """Full DB context for LangChain SQL agent (injected as prefix)."""
    view_ddls = (
        "-- VW_SalesByWarehouse (use if view exists, else query FactSalesDetail + DimWarehouse + DimDate)\n"
        + VIEW_SALES_BY_WAREHOUSE.strip()
        + "\n\n"
        + "-- VW_SalesMonthly (use if view exists, else query FactSalesInvoice + DimDate)\n"
        + VIEW_SALES_MONTHLY.strip()
    )
    return (
        "=== DATABASE CONTEXT (read-only, StarScemaSPARS star schema) ===\n\n"
        + BUSINESS_DOCUMENTATION.strip()
        + "\n\n=== ANALYTICS VIEW DEFINITIONS (for reference) ===\n\n"
        + view_ddls
        + "\n\nExecute only SELECT queries. Prefer views when they exist; otherwise query base tables."
    )


def get_training_docs() -> str:
    """Single documentation string for Vanna training (DDLs + full docs)."""
    ddl_block = "\n\n".join(ddl.strip() for ddl in ALL_VIEW_DDLS)
    return (
        "View DDLs (official analytics views):\n\n"
        + ddl_block
        + "\n\n"
        + BUSINESS_DOCUMENTATION.strip()
    )
