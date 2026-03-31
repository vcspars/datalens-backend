"""
Shared database knowledge for LangChain and Vanna agents.
Source: "Star Schema Documentation for Data Lens" — VISIONARY COMPUTER SOLUTIONS (PVT) LTD
         Prepared by Zahid Iqbal & Muhammad Numan, 3/10/2026
Database: StarScemaSPARS
Schema: dbo

All 30 tables (10 Dimension + 20 Fact) and 7 analytics views/references are documented below.
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
# Full schema documentation — ALL 30 tables + 7 views/references
# ---------------------------------------------------------------------------

BUSINESS_DOCUMENTATION = """
You are a senior SQL Server expert specializing in ERP Data Warehouse analytics using a Star Schema.
Your task is to convert natural language questions into accurate, optimized, and production-safe SQL queries.
Return ONLY SQL query. No explanation.
**note: Never generate complex and long SQL queries. Always keep it simple and optimized.
=== STAR SCHEMA: StarScemaSPARS ===
Designed for: Sales Analysis, Purchase Analysis, Inventory Monitoring, Profitability Reporting,
Customer & Vendor Analytics, Customer Returns & Payments, Vendor Returns & Payments,
Back Order Information, Consignments, Sales Rep Commissions.

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

DimVendors  — Vendor master data for procurement analytics.
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

DimInvoiceAddresses  — Shipping destination reference.
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


================================================================
                      FACT TABLES (21)
================================================================

FactSalesInvoice  — Invoice header metrics.
  (No column list defined in schema.md — purpose: invoice header level metrics)

FactSalesDetail  — Invoice line-level sales details.
  SalesKey             (Surrogate key)
  SalesInvoiceNo       (Sales invoice number)
  InvoiceLineNumber    (Sale item line number)
  DateKey              (FK → DimDate — invoice date)
  OrderDateKey         (FK → DimDate — order date)
  ProductKey           (FK → DimProduct)
  CustomerKey          (FK → DimCustomer)
  BranchKey            (FK → DimWarehouse)
  ItemType             (Item type — e.g. Prog, OAK)
  Quantity             (Sale item quantity sold)
  UnitPrice            (Sale item unit price — price charged per unit)
  UnitCost             (Sale item cost per unit at time of sale)
  DiscountAmount       (Sale item discount subtracted from specific line)
  SalesAmount          (Sale item net sales amount)
  TaxAmount            (Tax allocated to this line)
  ShippingCharges      (Sale item shipping fees allocated to this line)
  ProfitAmount         (Sale item net profit amount)

FactConsignments  — Consignment header metrics.
  ConsignmentKey       (Surrogate key)
  ConsignmentNo        (Consignment number)
  DateKey              (FK → DimDate — consignment date)
  OrderDateKey         (FK → DimDate — order date)
  CustomerKey          (FK → DimCustomer)
  AddressesKey         (FK → DimInvoiceAddresses — shipping destination)
  BranchKey            (FK → DimWarehouse — fulfillment branch)
  PaymentTermKey       (FK → DimPaymentTerms)
  SalesType            (Sales classification)
  InvoiceType          (Document type)
  Status               (Invoice status)
  TotalQuantity        (Total quantity)
  TotalAmount          (Total invoice amount)
  TaxAmount            (Tax total)
  ShippingCharges      (Shipping fees)
  HandlingCharges      (Handling fees)
  ServiceCharges       (Service fees)
  MerchandiseAmount    (Merchandise value)
  ServicesAmount       (Service revenue)
  AppliedAmount        (Applied payments)
  DiscountAmount       (Discounts)
  TotalWeight          (Total shipment weight)

FactConsignmentDetail  — Consignment line-level sales details.
  SalesKey             (Surrogate key)
  ConsignmentNo        (Consignment number)
  LineNumber           (Item line number)
  DateKey              (FK → DimDate — consignment date reference)
  OrderDateKey         (FK → DimDate — order date reference)
  ProductKey           (FK → DimProduct)
  CustomerKey          (FK → DimCustomer)
  BranchKey            (FK → DimWarehouse)
  ItemType             (Item type — e.g. Prog, OAK)
  Quantity             (Quantity sold)
  UnitPrice            (Price charged per unit)
  UnitCost             (Cost per unit at time of sale)
  DiscountAmount       (Discount subtracted from specific line)
  SalesAmount          (Net sales amount)
  TaxAmount            (Tax allocated to this line)
  ShippingCharges      (Shipping fees allocated to this line)
  ProfitAmount         (Net profit amount)

