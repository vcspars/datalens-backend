"""
Shared database knowledge for LangChain and Vanna agents.
Source: "Star Schema Documentation for Data Lens" — VISIONARY COMPUTER SOLUTIONS (PVT) LTD
         Prepared by Zahid Iqbal & Muhammad Numan, 2/24/2026
Database: StarScemaSPARS
Schema: dbo

All 26 tables (9 Dimension + 17 Fact) and 5 analytics views are documented below.
The agents MUST only generate read-only SELECT queries.
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

VIEW_CUSTOMER_CREDIT_YEARLY = """
CREATE VIEW VW_CustomerCreditYearly AS
SELECT
    dc.CustomerID,
    d.Year,
    SUM(fc.TotalAmount) AS TotalCredit
FROM FactCreditMemo fc
JOIN DimCustomer dc ON fc.CustomerKey = dc.CustomerKey
JOIN DimDate d ON fc.InvoiceDateKey = d.DateKey
GROUP BY dc.CustomerID, d.Year;
"""

VIEW_CUSTOMER_PAYMENT = """
CREATE VIEW VW_CustomerPayment AS
SELECT
    dc.CustomerID,
    SUM(fcp.Amount) AS PaymentReceived,
    SUM(fcp.AppliedAmount) AS AppliedAmount,
    SUM(fcp.Amount - fcp.AppliedAmount) AS PendingAmount
FROM FactCustomerPayment fcp
JOIN DimCustomer dc ON fcp.CustomerKey = dc.CustomerKey
GROUP BY dc.CustomerID;
"""

VIEW_VENDOR_RETURN_QTY_MONTHLY = """
CREATE VIEW VW_VendorReturnQtyMonthly AS
SELECT
    dv.VendorID,
    d.Year,
    d.MonthName,
    SUM(fvid.ReturnQty) AS ReturnQty
FROM FactVendorInvoiceDetail fvid
JOIN DimVendors dv ON fvid.VendorKey = dv.VendorKey
JOIN DimDate d ON fvid.DateKey = d.DateKey
GROUP BY dv.VendorID, d.Year, d.MonthName;
"""

ALL_VIEW_DDLS: list[str] = [
    VIEW_SALES_BY_WAREHOUSE,
    VIEW_SALES_MONTHLY,
    VIEW_CUSTOMER_CREDIT_YEARLY,
    VIEW_CUSTOMER_PAYMENT,
    VIEW_VENDOR_RETURN_QTY_MONTHLY,
]

# ---------------------------------------------------------------------------
# Full schema documentation — ALL 26 tables + 5 views
# ---------------------------------------------------------------------------

BUSINESS_DOCUMENTATION = """
=== STAR SCHEMA: StarScemaSPARS ===
Designed for: Sales Analysis, Purchase Analysis, Inventory Monitoring, Profitability Reporting,
Customer & Vendor Analytics, Customer Returns & Payments, Vendor Returns & Payments, Back Order Information.

*** READ-ONLY ACCESS ONLY ***
This application has STRICTLY read-only database access.
NEVER generate CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, TRUNCATE, EXEC, EXECUTE, MERGE, or any DDL/DML.
Execute ONLY SELECT (or WITH ... SELECT) queries. Any non-SELECT query will be rejected.

================================================================
                    DIMENSION TABLES (9)
================================================================

DimCustomer  — Customer master data for sales and receivable analytics.
  CustomerKey          (Surrogate key, PK)
  CustomerID           (Business identifier from source systems)
  CustomerCode         (Alternate reference code)
  CustomerName         (Full customer or company name)
  CustomerType         (Retail, Wholesale, or other classification)
  Category             (Segmentation grouping)
  Class                (Internal classification)
  City                 (Customer city)
  State                (Customer state or province)
  Country              (Customer country)
  Region               (Geographic region)
  Province             (Province if applicable)
  Phone                (Primary phone number)
  Email                (Primary email address)
  PriceCategory        (Assigned pricing tier)
  PaymentTerm          (Default payment terms)
  SalesDiscount        (Default discount percentage)
  TaxRate              (Default tax rate applied)
  CreditLimit          (Maximum credit allowed)
  Status               (Account status)
  IsDropShipOnly       (Drop-ship only flag)
  IsSpecialPricing     (Flag indicating if special pricing rules apply)
  CreatedDate          (Record creation timestamp)
  ModifiedDate         (Last modification timestamp)

DimDate  — Time dimension supporting all fact tables.
  DateKey              (Surrogate date key, PK)
  FullDate             (Actual calendar date)
  Year                 (Year component)
  Quarter              (Quarter number)
  Month                (Month number)
  MonthName            (Month name)
  NOTE: Join fact tables to DimDate using DateKey. Use Year, Month, Quarter, MonthName for filtering.

DimProduct  — Product master data for inventory and sales analysis.
  ProductKey           (Surrogate product key, PK)
  ItemID               (Unique business identifier for the product)
  ItemCode             (Secondary code)
  ItemName             (Product name or description)
  Category             (Product category)
  Collection           (Collection or series)
  Design               (Pattern or design)
  Color                (Primary color)
  Size                 (Dimensions)
  Brand                (Brand name)
  Country              (Country of origin)
  Vendor               (Default supplier)
  MaterialType         (Composition material — e.g. Wool, Silk)
  Shape                (Shape — e.g. Rectangular, Round)
  Weight               (Product weight)
  Area                 (Surface area)
  Volume               (Volume)
  IsDiscontinued       (Flag indicating if product is no longer for sale)
  Status               (Lifecycle status)
  CreatedDate          (Creation timestamp)
  ModifiedDate         (Last update timestamp)

