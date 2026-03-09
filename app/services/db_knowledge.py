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
  SalesType            (Sales classification: 'S' = Sales, 'C'/'M' = Credit, 'D' = Debit)
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
  SalesType            (Sale item classification)
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

FactInventorySnapshot  — Point-in-time inventory position per product per warehouse.
  InventorySnapshotKey (Surrogate key, PK)
  DateKey              (FK → DimDate — snapshot date)
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
  NOTE: For current inventory, use snapshot with the latest DateKey.
        AvailableQty = QuantityOnHand - PickingQuantity - SalesOrderQuantity.
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

--- GENERAL RULES ---
1. Always use base tables (joining with DimDate and dimension tables) if the views are not available.
2. Generate only a single SELECT (or WITH ... SELECT) statement per query.
   Do NOT use DECLARE or T-SQL variables; use inline expressions such as YEAR(GETDATE()), DATEADD(), DATEPART().
3. Never use schema-qualified names like dbo.TableName unless needed; just use the table/view name directly.
4. FactSalesInvoice.SalesType filter: 'S' = Sales, 'C'/'M' = Credit, 'D' = Debit.
5. FactPurchaseOrder.POStatus values: Open, Closed, Partially Shipped, Void, New, Cancel.

--- TIME / DATE RULES ---
6. For time-based filtering: JOIN to DimDate on DateKey and filter on Year, Month, Quarter, MonthName.
7. For current period: use YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
8. For last N months: DimDate.DateKey IN (SELECT DateKey FROM DimDate WHERE FullDate >= DATEADD(MONTH, -N, GETDATE())).
9. For fiscal year comparisons, use DimDate.Year directly.
10. CRITICAL — When using LAG(), LEAD(), or ROW_NUMBER() to compare monthly data across years,
    ALWAYS sort by (Year * 100 + Month) instead of (Year, Month) to guarantee correct cross-year ordering.
    Example: ORDER BY Year * 100 + Month   — this makes Dec-2023 (202312) correctly sort before Jan-2024 (202401).

--- TABLE RELATIONSHIP RULES ---
11. For customer returns: FactCustomerReturn (header) + FactCustomerReturnDetail (lines) via CustomerReturnNo.
12. For credit memos: FactCreditMemo (header) + FactCreditMemoDetail (lines) via CreditMemoNo.
13. For vendor invoices: FactVendorInvoices (header) + FactVendorInvoiceDetail (lines) via PayableInvoiceNo.
14. For vendor returns: FactVendorReturn (header) + FactVendorReturnDetail (lines) via VendorReturnNo.
15. For customer payment application: FactCustomerApplication + FactCustomerPayment via CashReceiptNo.
16. For back-order history: DimSalesOrderDetail_Log filtered on BackOrder column.
17. For customer debit analysis: FactCustomerDebit + DimCustomer via CustomerKey.
18. For purchase on-time analysis: join FactPurchaseOrder to DimDate twice (DueDateKey, CompletionDateKey) and compare.

--- SQL QUALITY RULES (CRITICAL — follow strictly) ---

19. NULL-SAFE EXCLUSIONS: NEVER use NOT IN with a subquery. It silently returns zero rows if ANY NULL exists
    in the subquery result. Always use LEFT JOIN ... WHERE key IS NULL instead.
    BAD:  WHERE dp.ProductKey NOT IN (SELECT ProductKey FROM ...)
    GOOD: LEFT JOIN (...) rs ON dp.ProductKey = rs.ProductKey WHERE rs.ProductKey IS NULL

20. ALWAYS COMPUTE WHAT IS ASKED: When the user asks for "growth", "trend", "change", or "comparison",
    you MUST compute the actual metric using window functions (LAG, LEAD, or self-join), not just show raw numbers.
    If they ask for YoY growth → use LAG() partitioned by entity and ordered by Year.
    If they ask for MoM growth → use LAG() partitioned by entity and ordered by Year * 100 + Month.
    Always include both the absolute change AND the percentage change.

21. PRODUCT ANALYSIS: When analyzing products (dead stock, slow movers, declining items, best-sellers):
    - Exclude discontinued products: WHERE dp.IsDiscontinued = 0
    - For dead stock or slow movers, cross-reference FactInventorySnapshot to confirm the product has stock on hand
      (a product with zero sales AND zero inventory is just out of stock, not dead stock).
    - Include revenue/profit context alongside quantity: always include SalesAmount or ProfitAmount from FactSalesDetail.