FactPurchaseOrder  — Purchase order header metrics.
  PurchaseOrderKey     (Surrogate key)
  PurchaseOrderNo      (Purchase order number)
  VendorKey            (FK → DimVendors)
  DateKey              (FK → DimDate — issue date)
  DueDateKey           (FK → DimDate — expected receipt date)
  CancelDateKey        (FK → DimDate — cancellation date)
  CompletionDateKey    (FK → DimDate — completion date)
  WarehouseKey         (FK → DimWarehouse — receiving warehouse)
  CustomerKey          (FK → DimCustomer — special order for this customer)
  TotalQty             (Purchase order total items quantity)
  TotalAmount          (Purchase order grand total amount)
  TotalTax             (Purchase order total tax)
  InTransitQty         (Quantity currently shipping from vendor)
  ReceivedQty          (Received quantity)
  DropShipment         (Flag for direct-to-customer shipments: 1=Yes, 0=No)


FactPurchaseDetail  — Purchase order line-level details.
  PurchaseLineKey      (Surrogate key)
  PurchaseOrderNo      (Purchase order number)
  Line_No              (Purchase item line number)
  VendorKey            (FK → DimVendors)
  ProductKey           (FK → DimProduct)
  DateKey              (FK → DimDate — issue date)
  DueDateKey           (FK → DimDate — expected receipt date)
  WarehouseKey         (FK → DimWarehouse — destination warehouse)
  CustomerKey          (FK → DimCustomer — special order for this customer)
  OrderQty             (Purchase item quantity requested from vendor)
  UnitCost             (Purchase item cost per unit)
  LineAmount           (Purchase item total line cost amount)
  TaxAmount            (Purchase item line tax amount)
  DiscountPercent      (Purchase item discount percent for specific line item)
  InTransitQty         (Purchase item quantity currently mid-shipment)
  ReceivedQty          (Purchase item received quantity)
  SQFTCost             (Purchase item cost per square foot)

FactInventorySnapshot  — Inventory position snapshots.
  InventorySnapshotKey (Surrogate key)
  ProductKey           (FK → DimProduct)
  BranchKey            (FK → DimWarehouse)
  QuantityOnHand       (Inventory available quantity)
  InventoryValue       (Inventory value)
  PickingQuantity      (Inventory allocated for picking)
  SalesOrderQuantity   (Inventory reserved for sales orders)
  DamagedQuantity      (Inventory damaged stock)
  ShowRoomQuantity     (Inventory display stock)
  MissingBinQuantity   (Inventory missing stock)
  AverageCost          (Inventory average cost)