DimVendors  — Vendor/supplier master data for procurement analytics.
  VendorKey            (Surrogate vendor key, PK)
  VendorID             (Business vendor identifier)
  VendorName           (Full company name of the supplier)
  VendorType           (Vendor classification)
  Category             (Business category)
  Class                (Priority or quality class)
  Region               (Geographic region)
  Status               (Current relationship status — Active, Hold, etc.)
  City                 (Vendor city)
  State                (Vendor state)
  Country              (Vendor country)
  PaymentTerm          (Payment terms)
  PaymentPriority      (Settlement priority)
  TaxRate              (Tax percentage applied to vendor invoices)
  CreditLimit          (Vendor credit limit)
  FurnitureVendor      (Furniture supplier flag)
  DesignerRate         (Special percentage rate for designers)
  InTransitDays        (Estimated delivery time from vendor)
  EffectiveDate        (Record effective date)

DimWarehouse  — Warehouse and branch locations.
  BranchKey            (Surrogate branch key, PK)
  WarehouseID          (Business location identifier)
  BranchName           (Descriptive name of the branch/warehouse)
  City                 (City)
  State                (State)
  Country              (Country)
  ZIP                  (Postal code)
  Address              (Street address)
  Phone                (Contact number)
  Email                (Contact email)
  ManagerID            (Manager identifier)
  StoreType            (Location type)
  BusinessDivisionID   (Division mapping)
  BufferQty            (Safety stock / minimum reorder quantity per branch)
  TaxID                (Tax identifier)
  TimeZoneHours        (UTC offset)
  IsActive             (Operational flag)
  WHSStatus            (Warehouse status)
  CreatedDate          (Creation timestamp)
  ModifiedDate         (Last update timestamp)

DimInvoiceAddresses  — Shipping destination reference per invoice.
  AddressesKey         (Surrogate key, PK)
  State                (Destination state)
  City                 (Destination city)
  Country              (Destination country)

DimPaymentTerms  — Payment term definitions.
  PaymentTermKey       (Surrogate key, PK)
  PaymentTermNo        (Business key / term code)
  Description          (Term description)
  DueDays              (Number of days until payment is due)
  DiscountDays         (Days within which early payment discount applies)
  PaymentDiscount      (Discount percentage if paid early)
  CreditCardTerms      (Flag for credit card terms)
  SQFTPrice            (Cost/price per square foot — for rugs)
  OrgCost              (Original cost per unit)

DimPriceCategory  — Price category definitions.
  PriceCategoryKey     (Surrogate key, PK)
  CategoryNo           (Business key / category code)
  Description          (Category description)
  Blocked              (Flag indicating if category is inactive)

DimSalesOrderDetail_Log  — Sales order detail log for back-order tracking.
  SalesOrderNo         (Order number)
  ItemID               (Item ID)
  SKU                  (Stock keeping unit ID)
  LogSource            (Log source)
  LogReason            (Log reason)
  BackOrder            (Flag Yes/No — whether item is on back order)
  LogDate              (Back order created date or released date)
  NOTE: Use this table for back-order history and analysis. Filter on BackOrder = 'Yes' for active back orders.

================================================================
                      FACT TABLES (17)
================================================================

FactSalesInvoice  — Invoice-header level metrics.
  SalesInvoiceKey      (Surrogate key, PK)
  SalesInvoiceNo       (Sales invoice number)
  DateKey              (FK → DimDate — invoice date)
  OrderDateKey         (FK → DimDate — order date)
  CustomerKey          (FK → DimCustomer)
  AddressesKey         (FK → DimInvoiceAddresses — shipping destination)
  BranchKey            (FK → DimWarehouse — fulfillment branch)
  PaymentTermKey       (FK → DimPaymentTerms)
  SalesType            (Sales classification: 'SO0' = Sales Orders, 'CS0' = Credit/Service. Do NOT filter unless user asks.)
  InvoiceType          (Document type)
  Status               (Invoice status)
  TotalQuantity        (Total quantity)
  TotalAmount          (Total amount)
  TaxAmount            (Tax total)
  ShippingCharges      (Shipping fees)
  HandlingCharges      (Handling fees)
  ServiceCharges       (Service fees)
  MerchandiseAmount    (Merchandise value)
  ServicesAmount       (Service revenue)
  AppliedAmount        (Applied payments)
  AdjustmentAmount     (Adjustments)
  DiscountAmount       (Discounts)
  TotalWeight          (Total shipment weight)

FactSalesDetail  — Invoice line-level sales details.
  SalesKey             (Surrogate key, PK)
  SalesInvoiceNo       (Sales invoice number)
  InvoiceLineNumber    (Line number within invoice)
  DateKey              (FK → DimDate — invoice date)
  OrderDateKey         (FK → DimDate — order date)
  ProductKey           (FK → DimProduct)
  CustomerKey          (FK → DimCustomer)
  BranchKey            (FK → DimWarehouse)
  SalesType            (Sale item classification: 'SO0' = Sales Orders, 'CS0' = Credit/Service. Do NOT filter unless user asks.)
  ItemType             (Sale item category)
  Quantity             (Quantity sold)
  ShippedQuantity      (Quantity physically sent to customer)
  ReturnQuantity       (Quantity returned after sale)
  UnitPrice            (Price charged per unit)
  UnitCost             (Cost per unit at time of sale)
  DiscountAmount       (Discount on this line)
  SalesAmount          (Net sales amount)
  TaxAmount            (Tax allocated to this line)
  ShippingCharges      (Shipping fees allocated to this line)
  ProfitAmount         (Net profit = SalesAmount - (UnitCost * Quantity))

FactPurchaseOrder  — Purchase order header metrics.
  PurchaseOrderKey     (Surrogate key, PK)
  PurchaseOrderNo      (Purchase order number)
  VendorKey            (FK → DimVendors)
  DateKey              (FK → DimDate — issue date)
  DueDateKey           (FK → DimDate — expected receipt date)
  CancelDateKey        (FK → DimDate — cancellation date)
  CompletionDateKey    (FK → DimDate — actual completion date)
  WarehouseKey         (FK → DimWarehouse — receiving warehouse)
  CustomerKey          (FK → DimCustomer)
  TotalQty             (Total items quantity)
  TotalAmount          (Grand total amount)
  TotalTax             (Total tax)
  InTransitQty         (Quantity currently shipping from vendor)
  ReceivedQty          (Received quantity)
  PaymentDiscount      (Discount for early payment terms)
  SalesDiscount        (Trade discount provided by vendor)
  FreightTerm          (Freight terms)
  POStatus             (Status: Open, Closed, Partially Shipped, Void, New, Cancel)
  DropShipment         (Flag for direct-to-customer shipments: 1=Yes, 0=No)
  NOTE: On-time = CompletionDateKey <= DueDateKey. Delayed = CompletionDateKey > DueDateKey.
        Join DueDateKey and CompletionDateKey to DimDate for date comparisons.