22. INVENTORY QUERIES: For current inventory, use the snapshot with the latest DateKey:
      WHERE FIS.DateKey = (SELECT MAX(DateKey) FROM FactInventorySnapshot)
    AvailableQty = QuantityOnHand - PickingQuantity - SalesOrderQuantity.
    Reorder needed when QuantityOnHand < DimWarehouse.BufferQty.

23. CURRENT STATE VS HISTORY: When asked about "current" declining items, dead stock, or overdue invoices,
    filter to the most recent occurrence per entity (use ROW_NUMBER() partitioned by entity ORDER BY date DESC,
    then WHERE RowNum = 1). Do NOT return all historical occurrences.

24. ORDER BY BUSINESS IMPACT: Always sort final results by business impact (revenue, profit, total amount,
    quantity value, severity of decline), not alphabetically by name. Alphabetical sorting has no business value.

25. THRESHOLDS: For trend or decline analysis, add a minimum volume threshold so trivially small numbers
    (e.g. going from 2 units to 1 unit) do not dominate results. Use a reasonable floor like > 10 units
    or a percentage of the overall average.

26. PROFITABILITY: use FactSalesDetail.ProfitAmount or (SalesAmount - UnitCost * Quantity).

27. RANKING VISIBILITY: When computing RANK() or ROW_NUMBER() for "top N" queries, always include
    the rank column in the final SELECT so the user can verify the ordering.

================================================================
              FEW-SHOT EXAMPLE PATTERNS
================================================================

--- Example 1: YoY growth with LAG (correct cross-year ordering) ---
Question: "Show yearly revenue per customer with year-over-year growth"
WITH CustomerYearly AS (
    SELECT DC.CustomerID, DC.CustomerName, DD.Year,
           SUM(FSD.SalesAmount) AS Revenue
    FROM FactSalesDetail FSD
    JOIN DimCustomer DC ON FSD.CustomerKey = DC.CustomerKey
    JOIN DimDate DD ON FSD.DateKey = DD.DateKey
    GROUP BY DC.CustomerID, DC.CustomerName, DD.Year
)
SELECT CustomerID, CustomerName, Year, Revenue,
       LAG(Revenue) OVER (PARTITION BY CustomerID ORDER BY Year) AS PrevYearRevenue,
       Revenue - LAG(Revenue) OVER (PARTITION BY CustomerID ORDER BY Year) AS YoY_Change,
       ROUND(100.0 * (Revenue - LAG(Revenue) OVER (PARTITION BY CustomerID ORDER BY Year))
             / NULLIF(LAG(Revenue) OVER (PARTITION BY CustomerID ORDER BY Year), 0), 2) AS YoY_Pct
FROM CustomerYearly
ORDER BY CustomerID, Year

--- Example 2: Dead stock — NULL-safe exclusion + inventory cross-check ---
Question: "Products with no sales in 90 days that still have stock"
WITH RecentSales AS (
    SELECT DISTINCT FSD.ProductKey
    FROM FactSalesDetail FSD
    JOIN DimDate DD ON FSD.DateKey = DD.DateKey
    WHERE DD.FullDate >= DATEADD(DAY, -90, GETDATE())
),
CurrentInventory AS (
    SELECT ProductKey, SUM(QuantityOnHand) AS QtyOnHand, SUM(InventoryValue) AS InvValue
    FROM FactInventorySnapshot
    WHERE DateKey = (SELECT MAX(DateKey) FROM FactInventorySnapshot)
    GROUP BY ProductKey
)
SELECT DP.ItemID, DP.ItemName, DP.Category,
       CI.QtyOnHand, CI.InvValue
FROM DimProduct DP
LEFT JOIN RecentSales RS ON DP.ProductKey = RS.ProductKey
JOIN CurrentInventory CI ON DP.ProductKey = CI.ProductKey
WHERE RS.ProductKey IS NULL
  AND CI.QtyOnHand > 0
  AND DP.IsDiscontinued = 0
ORDER BY CI.InvValue DESC