FactVendorInvoices  — Vendor position invoices.
  PayableInvoiceNo     (Primary key — payable invoice number)
  VendorKey            (FK → DimVendors)
  InvoiceType          (Code classifying the invoice type)
  PaymentTermKey       (FK → DimPaymentTerms)
  Status               (Current invoice status)
  VendorInvoiceRef     (Vendor's reference/invoice number)
  VendorInvoiceDateKey (FK → DimDate)
  DueDateKey           (FK → DimDate)
  TotalAmount          (Total invoice amount)
  PaidAmount           (Amount already paid to the vendor)
  WarehouseKey         (FK → DimWarehouse)
  PeriodID             (Period identifier)

FactVendorPayment  — Vendor position payments.
  PaymentNo            (Primary key — payment number)
  VendorKey            (FK → DimVendors)
  DocDateKey           (FK → DimDate — document date)
  PaymentDateKey       (FK → DimDate — payment date)
  PaymentAccount       (Bank or cash account debited for payment)
  DiscountAccount      (Account where discount taken is recorded)
  DocType              (Payment mode — Wire Transfer, IDC)
  Amount               (Total payment amount sent to vendor)
  AppliedAmount        (Amount applied to outstanding invoices)
  AppliedDiscount      (Discount amount deducted from payment)
  Status               (Payment status)
  PaymentType          (Method of payment)
  PeriodID             (Accounting period identifier)
  VoidDateKey          (FK → DimDate — void date if payment was voided)

FactCustomerReturn  — Customer position returns.
  ReturnHeaderKey      (Surrogate key)
  CustomerReturnNo     (Unique business identifier for the return)
  SalesInvoiceNo       (Sales invoice number for which this credit is issued)
  CreditMemoNo         (Credit memo issued for this return)
  CustomerKey          (FK → DimCustomer)
  DateReceivedKey      (FK → DimDate — date return was received)
  CreditDateKey        (FK → DimDate — date credit was issued)
  InvoiceDateKey       (FK → DimDate — date of the original sales invoice)
  Status               (Return status)
  ReceivingBin         (Warehouse bin where returned items are stored)
  TotalQty             (Total quantity of items returned)
  TotalAmount          (Total value/credit amount for the return)
  ShippingHandlingAmount  (Return shipping and handling charges)
  TotalBales           (For rugs/large items: number of bales/packages in return)

FactCustomerReturnDetail  — Customer position returns detail.
  ReturnKey            (Surrogate key)
  CustomerReturnNo     (Unique business identifier for the return)
  SalesInvoiceNo       (Reference sales invoice number of the return)
  CustomerKey          (FK → DimCustomer)
  DateReceivedKey      (FK → DimDate)
  ProductKey           (FK → DimProduct)
  ReturnReason         (Reason for return)
  ReturnQty            (Quantity returned)
  Cost                 (Product cost)
  Price                (Selling price)
  Discount             (Discount that was applied)
  ExtPrice             (Extended price — credit amount for this line)
  TaxAmount            (Tax on the credit)
  SQFTPrice            (Cost/price per square foot — for rugs)

FactCreditMemo  — Credit memo headers.
  CreditMemoKey        (Surrogate key)
  CreditMemoNo         (Business identifier for the credit memo)
  CustomerKey          (FK → DimCustomer)
  SalesInvoiceNo       (Sales invoice number)
  CustomerReturnNo     (Related customer return number)
  BranchKey            (FK → DimWarehouse)
  CreditDateKey        (FK → DimDate — date credit was issued)
  InvoiceDateKey       (FK → DimDate — original invoice date)
  OrderDateKey         (FK → DimDate — original order date)
  ShippedDateKey       (FK → DimDate — shipped date)
  TotalQty             (Total quantity of items on the credit memo)
  TotalQtyInvoiced     (Total quantity that was originally invoiced)
  TotalMerchandise     (Value of merchandise only — excluding services)
  TotalServices        (Value of services — if any)
  TotalAmount          (Total credit memo amount before adjustments)
  TaxAmount            (Tax amount on the credit)
  ShippingCharges      (Return shipping charges)
  HandlingCharges      (Handling charges)
  ServiceCharges       (Service charges — if applicable)
  DiscountAmount       (Discount applied to the credit)
  AppliedAmount        (Amount of credit already applied to invoices)
  Status               (Credit status)
  PriceCategoryKey     (FK → DimPriceCategory — pricing tier applied)
  PaymentTermKey       (FK → DimPaymentTerms)

FactCreditMemoDetail  — Credit memo line-level details.
  SalesKey             (Credit detail key)
  CreditMemoNo         (Business identifier for the credit memo)
  InvoiceLineNumber    (Line number)
  SalesInvoiceNo       (Sales invoice number)
  BranchKey            (FK → DimWarehouse)
  InvoiceDateKey       (FK → DimDate)
  OrderDateKey         (FK → DimDate)
  ProductKey           (FK → DimProduct)
  CustomerKey          (FK → DimCustomer)
  SalesType            (Type of sales)
  ItemType             (Item category)
  Quantity             (Quantity credited)
  UnitPrice            (Original unit price)
  UnitCost             (Original unit cost)
  DiscountAmount       (Discount applied on this line)
  SalesAmount          (Extended credit amount after discount)
  TaxAmount            (Tax on the credit line)
  ShippingCharges      (Shipping charges allocated to this line)

FactCustomerPayment  — Customer payments (incoming cash receipts).
  CashReceiptNo        (Unique identifier for the cash receipt)
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
  PeriodID             (Accounting period identifier)

FactCustomerApplication  — A single customer payment often applies to multiple invoices.
  CRBatchApplicationNo (Batch application number)
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
  Write Off            (Flag indicating if any amount was written off)
  PeriodID             (Accounting period identifier)

FactVendorInvoiceDetail  — Each vendor invoice header contains multiple line items (products received). FactVendorInvoiceDetail captures every invoice line: which product, quantity received
  VendorInvoiceDetailKey  (Surrogate key)
  PayableInvoiceNo     (FK → FactVendorInvoices)
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

FactCustomerDebit  — Summary level data for customer credit memos and debit adjustments.
  CreditMemoKey        (Surrogate key — IDENTITY)
  CustomerDebitNo      (Business key — actual credit memo number from ERP)
  CustomerKey          (FK → DimCustomer)
  InvoiceNo            (Reference to the original sales invoice, if applicable)
  BranchKey            (FK → DimWarehouse — which location issued the credit)
  CreditDateKey        (FK → DimDate — date the credit was issued)
  InvoiceDateKey       (FK → DimDate — date of the original invoice)
  OrderDateKey         (FK → DimDate — original order date)
  ADDDateKey           (FK → DimDate — system entry date)
  TotalServices        (Value of services being credited)
  TotalAmount          (Final total amount of the debit/credit)
  TaxAmount            (Amount of tax being reversed or adjusted)
  ShippingCharges      (Shipping costs included in the credit)
  HandlingCharges      (Handling fees included in the credit)
  ServiceCharges       (Fees for services associated with this debit)
  SalesDiscount        (Any additional sales discounts applied)
  PaymentDiscountAmount  (Cash/payment discounts reversed or applied)
  OpenCredit           (Remaining balance of the credit yet to be used)
  AppliedAmount        (Portion of the credit already applied to other invoices)
  CreditApplied        (Flag 0/1 indicating if credit is fully applied)
  Status               (Current state: Open, Applied, Void, Pending)
  InvoiceType          (Internal code for the document type)
  SalesType            (Classification of the sale: 'RET' = Retail, 'WHL' = Wholesale)

FactVendorReturn  — Summary level data for customer credit memos and debit adjustments.
  VendorReturnKey      (Surrogate key)
  VendorReturnNo       (Unique vendor return number)
  VendorKey            (FK → DimVendors)
  PaymentTermKey       (FK → DimPaymentTerms)
  InvoiceType          (Type of return)
  Status               (Return status)
  VendorInvoiceRef     (Vendor's invoice or reference number)
  PurchaseReceiptNo    (Associated purchase receipt number)
  VendorReturnDateKey  (FK → DimDate — return date)
  WarehouseKey         (FK → DimWarehouse)
  TotalAmount          (Total value of goods being returned)
  PaidAmount           (Amount already paid or credited by the vendor)
  DiscountAvailed      (Discount amount actually taken/applied)
  PeriodID             (Accounting period identifier)

FactVendorReturnDetail  — Vendor return line-level details.
  VendorReturnDetailKey  (Surrogate key)
  VendorReturnNo       (Return number)
  Line_No              (Line sequence number)
  VendorKey            (FK → DimVendors)
  ProductKey           (FK → DimProduct)
  DateKey              (FK → DimDate)
  BaleNumber           (Bale or package identifier)
  Description          (Item description)
  ItemType             (Item classification)
  VendorStyle          (Vendor's style code for the item)
  ReturnQty            (Quantity returned to vendor)
  Cost                 (Unit cost from vendor)
  ExtCost              (Extended cost = Cost × ReturnQty)
  TaxRate              (Tax rate applied to this line)
  ExtTax               (Extended tax amount)
  SKU                  (Stock ID)
  PONo                 (Purchase order number)
  ReceiveBin           (Receive bin)
  LotNo                (Lot number)

DimSalesRep  — Sales Rep master data for procurement analytics. (Summary level data for Sales Rep Commissions)
  SalesRepKey        (Surrogate key)
  SalesRepID         (Business vendor identifier)
  SalesRepName       (Full company name of the supplier)
  VendorType         (Sales Rep type: Sales Rep, Internal Sales Rep, Marketing Company)
  Category           (Business category)
  Class              (Priority or quality class)
  Region             (Geographic region)
  Status             (Current relationship status: Active, Hold, etc.)
  City               (Sales Rep city)
  State              (Sales Rep state)
  Country            (Sales Rep country)
  PaymentTerm        (Payment terms)
  PaymentPriority    (Settlement priority)
  TaxRate            (Tax percentage applied to Sales Rep invoices)
  CreditLimit        (Sales Rep credit limit)
  DesignerRate       (Special percentage rate for designers)


FactCommissionInvoice  — Sales Rep commission invoices.
  CommissionInvoiceNo  (Primary key — commission invoice number)
  SalesRepKey          (FK → DimSalesRep)
  PaymentTermKey       (FK → DimPaymentTerms)
  Status               (Current invoice status)
  CommissionInvoiceRef (Sales Rep's reference/invoice number)
  CommissionInvoiceDateKey (FK → DimDate)
  DueDateKey           (FK → DimDate)
  TotalAmount          (Total invoice amount)
  PaidAmount           (Amount already paid to the Sales Rep)
  WarehouseKey         (FK → DimWarehouse)
  PeriodID             (Accounting period identifier)

================================================================
                     ANALYTICS VIEWS (5) + REFERENCE QUERIES (2)
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

BackOrderHistory  — Back-order lookup (reference query pattern).
  Usage: SELECT * FROM DimSalesOrderDetail_Log WHERE SalesOrderNo = '<order_no>'
  Use this for back-order history and analysis.

CommissionInvoice  — Commission invoice lookup (reference query pattern).
  Usage: SELECT * FROM FactCommissionInvoice WHERE CommissionInvoiceNo = <invoice_no>
  Use this for sales rep commission invoice lookups.

================================================================
          QUERY GUIDELINES  (EXECUTIVE ROLE)
================================================================
This user has the EXECUTIVE / MANAGEMENT role.
Allowed scope:Full access: profitability reporting, margins, financial analytics, vendor & customer analytics, and all modules.

================================================================
  METRIC DEFINITIONS (CRITICAL)
================================================================
These are critical to always use the correct column when writing queries.
•	"Sales" / "Revenue" = FactSalesInvoice.MerchandiseAmount (pure merchandise value — excludes tax, shipping, handling).
•	NEVER use TotalAmount for "sales" or "revenue" — TotalAmount = MerchandiseAmount + TaxAmount + ShippingCharges + HandlingCharges + ServiceCharges.
•	Only use TotalAmount when the user explicitly asks for "total invoice amount" or "total amount including everything".
•	"Profit" = FactSalesDetail.ProfitAmount (already computed: SalesAmount − UnitCost × Quantity).
•	"Net Quantity Sold" = SUM(FactSalesDetail.Quantity - ISNULL(FactCreditMemoDetail.Quantity, 0)) from FactSalesDetail and FactCreditMemoDetail tables.
•	"Net Line Revenue" = FactSalesDetail.SalesAmount (already net at line level — use for product-level detail).
•	"Invoice Count" = COUNT(*) from FactSalesInvoice — but filter out void/cancelled.
•	"Customer Count" / "Vendor Count" = COUNT with Status filter (see DEFAULT FILTERS below).
•	For monthly/quarterly/yearly aggregated sales:
•	PREFERRED: Use VW_SalesMonthly view (has both TotalSalesAmount and MerchandiseRevenue columns).
•	Use MerchandiseRevenue from VW_SalesMonthly for "sales" questions.


================================================================
  DEFAULT FILTERS (MANDATORY)
================================================================
Always apply default filters unless user says otherwise.
•	FactSalesInvoice: Do NOT include void/cancelled invoices in totals.
•	Add: WHERE FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed') — or similar exclusion.
•	Only count/sum active invoices.
•	Only include Void/Cancel when user asks "by status" breakdowns.
•	DimCustomer: WHERE DC.Status = 'Active' for customer COUNTS and "how many customers" questions.
•	For revenue analysis, include all customers (they may be inactive now but had past revenue).
•	DimWarehouse: WHERE DW.IsActive = 1 when listing/counting active warehouses.
•	For historical sales analysis, include all warehouses.
•	DimProduct: WHERE DP.IsDiscontinued = 0 for product analysis (unless user asks about discontinued).
•	NOTE: DimProduct.Status values in this database are not reliably populated.
•	Do NOT filter on DP.Status = 'Active' — this returns 0 rows. Use IsDiscontinued = 0 only.
•	FactVendorPayments: WHERE FVP.VoidDateKey IS NULL to exclude voided payments.
•	SalesType: Actual values are 'SO0' (Sales) and 'CS0' (Sales from Consignment).
•	Do NOT filter on SalesType by default. Only filter when user explicitly asks to separate types.
•	NULL grouping columns: When GROUP BY a nullable column (Region, Category, etc.),
•	add WHERE column IS NOT NULL to avoid NULL group unless user wants to see NULLs.
•	There must be at least one record, or the amount must be greater than zero, when the user requests ‘bottom’, ‘lower’, or ‘minimum’.


================================================================
  ANTI-PATTERNS (STRICTLY FORBIDDEN)
================================================================
Never do list these produce wrong results

AP1: 
o	NEVER JOIN FactSalesInvoice WITH FactSalesDetail in the same aggregation query.
o	Each invoice has multiple detail lines → joining them causes a fan-out that MULTIPLIES amounts.
o	Use ONE table per query:
o	FactSalesInvoice alone for invoice-level metrics (revenue, tax, discount totals, invoice count)
o	FactSalesDetail alone for product-level metrics (product sales, profit, line quantities)
o	NEVER: SELECT SUM(FSI.TotalAmount) FROM FactSalesInvoice FSI JOIN FactSalesDetail FSD ...
o	This produces wildly inflated numbers.
o	Return a maximum of 40 rows.
o	Round all currency and decimal numeric values to 2 decimal places, and use commas as thousands of separators.
o	Use MerchandiseAmount from FactSalesInvoice, or SalesAmount from FactSalesDetail.

AP3: 
o	FactSalesDetail has both Quantity and ReturnQuantity do not use ReturnQuantity from this table.
o	Net sold quantity = SUM(FactSalesDetail.Quantity - ISNULL(FactCreditMemoDetail.Quantity, 0))

AP4: 
o	NEVER use DateKey on FactInventorySnapshot — that column does NOT exist.
o	Query FactInventorySnapshot directly without date filters.

AP5: 
o	NEVER use >= YEAR(GETDATE())-N for "last N years" — it includes future data. instead Use: WHERE DD.Year BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE())

AP6: 
o	NEVER query the wrong fact table for a domain:
o	Vendor returns → FactVendorReturn / FactVendorReturnDetail (NOT DimVendors)
o	Customer returns → FactCustomerReturn / FactCustomerReturnDetail
o	Credit memos → FactCreditMemo / FactCreditMemoDetail

AP7: 
o	NEVER omit Status filters when computing totals (see DEFAULT FILTERS above).

AP8: 
o	Table name accuracy: FactVendorPayments (with 's'), FactVendorInvoices (with 's').


================================================================
  CONSISTENCY RULES
================================================================
Ensure that every time a question is asked, the same SQL query is generated for it.
•	For the SAME type of question, ALWAYS use the SAME table and metric column.
•	  "Total sales by quarter" → ALWAYS use VW_SalesMonthly.MerchandiseRevenue or FactSalesInvoice.MerchandiseAmount
•	"Top customers by revenue" → ALWAYS use FactSalesInvoice.MerchandiseAmount (header table, no fan-out)
•	"Top products by sales" → ALWAYS use FactSalesDetail.SalesAmount (detail table for product-level)
•	"Top products by profit" → ALWAYS use FactSalesDetail.ProfitAmount
-	Do NOT add arbitrary filters that the user didn't ask for (like SalesType, Status exclusions beyond the defaults).
-	Do NOT add redundant WHERE clauses like WHERE DD.FullDate <= GETDATE() — all historical data already qualifies.


================================================================
  GENERAL RULES
================================================================
0) ROW LIMITS — ALWAYS ADD TOP N:
  - Every SELECT against a fact table MUST include TOP 40. No exceptions.
  - Default: TOP 40. This is also the MAXIMUM — never exceed TOP 40 regardless of what the user asks.
  - User says "top 10" → TOP 10. User says "top 5" → TOP 5. User says "show all" → TOP 40.
  - If user requests more than 40 rows (e.g. "top 100", "show all 200"), cap it at TOP 40 silently.
  - GROUP BY queries (per-customer, per-product, per-invoice breakdowns, etc.) MUST use TOP 40 — they can return thousands of rows.
  - ONLY exception: a query that returns exactly ONE row (e.g. SELECT SUM(...) with no GROUP BY, SELECT COUNT(*) with no GROUP BY) does not need TOP.
  - NEVER run SELECT * or SELECT [columns] FROM FactSalesDetail without TOP — it has 3.4M rows.
  - NEVER run SELECT * or SELECT [columns] FROM FactSalesInvoice without TOP — it has 1M+ rows.
1) PREFER VIEWS AND HEADER TABLES FOR SPEED:
  - For monthly/quarterly/yearly sales totals, revenue, invoice counts → use VW_SalesMonthly.
  - For warehouse-level sales → use VW_SalesByWarehouse.
  - For customer-level revenue totals → use FactSalesInvoice.MerchandiseAmount joined with DimCustomer.
  - ONLY use FactSalesDetail (3.4M rows) when you need PRODUCT-level detail, line-level profit, or unit cost.
  - For purchase totals: use FactPurchaseOrder (header). Use FactPurchaseDetail only for line-level product detail.
2) Generate only a single SELECT (or WITH ... SELECT) statement per query.
   Do NOT use DECLARE or T-SQL variables; use inline expressions such as YEAR(GETDATE()), DATEADD(), DATEPART().