FactPurchaseDetail  — Purchase order line-level details.
  PurchaseLineKey      (Surrogate key, PK)
  PurchaseOrderNo      (Purchase order number)
  Line_No              (Line number)
  VendorKey            (FK → DimVendors)
  ProductKey           (FK → DimProduct)
  DateKey              (FK → DimDate — issue date)
  DueDateKey           (FK → DimDate — expected receipt date)
  WarehouseKey         (FK → DimWarehouse — destination warehouse)
  CustomerKey          (FK → DimCustomer)
  OrderQty             (Quantity requested from vendor)
  UnitCost             (Cost per unit)
  LineAmount           (Total line cost amount)
  TaxAmount            (Line tax amount)
  DiscountPercent      (Discount percent for this line item)
  InTransitQty         (Quantity currently mid-shipment)
  ReceivedQty          (Received quantity)
  SQFTCost             (Cost per square foot)

FactInventorySnapshot  — Current inventory position per product per warehouse.
  InventorySnapshotKey (Surrogate key, PK)
  ProductKey           (FK → DimProduct)
  BranchKey            (FK → DimWarehouse)
  QuantityOnHand       (Available quantity)
  InventoryValue       (Inventory value)
  PickingQuantity      (Allocated for picking)
  SalesOrderQuantity   (Reserved for sales orders)
  DamagedQuantity      (Damaged stock)
  ShowRoomQuantity     (Display stock)
  MissingBinQuantity   (Missing stock)
  AverageCost          (Average cost)
  OriginalCost         (Original cost)
  *** WARNING: This table has NO DateKey column. Do NOT use DateKey or MAX(DateKey) filters. ***
  Query it directly — it represents current inventory state.
  AvailableQty = QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0).
  Reorder needed when QuantityOnHand < DimWarehouse.BufferQty.