--- Example 3: MoM decline detection — correct period sort + most recent only ---
Question: "Products declining for 3+ consecutive months"
WITH MonthlySales AS (
    SELECT FSD.ProductKey, DD.Year, DD.Month, DD.MonthName,
           DD.Year * 100 + DD.Month AS YearMonth,
           SUM(FSD.Quantity) AS Qty, SUM(FSD.SalesAmount) AS Revenue
    FROM FactSalesDetail FSD
    JOIN DimDate DD ON FSD.DateKey = DD.DateKey
    GROUP BY FSD.ProductKey, DD.Year, DD.Month, DD.MonthName
),
WithLag AS (
    SELECT *, LAG(Qty, 1) OVER (PARTITION BY ProductKey ORDER BY YearMonth) AS Lag1,
              LAG(Qty, 2) OVER (PARTITION BY ProductKey ORDER BY YearMonth) AS Lag2,
              LAG(Qty, 3) OVER (PARTITION BY ProductKey ORDER BY YearMonth) AS Lag3,
              ROW_NUMBER() OVER (PARTITION BY ProductKey ORDER BY YearMonth DESC) AS RN
    FROM MonthlySales
)
SELECT DP.ItemID, DP.ItemName, DP.Category,
       WL.Year, WL.MonthName, WL.Qty AS CurrentQty,
       WL.Lag1 AS Prev1, WL.Lag2 AS Prev2, WL.Lag3 AS Prev3,
       WL.Lag3 - WL.Qty AS TotalDrop, WL.Revenue
FROM WithLag WL
JOIN DimProduct DP ON WL.ProductKey = DP.ProductKey
WHERE WL.Qty < WL.Lag1 AND WL.Lag1 < WL.Lag2 AND WL.Lag2 < WL.Lag3
  AND WL.Lag3 > 10
  AND WL.RN = 1
  AND DP.IsDiscontinued = 0
ORDER BY WL.Lag3 - WL.Qty DESC

--- Example 4: Top N with rank visible + growth computed ---
Question: "Top 10 vendors by purchase volume with YoY comparison"
WITH VendorYearly AS (
    SELECT DV.VendorID, DV.VendorName, DD.Year,
           SUM(FPO.TotalAmount) AS PurchaseTotal
    FROM FactPurchaseOrder FPO
    JOIN DimVendors DV ON FPO.VendorKey = DV.VendorKey
    JOIN DimDate DD ON FPO.DateKey = DD.DateKey
    WHERE FPO.POStatus NOT IN ('Void', 'Cancel')
    GROUP BY DV.VendorID, DV.VendorName, DD.Year
),
Ranked AS (
    SELECT VendorID, VendorName, SUM(PurchaseTotal) AS AllTimeTotal,
           RANK() OVER (ORDER BY SUM(PurchaseTotal) DESC) AS VendorRank
    FROM VendorYearly GROUP BY VendorID, VendorName
)
SELECT R.VendorRank, VY.VendorID, VY.VendorName, VY.Year,
       VY.PurchaseTotal, R.AllTimeTotal,
       VY.PurchaseTotal - LAG(VY.PurchaseTotal) OVER (PARTITION BY VY.VendorID ORDER BY VY.Year) AS YoY_Change
FROM VendorYearly VY
JOIN Ranked R ON VY.VendorID = R.VendorID
WHERE R.VendorRank <= 10
ORDER BY R.VendorRank, VY.Year

--- Example 5: Outstanding vendor invoices sorted by financial exposure ---
Question: "Vendor invoices that are still unpaid"
SELECT DV.VendorName, FVI.PayableInvoiceNo,
       FVI.TotalAmount, FVI.PaidAmount,
       (FVI.TotalAmount - FVI.PaidAmount) AS Outstanding, FVI.Status
FROM FactVendorInvoices FVI
JOIN DimVendors DV ON FVI.VendorKey = DV.VendorKey
WHERE FVI.Status NOT IN ('Paid', 'Void')
  AND (FVI.TotalAmount - FVI.PaidAmount) > 0
ORDER BY Outstanding DESC

--- Example 6: Customer payment overview with pending amounts ---
Question: "Which customers have the largest pending payment balances?"
SELECT DC.CustomerID, DC.CustomerName,
       SUM(FCP.Amount) AS TotalReceived,
       SUM(FCP.AppliedAmount) AS Applied,
       SUM(FCP.Amount - FCP.AppliedAmount) AS Pending
FROM FactCustomerPayment FCP
JOIN DimCustomer DC ON FCP.CustomerKey = DC.CustomerKey
GROUP BY DC.CustomerID, DC.CustomerName
HAVING SUM(FCP.Amount - FCP.AppliedAmount) > 0
ORDER BY Pending DESC
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