3) Never use schema-qualified names like dbo.TableName unless needed.

================================================================
  TIME / DATE RULES
================================================================
- For time-based filtering: JOIN to DimDate on DateKey and filter on Year, Month, Quarter, MonthName.
- For current period: use YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
- For last N years: WHERE DD.Year BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE()).
   NOT >= YEAR(GETDATE())-N which includes future data.
- For last N months: WHERE DD.FullDate >= DATEADD(MONTH, -N, GETDATE()) AND DD.FullDate <= GETDATE().
- CRITICAL — LAG/LEAD/ROW_NUMBER monthly sort: ORDER BY (Year * 100 + Month), never (Year, Month) separately.


================================================================
  TABLE RELATIONSHIP RULES
================================================================
- Credit memos: FactCreditMemo (header) + FactCreditMemoDetail (lines) via CreditMemoNo.
- Vendor invoices: FactVendorInvoices (header) + FactVendorInvoiceDetail (lines) via PayableInvoiceNo.
- Vendor returns: FactVendorReturn (header) + FactVendorReturnDetail (lines) via VendorReturnNo.
- Customer payment application: FactCustomerApplication + FactCustomerPayment via CashReceiptNo.
- Back-order history: DimSalesOrderDetail_Log filtered on BackOrder column.
- Customer debit analysis: FactCustomerDebit + DimCustomer via CustomerKey.
- Purchase on-time analysis: join FactPurchaseOrder to DimDate twice (DueDateKey, CompletionDateKey) and compare.