FactVendorInvoices  — Vendor invoices (accounts payable).
  PayableInvoiceNo     (Primary key — payable invoice number)
  VendorKey            (FK → DimVendors)
  InvoiceType          (Code classifying the invoice type)
  PaymentTermKey       (FK → DimPaymentTerms)
  Status               (Current invoice status)
  VendorInvoiceRef     (Vendor's reference/invoice number)
  VendorInvoiceDateKey (FK → DimDate)
  DueDateKey           (FK → DimDate)
  DiscountDateKey      (FK → DimDate)
  CutOffDateKey        (FK → DimDate)
  TotalAmount          (Total invoice amount before payments/adjustments)
  PaidAmount           (Amount already paid to the vendor)
  DiscountAmount       (Early payment discount offered by vendor)
  DiscountAvailed      (Discount actually taken/applied)
  AdjustmentAmount     (Manual adjustments — returns, quality issues, etc.)
  ApprovedAmount       (Amount approved for payment by management)
  ApprovedDiscount     (Discount amount approved)
  ApprovedAdjustment   (Adjustment amount approved)
  PaymentAccount       (Account code where payment is recorded)
  OtherChargesAccount  (Account for freight, handling, or other charges)
  WarehouseKey         (FK → DimWarehouse)
  PeriodID             (Accounting period identifier)

FactVendorPayments  — Vendor payments (outgoing payments to vendors).
  PaymentNo            (Primary key — payment number)
  VendorKey            (FK → DimVendors)
  DocDateKey           (FK → DimDate — document date)
  PaymentDateKey       (FK → DimDate — payment date)
  PaymentAccount       (Bank or cash account debited for payment)
  DiscountAccount      (Account where discount taken is recorded)
  DocType              (Document type code)
  Amount               (Total payment amount sent to vendor)
  AppliedAmount        (Amount applied to outstanding invoices)
  AppliedDiscount      (Discount amount deducted from payment)
  Status               (Payment status)
  PaymentType          (Method of payment)
  PeriodID             (Accounting period identifier)
  VoidDateKey          (FK → DimDate — void date if payment was voided)

FactCustomerReturn  — Customer return headers.
  ReturnHeaderKey      (Surrogate key, PK)
  CustomerReturnNo     (Unique business identifier for the return)
  SalesInvoiceNo       (Original sales invoice number)
  CreditMemoNo         (Credit memo issued for this return)
  CustomerKey          (FK → DimCustomer)
  DateReceivedKey      (FK → DimDate — date return was received)
  CreditDateKey        (FK → DimDate — date credit was issued)
  InvoiceDateKey       (FK → DimDate — date of the original sales invoice)
  ReceiptType          (Type of receipt)
  Status               (Return status)
  ReceivingBin         (Warehouse bin where returned items are stored)
  TotalQty             (Total quantity of items returned)
  TotalAmount          (Total value/credit amount for the return)
  ShippingHandlingAmount  (Return shipping and handling charges)
  QtyToWarehouse       (Quantity accepted and sent to warehouse)
  TotalBales           (For rugs/large items: number of bales/packages)

FactCustomerReturnDetail  — Customer return line-level details.
  ReturnKey            (Surrogate key, PK)
  CustomerReturnNo     (Business identifier for the return)
  SalesInvoiceNo       (Original sales invoice number)
  CustomerKey          (FK → DimCustomer)
  DateReceivedKey      (FK → DimDate)
  ProductKey           (FK → DimProduct)
  ReturnReason         (Reason for return)
  ReturnQty            (Quantity returned)
  CreditQty            (Quantity credited)
  Cost                 (Product cost)
  Price                (Selling price)
  Discount             (Discount that was applied)
  ExtPrice             (Extended price — credit amount for this line)
  TaxAmount            (Tax on the credit)
  SQFTPrice            (Cost/price per square foot — for rugs)
  OrgCost              (Original cost per unit)

FactCreditMemo  — Credit memo headers (credits issued to customers).
  CreditMemoKey        (Surrogate key, PK)
  CreditMemoNo         (Business identifier for the credit memo)
  CustomerKey          (FK → DimCustomer)
  SalesInvoiceNo       (Original sales invoice number)
  CustomerReturnNo     (Related customer return number)
  BranchKey            (FK → DimWarehouse)
  CreditDateKey        (FK → DimDate — date credit was issued)
  InvoiceDateKey       (FK → DimDate — original invoice date)
  OrderDateKey         (FK → DimDate — original order date)
  ShippedDateKey       (FK → DimDate — shipped date)
  TotalQty             (Total quantity of items on the credit memo)
  TotalQtyInvoiced     (Total quantity originally invoiced)
  TotalMerchandise     (Value of merchandise only, excluding services)
  TotalServices        (Value of services, if any)
  TotalAmount          (Total credit memo amount before adjustments)
  TaxAmount            (Tax amount on the credit)
  ShippingCharges      (Return shipping charges)
  HandlingCharges      (Handling charges)
  ServiceCharges       (Service charges, if applicable)
  DiscountAmount       (Discount applied to the credit)
  OpenCredit           (Remaining unapplied credit amount)
  AppliedAmount        (Amount of credit already applied to invoices)
  CreditApplied        (Flag indicating if credit has been applied)
  Status               (Credit status)
  InvoiceType          (Type of document)
  SalesType            (Sales type code)
  PriceCategoryKey     (FK → DimPriceCategory — pricing tier applied)
  PaymentTermKey       (FK → DimPaymentTerms)

FactCreditMemoDetail  — Credit memo line-level details.
  SalesKey             (Credit detail key, PK)
  CreditMemoNo         (Business identifier for the credit memo)
  InvoiceLineNumber    (Line number)
  SalesInvoiceNo       (Original sales invoice number)
  BranchKey            (FK → DimWarehouse)
  InvoiceDateKey       (FK → DimDate)
  OrderDateKey         (FK → DimDate)
  ProductKey           (FK → DimProduct)
  CustomerKey          (FK → DimCustomer)
  SalesType            (Type of sales)
  ItemType             (Item category)
  Quantity             (Quantity credited)
  ShippedQuantity      (Quantity originally shipped)
  ReturnQuantity       (Quantity returned, if credit is for a return)
  UnitPrice            (Original unit price)
  UnitCost             (Original unit cost)
  DiscountAmount       (Discount applied on this line)
  SalesAmount          (Extended credit amount after discount)
  TaxAmount            (Tax on the credit line)
  ShippingCharges      (Shipping charges allocated to this line)

FactCustomerPayment  — Customer payments (incoming cash receipts).
  CashReceiptNo        (Unique identifier for the cash receipt, PK)
  CustomerKey          (FK → DimCustomer — customer making the payment)
  SalesInvoice         (Sales invoice number)
  DocDateKey           (FK → DimDate — document date)
  PaymentDateKey       (FK → DimDate — payment date)
  ApprovedDateKey      (FK → DimDate — approval date)
  BounceDateKey        (FK → DimDate — bounce date if payment bounced)
  CashAccount          (Account receiving payment)
  CreditAccount        (Account credit — revenue/receivable)
  DiscountAccount      (Account for discount)
  DocType              (Payment method)
  Amount               (Total payment amount received)
  AppliedAmount        (Amount applied to outstanding invoices)
  AppliedDiscount      (Discount given for early payment)
  Status               (Payment status)
  Approved             (Flag: approved)
  PeriodID             (Accounting period identifier)

FactCustomerApplication  — Payment-to-invoice application (a single customer payment often applies to multiple invoices).
  CRBatchApplicationNo (Batch application number, PK)
  LineNo               (Line sequence within the batch)
  CustomerKey          (FK → DimCustomer)
  SalesInvoiceNo       (Sales invoice number)
  CashReceiptNo        (Payment being applied)
  CreditMemo           (Credit memo being applied)
  DocDateKey           (FK → DimDate)
  TransactionDateKey   (FK → DimDate)
  ControlAccount       (Control/suspense account)
  DiscountAccount      (Account for discount)
  InvoiceBalance       (Outstanding balance on the invoice before application)
  AppliedAmount        (Amount of payment/credit applied to the invoice)
  DiscountAmount       (Discount taken on this application)
  DocType              (Document type)
  WriteOff             (Flag indicating if any amount was written off)
  PeriodID             (Accounting period identifier)

FactVendorInvoiceDetail  — Vendor invoice line-level details (products received per vendor invoice).
  VendorInvoiceDetailKey  (Surrogate key, PK)
  PayableInvoiceNo     (Payable invoice number — FK → FactVendorInvoices)
  Line_No              (Line sequence number within the invoice)
  VendorKey            (FK → DimVendors)
  ProductKey           (FK → DimProduct)
  DateKey              (FK → DimDate)
  WarehouseKey         (FK → DimWarehouse)
  BaleNumber           (Bale or package identifier)
  Description          (Item description from invoice)
  ItemType             (Item classification)
  VendorStyle          (Vendor's style code for the item)
  OrderQty             (Quantity ordered from vendor)
  ReceivedQty          (Quantity actually received)
  ReturnQty            (Quantity returned to vendor)
  Cost                 (Unit cost from vendor)
  ExtCost              (Extended cost = Cost × ReceivedQty)
  TaxRate              (Tax rate applied to this line)
  ExtTax               (Extended tax amount = TaxRate × ExtCost)
  Category             (Product category code)
  Collection           (Collection identifier)
  Design               (Design code or ID)
  PONo                 (Purchase order number)
  POQty                (Quantity on PO)
  ReceiveBin           (Warehouse bin where item is stored)
  LotNo                (Lot number for batch tracking)

FactCustomerDebit  — Customer debit adjustments (summary-level).
  CreditMemoKey        (Surrogate key, PK — IDENTITY)
  CustomerDebitNo      (Business key — the actual debit number from the ERP)
  CustomerKey          (FK → DimCustomer)
  InvoiceNo            (Reference to the original sales invoice, if applicable)
  BranchKey            (FK → DimWarehouse — which location issued the debit)
  CreditDateKey        (FK → DimDate — date the debit was issued)
  InvoiceDateKey       (FK → DimDate — date of the original invoice)
  OrderDateKey         (FK → DimDate — original order date)
  ADDDateKey           (FK → DimDate — system entry date)
  TotalQty             (Total quantity of items being debited)
  TotalQtyInvoiced     (Total quantity originally invoiced)
  TotalMerchandise     (Value of physical goods being debited)
  TotalServices        (Value of services being debited)
  TotalAmount          (Final total amount of the debit)
  TaxAmount            (Tax amount being reversed or adjusted)
  ShippingCharges      (Shipping costs in the debit)
  HandlingCharges      (Handling fees in the debit)
  ServiceCharges       (Fees for services associated with this debit)
  SalesDiscount        (Additional sales discounts applied)
  PaymentDiscountAmount  (Cash/payment discounts reversed or applied)
  OpenCredit           (Remaining balance of the credit yet to be used)
  AppliedAmount        (Portion of the credit already applied to other invoices)
  CreditApplied        (Flag 0/1 indicating if credit is fully applied)
  Status               (Current state: Open, Applied, Void, Pending)
  InvoiceType          (Internal code for the document type)
  SalesType            (Classification: 'RET' = Retail, 'WHL' = Wholesale, etc.)

FactVendorReturn  — Vendor return headers (goods returned to vendors).
  VendorReturnKey      (Surrogate key, PK)
  VendorReturnNo       (Unique vendor return number)
  VendorKey            (FK → DimVendors)
  PaymentTermKey       (FK → DimPaymentTerms)
  InvoiceType          (Type of return)
  Status               (Return status)
  VendorInvoiceRef     (Vendor's invoice or reference number)
  PurchaseReceiptNo    (Associated purchase receipt number)
  VendorReturnDateKey  (FK → DimDate — return date)
  EntryDateKey         (FK → DimDate — entry date)
  DueDateKey           (FK → DimDate)
  DiscountDateKey      (FK → DimDate)
  CutOffDateKey        (FK → DimDate)
  WarehouseKey         (FK → DimWarehouse)
  TotalAmount          (Total value of goods being returned)
  PaidAmount           (Amount already paid or credited by the vendor)
  DiscountAvailed      (Discount amount actually taken/applied)
  AdjustmentAmount     (Manual adjustments made to the return amount)
  ApprovedAmount       (Final amount approved for credit by vendor)
  ApprovedDiscount     (Discount amount approved by vendor)
  ApprovedAdjustment   (Adjustment amount approved by vendor)
  PaymentAccount       (Account code where return is recorded)
  OtherChargesAccount  (Account code for freight, handling, restocking, or other charges)
  PeriodID             (Accounting period identifier)

FactVendorReturnDetail  — Vendor return line-level details.
  VendorReturnDetailKey  (Surrogate key, PK)
  VendorReturnNo       (Return number)
  Line_No              (Line sequence number)
  VendorKey            (FK → DimVendors)
  ProductKey           (FK → DimProduct)
  DateKey              (FK → DimDate)
  BaleNumber           (Bale or package identifier)
  Description          (Item description)
  ItemType             (Item classification)
  VendorStyle          (Vendor's style code for the item)
  OrderQty             (Quantity ordered from vendor)
  ReceivedQty          (Quantity actually received)
  ReturnQty            (Quantity returned to vendor)
  Cost                 (Unit cost from vendor)
  ExtCost              (Extended cost = Cost × ReceivedQty)
  TaxRate              (Tax rate applied to this line)
  ExtTax               (Extended tax amount)
  SKU                  (Stock keeping unit ID)
  PONo                 (Purchase order number)
  ReceiveBin           (Receive bin)
  LotNo                (Lot number)

================================================================
                     ANALYTICS VIEWS (5)
================================================================
If the following views exist in the database, prefer them for relevant queries;
otherwise query the underlying base tables directly.

VW_SalesByWarehouse  — Sales, quantity, profit, and shipping by warehouse and month.
  Columns: WarehouseID, BranchName, WarehouseCity, WarehouseState,
           Year, MonthName, TotalOrders, TotalQuantitySold,
           TotalSalesAmount, TotalProfit, TotalShipping
  NOTE: TotalSalesAmount here = SUM(FactSalesDetail.SalesAmount) — line-level net sales,
        not MerchandiseAmount. Do not compare directly to FactSalesInvoice revenue figures.
  Base tables: FactSalesDetail + DimWarehouse (BranchKey) + DimDate (DateKey)

VW_SalesMonthly  — Monthly sales overview across all invoices.
  Columns: Year, Month, MonthName, Quarter,
           TotalInvoices, CustomersCount, TotalQuantitySold, TotalSalesAmount,
           TotalTaxCollected, TotalDiscountGiven, MerchandiseRevenue,
           ServicesRevenue, AvgOrderValue
  Base tables: FactSalesInvoice + DimDate (DateKey)

VW_CustomerCreditYearly  — Yearly credit totals per customer.
  Columns: CustomerID, Year, TotalCredit
  Base tables: FactCreditMemo + DimCustomer (CustomerKey) + DimDate (InvoiceDateKey)

VW_CustomerPayment  — Customer payment summary.
  Columns: CustomerID, PaymentReceived, AppliedAmount, PendingAmount
  Base tables: FactCustomerPayment + DimCustomer (CustomerKey)

VW_VendorReturnQtyMonthly  — Monthly vendor return quantities.
  Columns: VendorID, Year, MonthName, ReturnQty
  Base tables: FactVendorInvoiceDetail + DimVendors (VendorKey) + DimDate (DateKey)

================================================================
                     QUERY GUIDELINES
================================================================

================================================================
  METRIC DEFINITIONS (CRITICAL — use the correct column)
================================================================
"Sales" / "Revenue" = FactSalesInvoice.MerchandiseAmount (pure merchandise value — excludes tax, shipping, handling).
  NEVER use TotalAmount for "sales" or "revenue" — TotalAmount = MerchandiseAmount + TaxAmount + ShippingCharges + HandlingCharges + ServiceCharges.
  Only use TotalAmount when the user explicitly asks for "total invoice amount" or "total amount including everything".
"Profit" = FactSalesDetail.ProfitAmount (already computed: SalesAmount − UnitCost × Quantity).
"Net Quantity Sold" = SUM(FSD.Quantity - ISNULL(FSD.ReturnQuantity, 0)) from FactSalesDetail.
  ALWAYS net out returns. FactSalesDetail.ReturnQuantity exists and must be subtracted.
"Net Line Revenue" = FactSalesDetail.SalesAmount (already net at line level — use for product-level detail).
"Invoice Count" = COUNT(*) from FactSalesInvoice — but filter out void/cancelled.
"Customer Count" / "Vendor Count" = COUNT with Status filter (see DEFAULT FILTERS below).

For monthly/quarterly/yearly aggregated sales:
  PREFERRED: Use VW_SalesMonthly view (has both TotalSalesAmount and MerchandiseRevenue columns).
  Use MerchandiseRevenue from VW_SalesMonthly for "sales" questions.

================================================================
  DEFAULT FILTERS (ALWAYS apply unless user says otherwise)
================================================================
- FactSalesInvoice: Do NOT include void/cancelled invoices in totals.
  Add: WHERE FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed') — or similar exclusion.
  Only count/sum active invoices.
- FactPurchaseOrder: WHERE FPO.POStatus NOT IN ('Void', 'Cancel') for totals/counts.
  Only include Void/Cancel when user asks "by status" breakdowns.
- DimCustomer: WHERE DC.Status = 'Active' for customer COUNTS and "how many customers" questions.
  For revenue analysis, include all customers (they may be inactive now but had past revenue).
- DimWarehouse: WHERE DW.IsActive = 1 when listing/counting active warehouses.
  For historical sales analysis, include all warehouses.
- DimProduct: WHERE DP.IsDiscontinued = 0 for product analysis (unless user asks about discontinued).
- FactVendorPayments: WHERE FVP.VoidDateKey IS NULL to exclude voided payments.
- SalesType: Actual values are 'SO0' (Sales Orders) and 'CS0' (Credit/Service).
  Do NOT filter on SalesType by default. Only filter when user explicitly asks to separate types.
- NULL grouping columns: When GROUP BY a nullable column (Region, Category, etc.),
  add WHERE column IS NOT NULL to avoid NULL group unless user wants to see NULLs.

================================================================
  ANTI-PATTERNS (NEVER DO — these produce wrong results)
================================================================
AP1. NEVER JOIN FactSalesInvoice WITH FactSalesDetail in the same aggregation query.
     Each invoice has multiple detail lines → joining them causes a fan-out that MULTIPLIES amounts.
     Use ONE table per query:
       - FactSalesInvoice alone for invoice-level metrics (revenue, tax, discount totals, invoice count)
       - FactSalesDetail alone for product-level metrics (product sales, profit, line quantities)
     NEVER: SELECT SUM(FSI.TotalAmount) FROM FactSalesInvoice FSI JOIN FactSalesDetail FSD ...
     This produces wildly inflated numbers.

AP2. NEVER use TotalAmount when user asks for "sales" or "revenue".
     TotalAmount includes tax + shipping + handling + services.
     Use MerchandiseAmount from FactSalesInvoice, or SalesAmount from FactSalesDetail.

AP3. NEVER forget to net out returns.
     FactSalesDetail has both Quantity and ReturnQuantity.
     Net quantity = SUM(FSD.Quantity - ISNULL(FSD.ReturnQuantity, 0))

AP4. NEVER use DateKey on FactInventorySnapshot — that column does NOT exist.
     Query FactInventorySnapshot directly without date filters.

AP5. NEVER use >= YEAR(GETDATE())-N for "last N years" — it includes future data.
     Use: WHERE DD.Year BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE())

AP6. NEVER query the wrong fact table for a domain:
     - Vendor returns → FactVendorReturn / FactVendorReturnDetail (NOT DimVendors)
     - Customer returns → FactCustomerReturn / FactCustomerReturnDetail
     - Credit memos → FactCreditMemo / FactCreditMemoDetail

AP7. NEVER omit Status filters when computing totals (see DEFAULT FILTERS above).

AP8. Table name accuracy: FactVendorPayments (with 's'), FactVendorInvoices (with 's').

================================================================
  CONSISTENCY RULES (same question = same SQL every time)
================================================================
- For the SAME type of question, ALWAYS use the SAME table and metric column.
  "Total sales by quarter" → ALWAYS use VW_SalesMonthly.MerchandiseRevenue or FactSalesInvoice.MerchandiseAmount
  "Top customers by revenue" → ALWAYS use FactSalesInvoice.MerchandiseAmount (header table, no fan-out)
  "Top products by sales" → ALWAYS use FactSalesDetail.SalesAmount (detail table for product-level)
  "Top products by profit" → ALWAYS use FactSalesDetail.ProfitAmount
- Do NOT add arbitrary filters that the user didn't ask for (like SalesType, Status exclusions beyond the defaults).
- Do NOT add redundant WHERE clauses like WHERE DD.FullDate <= GETDATE() — all historical data already qualifies.

--- GENERAL RULES ---
1. PREFER VIEWS AND HEADER TABLES FOR SPEED:
   - For monthly/quarterly/yearly sales totals, revenue, invoice counts → use VW_SalesMonthly (pre-aggregated, very fast).
   - For warehouse-level sales → use VW_SalesByWarehouse.
   - For customer-level revenue totals → use FactSalesInvoice.MerchandiseAmount joined with DimCustomer.
   - ONLY use FactSalesDetail (3.4M rows) when you need PRODUCT-level detail, line-level profit, or unit cost.
   - For purchase totals: use FactPurchaseOrder (header). Use FactPurchaseDetail only for line-level product detail.
2. Generate only a single SELECT (or WITH ... SELECT) statement per query.
   Do NOT use DECLARE or T-SQL variables; use inline expressions such as YEAR(GETDATE()), DATEADD(), DATEPART().
3. Never use schema-qualified names like dbo.TableName unless needed.

--- TIME / DATE RULES ---
4. For time-based filtering: JOIN to DimDate on DateKey and filter on Year, Month, Quarter, MonthName.
5. For current period: use YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
6. For last N years: WHERE DD.Year BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE()).
   NOT >= YEAR(GETDATE())-N which includes future data.
7. For last N months: WHERE DD.FullDate >= DATEADD(MONTH, -N, GETDATE()) AND DD.FullDate <= GETDATE().
8. CRITICAL — LAG/LEAD/ROW_NUMBER monthly sort: ORDER BY (Year * 100 + Month), never (Year, Month) separately.

--- TABLE RELATIONSHIP RULES ---
9. Customer returns: FactCustomerReturn (header) + FactCustomerReturnDetail (lines) via CustomerReturnNo.
10. Credit memos: FactCreditMemo (header) + FactCreditMemoDetail (lines) via CreditMemoNo.
11. Vendor invoices: FactVendorInvoices (header) + FactVendorInvoiceDetail (lines) via PayableInvoiceNo.
12. Vendor returns: FactVendorReturn (header) + FactVendorReturnDetail (lines) via VendorReturnNo.
13. Customer payment application: FactCustomerApplication + FactCustomerPayment via CashReceiptNo.
14. Back-order history: DimSalesOrderDetail_Log filtered on BackOrder column.
15. Customer debit analysis: FactCustomerDebit + DimCustomer via CustomerKey.
16. Purchase on-time analysis: join FactPurchaseOrder to DimDate twice (DueDateKey, CompletionDateKey) and compare.

--- SQL QUALITY RULES (CRITICAL) ---
17. NULL-SAFE EXCLUSIONS: NEVER use NOT IN with a subquery. Use LEFT JOIN ... WHERE key IS NULL instead.
18. ALWAYS COMPUTE WHAT IS ASKED: growth/trend/comparison → use LAG/LEAD window functions with both absolute and % change.
19. PRODUCT ANALYSIS: Exclude discontinued (IsDiscontinued=0), cross-check inventory, include revenue/profit context.
20. INVENTORY: FactInventorySnapshot has NO DateKey. Query directly.
    AvailableQty = QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0).
    Reorder = QuantityOnHand < DimWarehouse.BufferQty.
21. CURRENT STATE VS HISTORY: For "current" questions, use ROW_NUMBER() to isolate most recent per entity.
22. ORDER BY business impact (revenue, profit, amount), never alphabetically.
23. THRESHOLDS: Add minimum volume threshold for trend analysis.
24. RANKING: Include rank column in final SELECT for top-N queries.
25. PROFITABILITY: use FactSalesDetail.ProfitAmount.

================================================================
              FEW-SHOT EXAMPLE PATTERNS
================================================================

--- Example 1: Quarterly sales (correct metric: MerchandiseAmount, with status filter) ---
Question: "What is total sales of 2025 by quarter?"
SELECT DD.Quarter,
       SUM(FSI.MerchandiseAmount) AS SalesRevenue,
       SUM(FSI.TaxAmount) AS TaxCollected,
       SUM(FSI.DiscountAmount) AS DiscountsGiven,
       COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year = 2025
GROUP BY DD.Quarter
ORDER BY DD.Quarter

--- Example 2: Top customers by revenue (header table, no fan-out, with rank) ---
Question: "Top 10 customers by revenue"
SELECT TOP 10
    ROW_NUMBER() OVER (ORDER BY SUM(FSI.MerchandiseAmount) DESC) AS Rank,
    DC.CustomerID, DC.CustomerName,
    SUM(FSI.MerchandiseAmount) AS TotalRevenue,
    COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount
FROM FactSalesInvoice FSI
JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
GROUP BY DC.CustomerID, DC.CustomerName
ORDER BY TotalRevenue DESC

--- Example 3: Top products by quantity (net returns, detail table, with profit) ---
Question: "Top 10 products by quantity sold"
SELECT TOP 10
    ROW_NUMBER() OVER (ORDER BY SUM(FSD.Quantity - ISNULL(FSD.ReturnQuantity,0)) DESC) AS Rank,
    DP.ItemID, DP.ItemName, DP.Category,
    SUM(FSD.Quantity - ISNULL(FSD.ReturnQuantity,0)) AS NetQuantitySold,
    SUM(FSD.SalesAmount) AS TotalSalesAmount,
    SUM(FSD.ProfitAmount) AS TotalProfit
FROM FactSalesDetail FSD
JOIN DimProduct DP ON FSD.ProductKey = DP.ProductKey
WHERE DP.IsDiscontinued = 0
GROUP BY DP.ItemID, DP.ItemName, DP.Category
ORDER BY NetQuantitySold DESC

--- Example 4: Inventory stock on hand (NO DateKey — table has no date column) ---
Question: "Which products have the most stock on hand?"
SELECT TOP 10
    DP.ItemID, DP.ItemName, DP.Category,
    SUM(FIS.QuantityOnHand) AS TotalStockOnHand,
    SUM(FIS.InventoryValue) AS TotalInventoryValue
FROM FactInventorySnapshot FIS
JOIN DimProduct DP ON FIS.ProductKey = DP.ProductKey
WHERE DP.IsDiscontinued = 0
GROUP BY DP.ItemID, DP.ItemName, DP.Category
ORDER BY TotalStockOnHand DESC

--- Example 5: Purchase orders (exclude Void/Cancel) ---
Question: "Top vendors by purchase amount"
SELECT TOP 10
    ROW_NUMBER() OVER (ORDER BY SUM(FPO.TotalAmount) DESC) AS Rank,
    DV.VendorID, DV.VendorName,
    SUM(FPO.TotalAmount) AS TotalPurchaseAmount,
    COUNT(DISTINCT FPO.PurchaseOrderNo) AS POCount
FROM FactPurchaseOrder FPO
JOIN DimVendors DV ON FPO.VendorKey = DV.VendorKey
WHERE FPO.POStatus NOT IN ('Void', 'Cancel')
GROUP BY DV.VendorID, DV.VendorName
ORDER BY TotalPurchaseAmount DESC

--- Example 6: Vendor returns (correct table: FactVendorReturn) ---
Question: "Total vendor return amount by vendor"
SELECT TOP 10
    DV.VendorID, DV.VendorName,
    SUM(FVR.TotalAmount) AS TotalReturnAmount,
    COUNT(DISTINCT FVR.VendorReturnNo) AS ReturnCount
FROM FactVendorReturn FVR
JOIN DimVendors DV ON FVR.VendorKey = DV.VendorKey
GROUP BY DV.VendorID, DV.VendorName
ORDER BY TotalReturnAmount DESC

--- Example 7: Customer count (active only) ---
Question: "How many customers do we have?"
SELECT COUNT(*) AS ActiveCustomerCount
FROM DimCustomer
WHERE Status = 'Active'

--- Example 8: YoY revenue comparison (correct metric) ---
Question: "Year-over-year revenue comparison 2024 vs 2025"
SELECT DD.Year,
       SUM(FSI.MerchandiseAmount) AS Revenue,
       LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year) AS PrevYearRevenue,
       SUM(FSI.MerchandiseAmount) - LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year) AS YoY_Change,
       ROUND(100.0 * (SUM(FSI.MerchandiseAmount) - LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year))
             / NULLIF(LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year), 0), 2) AS YoY_Pct
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year BETWEEN 2024 AND 2025
GROUP BY DD.Year
ORDER BY DD.Year