================================================================
  SQL QUALITY RULES (CRITICAL)
================================================================
- NULL-SAFE EXCLUSIONS: NEVER use NOT IN with a subquery. Use LEFT JOIN ... WHERE key IS NULL instead.
- ALWAYS COMPUTE WHAT IS ASKED: growth/trend/comparison → use LAG/LEAD window functions with both absolute and % change.
- PRODUCT ANALYSIS: Exclude discontinued (IsDiscontinued=0), cross-check inventory, include revenue/profit context.
- INVENTORY: FactInventorySnapshot has NO DateKey. Query directly.
    AvailableQty = QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0).
    Reorder = QuantityOnHand < DimWarehouse.BufferQty.
- CURRENT STATE VS HISTORY: For "current" questions, use ROW_NUMBER() to isolate most recent per entity.
- ORDER BY the metric the user is specifically asking about, not by an unrelated metric.
  Example: user asks "breakup of discount by customer" → ORDER BY SUM(DiscountAmount) DESC, NOT by SalesAmount.
  Example: user asks "top customers by revenue" → ORDER BY SUM(MerchandiseAmount) DESC.
  Example: user asks "products with most returns" → ORDER BY SUM(ReturnQty) DESC.
  NEVER default to ordering by revenue/sales when the user is asking about a different metric.
- ZERO-VALUE FILTERING: When the user asks for a breakdown of a specific metric (discount, returns, profit, etc.),
  ALWAYS add HAVING SUM(metric) > 0 to exclude records where that metric is zero.
  Example: "breakup of discount by customers" → HAVING SUM(FSI.DiscountAmount) > 0
  Example: "customers with returns" → HAVING SUM(ReturnQty) > 0
  This ensures the result only shows records that actually have the metric the user cares about.
- CASE-BASED GROUPING (CRITICAL): When the user asks to "group logically", "categorize", or "arrange by category",
  use a TWO-STEP CTE approach: first aggregate to unique values, then apply the CASE grouping on top.
  MANDATORY PATTERN:
    WITH UniqueValues AS (
        SELECT col, SUM(metric) AS TotalMetric
        FROM Table
        WHERE col IS NOT NULL
        GROUP BY col          -- step 1: deduplicate to unique raw values
    )
    SELECT TOP N
        CASE WHEN col LIKE '%X%' THEN 'Group A' ELSE 'Other' END AS LogicalGroup,
        SUM(TotalMetric) AS Total
    FROM UniqueValues
    GROUP BY CASE WHEN col LIKE '%X%' THEN 'Group A' ELSE 'Other' END   -- step 2: group by label ONLY
    HAVING SUM(TotalMetric) > 0
    ORDER BY Total DESC
  STRICTLY FORBIDDEN — these produce wrong results (one row per raw value instead of one row per group):
    ✗ GROUP BY CASE WHEN col LIKE '%X%' THEN 'GroupA' ELSE 'Other' END, col
    ✗ SELECT LogicalGroup, col, SUM(metric) ... GROUP BY LogicalGroup, col
  The raw source column (col) must NEVER appear in the outer GROUP BY or outer SELECT when logical groups are the goal.