--- Example 9: Business summary (NO fan-out — use header table ONLY) ---
Question: "Summary: total revenue, profit, customer count, invoice count for 2025"
SELECT
    SUM(FSI.MerchandiseAmount) AS TotalRevenue,
    SUM(FSI.TaxAmount) AS TotalTax,
    SUM(FSI.DiscountAmount) AS TotalDiscount,
    COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount,
    COUNT(DISTINCT FSI.CustomerKey) AS UniqueCustomers
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year = 2025
-- NOTE: For profit, query FactSalesDetail separately (do NOT join with FactSalesInvoice)

--- Example 10: Dead stock (no DateKey on FactInventorySnapshot) ---
Question: "Products with no sales in 90 days that still have stock"
WITH RecentSales AS (
    SELECT DISTINCT FSD.ProductKey
    FROM FactSalesDetail FSD
    JOIN DimDate DD ON FSD.DateKey = DD.DateKey
    WHERE DD.FullDate >= DATEADD(DAY, -90, GETDATE())
)
SELECT
    DP.ItemID,
    DP.ItemName,
    DP.Category,
    DP.Brand,
    SUM(FIS.QuantityOnHand)   AS TotalQtyOnHand,
    SUM(FIS.InventoryValue)   AS TotalInventoryValue,
    AVG(FIS.AverageCost)      AS AvgCost,
    COUNT(DISTINCT FIS.BranchKey) AS WarehouseCount