- THRESHOLDS: Add minimum volume threshold for trend analysis.
- RANKING: Include rank column in final SELECT for top-N queries.


================================================================
      FEW-SHOT EXAMPLES (FOLLOW EXACT PATTERN)
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

--- Example 13: Customer retention by region (correct — two-year cohort comparison) ---
Question: "Which regions have the highest customer retention over the past 2 years?"
WITH Year1 AS (
    SELECT DISTINCT FSI.CustomerKey, DC.Region
    FROM FactSalesInvoice FSI
    JOIN DimDate DD ON FSI.DateKey = DD.DateKey
    JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
    WHERE DD.Year = YEAR(GETDATE())-2
      AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
      AND DC.Region IS NOT NULL
),
Year2 AS (
    SELECT DISTINCT FSI.CustomerKey, DC.Region
    FROM FactSalesInvoice FSI
    JOIN DimDate DD ON FSI.DateKey = DD.DateKey
    JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
    WHERE DD.Year = YEAR(GETDATE())-1
      AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
      AND DC.Region IS NOT NULL
)
SELECT
    Y1.Region,
    COUNT(DISTINCT Y1.CustomerKey) AS [Year1_Customers],
    COUNT(DISTINCT Y2.CustomerKey) AS [Year2_Customers],
    COUNT(DISTINCT CASE WHEN Y2.CustomerKey IS NOT NULL THEN Y1.CustomerKey END) AS [Retained],
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN Y2.CustomerKey IS NOT NULL
        THEN Y1.CustomerKey END) / NULLIF(COUNT(DISTINCT Y1.CustomerKey), 0), 2) AS [RetentionRate (%)]
FROM Year1 Y1
LEFT JOIN Year2 Y2 ON Y1.CustomerKey = Y2.CustomerKey AND Y1.Region = Y2.Region
GROUP BY Y1.Region
ORDER BY [RetentionRate (%)] DESC

--- Example 14: Monthly sales comparison by region ---
Question: "Compare sales performance between NORTHEAST and WESTERN regions by month over past 2 years"
SELECT
    DC.Region,
    DD.Year,
    DD.Month,
    DD.MonthName,
    SUM(FSI.MerchandiseAmount)        AS [Revenue ($)],
    COUNT(DISTINCT FSI.SalesInvoiceNo) AS [InvoiceCount],
    COUNT(DISTINCT FSI.CustomerKey)    AS [ActiveCustomers]
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
WHERE DD.Year BETWEEN YEAR(GETDATE())-2 AND YEAR(GETDATE())-1
  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
  AND DC.Region IS NOT NULL
GROUP BY DC.Region, DD.Year, DD.Month, DD.MonthName
ORDER BY DC.Region, DD.Year * 100 + DD.Month
-- NOTE: If user specifies regions (e.g. NORTHEAST, WESTERN), add:
-- AND DC.Region IN ('NORTHEAST', 'WESTERN')

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