FROM FactInventorySnapshot FIS
JOIN DimProduct DP  ON FIS.ProductKey = DP.ProductKey
LEFT JOIN RecentSales RS ON FIS.ProductKey = RS.ProductKey
WHERE RS.ProductKey IS NULL
  AND FIS.QuantityOnHand > 0
  AND DP.IsDiscontinued = 0
  AND DP.Status = 'Active'
GROUP BY DP.ItemID, DP.ItemName, DP.Category, DP.Brand
ORDER BY TotalInventoryValue DESC

--- Example 11: Vendor payments (correct table name with 's', exclude voided) ---
Question: "Total amount paid to vendors this year"
SELECT SUM(FVP.Amount) AS TotalPaidToVendors
FROM FactVendorPayments FVP
JOIN DimDate DD ON FVP.PaymentDateKey = DD.DateKey
WHERE DD.Year = YEAR(GETDATE())
  AND FVP.VoidDateKey IS NULL

--- Example 12: Last 3 years sales (correct BETWEEN to exclude future) ---
Question: "Total sales by year for last 3 years"
SELECT DD.Year,
       SUM(FSI.MerchandiseAmount) AS SalesRevenue,
       COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year BETWEEN YEAR(GETDATE())-3 AND YEAR(GETDATE())
GROUP BY DD.Year
ORDER BY DD.Year
"""


def get_system_prompt() -> str:
    """Full DB context for LangChain SQL agent (injected as prefix)."""
    view_ddls = "\n\n".join([
        "-- VW_SalesByWarehouse (use if view exists, else query FactSalesDetail + DimWarehouse + DimDate)\n"
        + VIEW_SALES_BY_WAREHOUSE.strip(),
        "-- VW_SalesMonthly (use if view exists, else query FactSalesInvoice + DimDate)\n"
        + VIEW_SALES_MONTHLY.strip(),
        "-- VW_CustomerCreditYearly (use if view exists, else query FactCreditMemo + DimCustomer + DimDate)\n"
        + VIEW_CUSTOMER_CREDIT_YEARLY.strip(),
        "-- VW_CustomerPayment (use if view exists, else query FactCustomerPayment + DimCustomer)\n"
        + VIEW_CUSTOMER_PAYMENT.strip(),
        "-- VW_VendorReturnQtyMonthly (use if view exists, else query FactVendorInvoiceDetail + DimVendors + DimDate)\n"
        + VIEW_VENDOR_RETURN_QTY_MONTHLY.strip(),
    ])
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
