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

=== STAR SCHEMA: StarScemaSPARS ===
Designed for: Sales Analysis, Purchase Analysis, Inventory Monitoring, Profitability Reporting,
Customer & Vendor Analytics, Customer Returns & Payments, Vendor Returns & Payments,
Back Order Information, Consignments, Sales Rep Commissions.

*** READ-ONLY ACCESS ONLY ***
This application has STRICTLY read-only database access.
NEVER generate CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, TRUNCATE, EXEC, EXECUTE, MERGE, or any DDL/DML.
Execute ONLY SELECT (or WITH ... SELECT) queries. Any non-SELECT query will be rejected.

================================================================
                    DIMENSION TABLES (18)
================================================================

Table: DimCustomer
Purpose: (This table contains the Customer's master data used for sales and receivable analytics.)
  CustomerKey         (Surrogate key uniquely identifying a customer record. It's the primary key of this table.)
  CustomerID          (Unique Customer Identification number Used in SPARS (source systems).)
  CustomerCode        (Alternate reference code of the Customer. Its normally provided by the customer.)
  CustomerName        (Full customer or company name.)
  CustomerType        (Type of the Customer. For Example; Retail, Wholesale, or other classifications.)
  Category            (It's the Category of the Customer. For Example; Designer, Consumer, Discount Store, Furniture Store, Home Centers etc.)
  Class               (It's the Internal classification. For Example; Gold, Silver, Platinum etc.)
  City                (City of the respective Customer.)
  State               (State of the respective Customer.)
  Country             (Country of the respective Customer.)
  RegionKey           (Geographic region reference key from DimRegion Table. It refers to the sales or geographic region to which this customer belongs.)
  Province            (Province of the respective Customer (if applicable).)
  Phone               (Primary phone number of the respective Customer.)
  Email               (Primary email address of the respective Customer.)
  PriceCategoryKey    (Price category reference key from DimPriceCategory Table. It refers to the assigned pricing tier applicable to this customer.)
  PaymentTermKey      (Payment term reference key from DimPaymentTerms Table. It refers to the default payment terms applicable to this customer.)
  SalesDiscount       (Default discount percentage.)
  TaxRate             (Default tax rate applied to the customer.)
  CreditLimit         (Maximum credit amount allowed for this customer account.)
  CurrentBalance      (Current Balance of the Customer.)
  Status              (Current account status of the customer. Possible values: Active (0), Sales Hold (1), Credit Hold (2).)
  IsDropShipOnly      (Drop-ship only flag.)
  IsSpecialPricing    (Flag indicating if special pricing rules apply.)
  CreatedDate         (Record creation timestamp.)
  ModifiedDate        (Last modification timestamp.)

Table: DimDate
Purpose: (Time dimension supporting all facts.)
  DateKey             (Surrogate date key. It's the primary key of this table.)
  FullDate            (Actual calendar date.)
  Year                (Year component.)
  Quarter             (Quarter number.)
  Month               (Month number.)
  MonthName           (Month name.)

Table: DimProduct
Purpose: (This table contains the master data of the items (products) for inventory and sales analysis.)
  ProductKey          (Surrogate product key. It's the primary key of this table.)
  ItemID              (Unique identification number of the item (product) used as Business Identifier in SPARS.)
  ItemCode            (It's the Secondary identification code of the item (product). It is normally provided by the clients. This is the number that the customers used for this product in their system.)
  ItemName            (Item (Product) name or description.)
  Category            (Product category.)
  Collection          (Collection or series.)
  Design              (Pattern or design.)
  DesignDescription   (Design description.)
  Color               (Primary color.)
  ColorDescription    (Color Description.)
  Size                (Product Size.)
  SizeDescription     (Size Description.)
  Brand               (Brand name.)
  Country             (Country of origin.)
  Vendor              (Default vendor of the respective item (product).)
  MaterialType        (Composition material (e.g., Wool, Silk).)
  Shape               (Shape of the product (e.g., Rectangular, Round).)
  Weight              (Product weight.)
  Area                (Surface area.)
  Volume              (Volume.)
  IsDiscontinued      (Flag indicating if product is no longer for sale.)
  Status              (Lifecycle status.)
  SetItem             (Y = Yes, N = No.)
  CreatedDate         (Creation timestamp.)
  ModifiedDate        (Last update timestamp.)
  Construction        (Construction.)
  ImagePath           (It's the Path of where the Image of the respective product (item) is available.)
  MinOrderQty         (Min Order Quantity.)
  CollectionType      (Collection Type.)

Table: DimVendors
Purpose: (This table contains the master data of Vendors for procurement analytics.)
  VendorKey           (Surrogate vendor key. It's the primary key of this table.)
  VendorID            (Unique identification number of the vendors used in SPARS.)
  VendorName          (Full company name of the Vendor.)
  VendorType          (Vendor classification.)
  Category            (Business category of the respective vendor.)
  Class               (Priority or quality class.)
  Region              (Geographic region.)
  Status              (Status of the vendor. Possible values: Active (0), Purchase Hold (1), Payment Hold (2).)
  City                (Vendor city.)
  State               (Vendor state.)
  Country             (Vendor country.)
  PaymentTerm         (Payment terms.)
  PaymentPriority     (Settlement priority.)
  TaxRate             (Tax percentage applied to vendor invoices.)
  CreditLimit         (Vendor credit limit.)
  FurnitureVendor     (Furniture supplier flag.)
  DesignerRate        (Special percentage rate for designers.)
  InTransitDays       (Estimated number of days for goods to arrive from this vendor after shipment, used for delivery planning and inventory management.)

Table: DimWarehouse
Purpose: (This table contains the list of the Warehouse, its location, its manager, its type, status and other information required for analysis.)
  WarehouseKey        (Surrogate Warehouse key. It's the primary key of this table.)
  WarehouseID         (A Unique location identifier used in SPARS.)
  WarehouseName       (Descriptive name of the warehouse Name.)
  City                (City.)
  State               (State.)
  Country             (Country.)
  ZIP                 (Postal code.)
  Address             (Street address.)
  Phone               (Contact number.)
  Email               (Contact email.)
  ManagerID           (Manager identifier.)
  StoreType           (Location type.)
  BusinessDivisionID  (Division mapping.)
  BufferQty           (Safety stock quantity.)
  TaxID               (Tax identifier.)
  TimeZoneHours       (UTC offset.)
  IsActive            (Operational flag.)
  WHSStatus           (Descriptive warehouse status indicating the current operational state of this warehouse. Possible values: Active (1), Inactive (any other value).)
  CreatedDate         (Creation timestamp.)
  ModifiedDate        (Last update timestamp.)

Table: DimInvoiceAddresses
Purpose: (This table contains the Shipping and billing information of the respective invoices of the customer. Shipping and Billing Address related information of invoices is stored in this table.)
  AddressesKey        (Surrogate key. It's the primary key of this table.)
  SalesInvoiceNo      (A Unique Sales Invoice Number used in SPARS.)
  State               (Destination state.)
  Zip                 (Zip.)
  City                (Destination city.)
  Country             (Destination country.)
  ShipToAddress       (Ship To Address.)
  SalesOrderNo        (Sales Order Number of the respective Sales Invoice.)
  BillToAddress       (Bill To address.)
  BillTocity          (Bill to City.)
  BillToState         (Bill to State.)
  BillToZip           (Bill To Zip.)

Table: DimPaymentTerms
Purpose: (This table contains the information (Definitions) of the Payment terms.)
  PaymentTermKey      (It's the primary key of this table.)
  PaymentTermNo       (Business key (term code) for identification of a payment term.)
  Description         (Term description.)
  DueDays             (Number of days until payment is due.)
  DiscountDays        (Days within which early payment discount applies.)
  PaymentDiscount     (Discount percentage if paid early.)
  CreditCardTerms     (It's a Flag for credit card terms. If this flag will be enabled (1), then this payment term will be used for Credit Card payments as well. Otherwise if it will be disabled (0), then the respective payment term record will not be used for credit card payments.)

Table: DimPriceCategory
Purpose: (This table contains the definitions of the Price Category definitions.)
  PriceCategoryKey    (It's the primary key of this table.)
  CategoryNo          (A Unique identifier used in SPARS for Price Category. Its Business key (category code).)
  Description         (Price Category description.)
  Blocked             (It's a Flag indicating if category is inactive or active. If this flag will be enabled (1), then it means this price category is inactive.)

Table: DimSalesOrderDetail_Log
Purpose: (This table contains the information of the Sales Order Detail Log For BackOrder.)
  SalesOrderNo        (A Unique Sales Order Number.)
  ItemID              (A Unique Item Identification number.)
  SKU                 (A Unique Identification number of the SKU (Stocking Unit of the OAK Items).)
  LogSource           (It's the name of the Interface for which this log is being created.)
  LogReason           (Log Reason (either "Create", "Release").)
  BackOrder           (It's a Flag with values 1 means Yes or 0 means No.)
  LogDate             (Log Date (BackOrder created date / Back Order Released date).)

Table: DimBillOfLading
Purpose: (This table contains the master information of the Bill Of Ladings.)
  BillOfLadingKey     (Bill Of Lading Key. It's the primary key of this table.)
  BillOfLadingNo      (A Unique identifier used in SPARS as Bill of Lading Number.)
  CustomerKey         (Customer Reference Key from DimCustomer Table.)
  WarehouseKey        (Warehouse Reference Key from DimWarehouse Table.)
  Address1            (Address line 1.)
  Address2            (Address line 2.)
  City                (City.)
  State               (State.)
  Zip                 (Zip Code.)
  VehicleNo           (Vehicle Number.)
  Carrier             (Carrier Number.)
  Route               (Route.)
  ShipVia             (Ship Via.)
  ScacCode            (SCAC Code.)
  PickUpDateKey       (Date Reference Key from DimDate Table.)
  DeliveryDateKey     (Date Reference Key from DimDate Table.)
  TotalAmount         (Total Amount of the relevant Bill of Lading document.)
  Freight             (Freight amount of the relevant Bill of Lading document.)
  TotalCharges        (Total Charges.)
  FreightPrepaid      (Freight Prepaid.)
  CODCharges          (COD Charges.)
  CODAmount           (COD amount of the relevant Bill of Lading document.)
  CODChargesPrepaid   (COD ChargesPrepaid.)
  CarrierProNo        (Carrier Pro No.)
  Status              (Status.)
  ADDDateKey          (Date Reference Key.)

Table: DimBillOfLadingDetail
Purpose: (This table contains the detail information of the Bill Of Lading. This is used a detail table against the master information of the bill of lading stored in the DimBillofLading table.)
  BillOfLadingDetailKey  (Bill of lading detail Key. It's the primary key of this table.)
  BillOfLadingNo         (A Unique identifier used in SPARS as Bill of Lading Number.)
  PackingSlipNo          (A Unique identifier used in SPARS Packing Slip Number Reference (table FactPackingSlips column packingslipNo).)
  BaleNo                 (Bale Number.)
  Weight                 (Weight.)
  Charges                (Charges.)
  DeclareValue           (Declared Value of the Items (products).)
  TotalCUFT              (Total Area in Cubic Feet.)
  Rate                   (Rate.)
  RateRef                (Rate Ref.)
  HandlingUnit           (Handling Unit.)
  SideMark               (It is used a description of the respective line. Usually printed in reports and labels for respective line.)
  Description            (Description.)

Table: DimRugOAK
Purpose: (This Table contains the information of the Items (products) with OAK Type.)
  RugKey                 (Rug Oak Key. It's the primary key of this table.)
  SKU                    (A Unique Identification number of the SKU (Stocking Unit of Item type as OAK).)
  ItemID                 (Unique Item Identification number of the item (product).)
  ProductKey             (Product Reference Key from the DimProduct Table.)
  RugID                  (Rug ID.)
  StockNo                (Stock Number.)
  VendorKey              (Vendor Reference Key from DimVendors.)
  LocationID             (A Unique Identification number of the Location.)
  Category               (Category.)
  Collection             (Collection.)
  Design                 (Design.)
  Color                  (Color.)
  Size                   (Size.)
  SizeDescription        (Size Description.)
  DesignType             (Design Type.)
  PurchasePrice          (Purchase Price.)
  LastSalePrice          (Last Sales Price.)
  UnitPrice              (Unit Price.)
  SQFTPrice              (SQFT Price.)
  STDCost                (STD Cost.)
  Cost                   (Cost amount.)
  OrgPurchasePrice       (Original Purchase Price.)
  LastCredit             (Last Credit amount.)
  LastCreditDate         (LastCreditDate.)
  RTVDebitMemo           (RTV Debit Memo.)
  RTVDate                (RTVDate.)
  SerialNo               (Serial Number.)

Table: DimItemPrice
Purpose: (This table contains the Prices of the Items (Products).)
  ItemPriceKey        (Item Price Key. It's the primary key of this table.)
  ItemID              (A Unique Item Identification number of the item (product).)
  ProductKey          (Product Key Reference from DimProduct Table.)
  Pricecategory       (Price Category.)
  UnitPrice           (Unit Price of the respective item (product).)
  SQFTPrice           (SQFT Price of the respective item (product).)

Table: DimRegion
Purpose: (This table contains the definitions of the Regions.)
  RegionKey           (Region Key. It's the primary key of this table.)
  RegionNo            (A Unique identification number assigned to this Region in SPARS.)
  RegionName          (It's the name of the Region.)

Table: DimGLAccounts
Purpose: (This table contains the details of the General Ledger Accounts.)
  GLAccountKey        (Surrogate key. It's the primary key of this table.)
  AccountID           (Natural/business key of the account.)
  Description         (Name or title of the GL account.)
  Category            (Classification of the account.)
  TypeID              (Type of the account.)

Table: DimConsignmentAddresses
Purpose: (This table contains the information of the Addresses linked to the consignment documents.)
  AddressesKey        (Surrogate key. It's the primary key of this table.)
  ConsignmentNo       (A Unique Item Identification number of the consignment document.)
  City                (City part of the address for the respective consignment document.)
  State               (State part of the address for the respective consignment document.)
  Zip                 (Zip Code part of the address for the respective consignment document.)
  Country             (Country part of the address for the respective consignment document.)

Table: DimSalesRep
Purpose: (This table contains the definitions of the Sales Representatives.)
  SalesRepKey         (Surrogate key. It's the primary key of this table.)
  SalesRepID          (A Unique identification number of the Sales Representative used in SPARS.)
  SalesRepName        (Sales Representative Name.)
  SalesRepType        (SalesRepType = 1 ('Supplier'), SalesRepType = 2 ('Vendor'), SalesRepType = 3 ('Designer'), SalesRepType = 4 ('Sales Representative'), SalesRepType = 5 ('Internal Sales Person'), Otherwise SalesRepType = ('Marketing Company').)
  Category            (Category.)
  Class               (Class.)
  Region              (Region.)
  Status              (Status.)
  City                (City.)
  State               (State.)
  Country             (Country.)
  PaymentTerm         (Payment Term.)
  PaymentPriority     (Payment Priority.)
  TaxRate             (Tax.)
  CreditLimit         (Credit Limit.)
  DesignerRate        (Designer Rate.)

Table: COAMaping
Purpose: (This table contains the information of the Chart of Account.)
  SegmentID                  (Segment ID.)
  Value                      (Value.)
  AccountID                  (Account ID.)
  Main                       (Main.)
  AccDescr                   (Acc Description.)
  TypeID                     (Type.)
  Category                   (Category.)
  BalanceSheet_MainGroups    (Balance Sheet Main Groups.)
  BalanceSheet_SubGroups     (Balance Sheet Sub Groups.)
  BalanceSheet_Details       (Balance Sheet Details.)
  PLStatementMainGroups      (PL Statement Main Groups.)
  PLStatementSubGroups       (PL Statement Sub Groups.)
  PLStatementDetails         (PL Statement Details.)

================================================================
                      FACT TABLES (28)
================================================================

Table: FactSalesInvoice
Purpose: (This table contains the master (header level) information of the Sales Invoices.)
  SalesInvoiceKey     (Surrogate key. It's the primary key of this table.)
  SalesInvoiceNo      (It's a unique identification number of the Sales Invoice.)
  SalesOrderNo        (It's a unique identification number of the Sale Order Number associated with respective Sales Invoice record.)
  PackingSlipNo       (It's a unique identification number of the Packing Slip associated with respective Sales Invoice record.)
  DateKey             (It's a Invoice date Key of the DimDate Table.)
  OrderDateKey        (It's a sales order date Key of the DimDate Table.)
  CustomerKey         (Customer reference from DimCustomer Table.)
  AddressesKey        (It's a unique address key from DimInvoiceAddresses Table. Shipping destination.)
  WarehouseKey        (It's a unique address key from DimWarehouse Table. Fulfillment Warehouse.)
  PaymentTermKey      (It's a unique address key from DimPaymentTerms Table. Payment terms.)
  PriceCategoryKey    (It's a unique address key from DimPriceCategory Table. Price Category.)
  SalesType           (Sales classification. It could have values: SO0 or CS0. SO0 = Sales Invoice, CS0 = Consignment Invoice.)
  InvoiceType         (Document type. It could have values: S or O. S = Sales Invoice, O = One Step Invoice.)
  Status              (Invoice status. (i-e; Close, Open, Partially Shipped, Void).)
  TotalQuantity       (Total quantity.)
  TotalAmount         (Total amount.)
  TaxAmount           (Total Tax Amount.)
  ShippingCharges     (Shipping fees.)
  HandlingCharges     (Handling fees.)
  ServiceCharges      (Service fees.)
  MerchandiseAmount   (Merchandise value.)
  ServicesAmount      (Service revenue.)
  AppliedAmount       (Applied payments.)
  DiscountAmount      (Discount Amount (If any).)
  TotalWeight         (Total shipment weight.)

Table: FactSalesDetail
Purpose: (This table contains the detail level (line-level) information of the Sales Invoices.)
  SalesKey            (Surrogate key. It's the primary key of this table.)
  SalesInvoiceNo      (It's a unique identification number of the Sales Invoice Reference from (table FactSalesInvoice Column SalesInvoiceNo).)
  InvoiceLineNumber   (It's a unique identification number of the Line of a Sale Invoice.)
  DateKey             (Invoice line date reference of the DimDate Table.)
  OrderDateKey        (Order date reference of the DimDate Table.)
  ProductKey          (Product reference of the DimProduct Table.)
  CustomerKey         (Customer reference of the DimCustomer Table.)
  WarehouseKey        (Warehouse reference of the DimWarehouse Table.)
  ItemType            (Sale Item category. It could have values: O or P. O means OAK Item, P means Program Item.)
  Quantity            (Sale Item Quantity sold.)
  UnitPrice           (Sale Item Unit price, Price charged per unit.)
  UnitCost            (Sale Item cost per unit (at time of sale).)
  DiscountAmount      (Sale Item Discount subtracted from specific line.)
  SalesAmount         (Sale Item Net sales amount.)
  TaxAmount           (Tax allocated to this line.)
  ShippingCharges     (Sale Item Shipping fees allocated to this line.)
  ProfitAmount        (Sale Item Net Profit amount.)

Table: FactPurchaseOrder
Purpose: (This table contains the master (header level) information of the Purchase Orders.)
  PurchaseOrderKey    (Surrogate key. It's the primary key of this table.)
  PurchaseOrderNo     (It's a unique identification number of the Purchase Order.)
  VendorKey           (Vendor reference from DimVendors Table.)
  DateKey             (Issue date reference from DimDate Table. It refers to Purchase Order Date.)
  OrderDateKey        (Order Date reference from DimDate Table.)
  DueDateKey          (Date Reference Key from DimDate Table. It refers to Due Date of the Purchase Order till when this purchase order Payment must be fulfilled.)
  CancelDateKey       (Date Reference Key from DimDate Table. It refers to the Cancel Date of the Purchase Order (If any).)
  ETADateKey          (Date Reference Key from DimDate Table. It refers to the Estimated Time of Arrival (ETA Date) of the Purchase Order.)
  WarehouseKey        (It's a Reference Key from DimWarehouse Table. It refers to the Purchase Receiving warehouse.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the Customer Information for whom this purchase order is placed.)
  TotalQty            (Purchase Order Total Items quantity.)
  TotalAmount         (Purchase Order Grand Total amount.)
  TotalTax            (Purchase Order Total tax.)
  InTransitQty        (Purchase Order Quantity currently shipping from vendor.)
  ReceivedQty         (Purchase Order Received quantity.)
  Status              (Purchase Order status (Open, Closed, Partially Shipped, Void, New, Cancel).)
  DropShipment        (Flag for direct-to-customer shipments (1=Yes, 0=No).)

Table: FactPurchaseDetail
Purpose: (This table contains the detail level (line-level) information of the Purchase Orders.)
  PurchaseLineKey     (Surrogate key. It's the primary key of this table.)
  PurchaseOrderNo     (A Unique Purchase Order number in SPARS.)
  Line_No             (Unique Line number of the Purchase Order.)
  VendorKey           (Vendor reference Key from DimVendors Table. It refers to the vendor information of respective VendorKey.)
  ProductKey          (Product reference from DimProduct Table. It refers to the product information of the respective ProductKey.)
  DateKey             (Issue date reference key from the DimDate Table. It refers to the Date of the Product line addition date.)
  DueDateKey          (Date reference key from the DimDate Table. Expected receipt date reference.)
  WarehouseKey        (Warehouse reference key from the DimWarehouse Table. Destination warehouse reference.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the Customer Information of the respective CustomerKey.)
  OrderQty            (Purchase Item Quantity requested from vendor.)
  UnitCost            (Purchase Item Cost per unit.)
  LineAmount          (Purchase Item Total line cost Amount.)
  TaxAmount           (Purchase Item Line tax Amount.)
  DiscountPercent     (Purchase Item Discount percent for specific line item.)
  InTransitQty        (Purchase Item Quantity currently mid-shipment.)
  ReceivedQty         (Purchase Item Received quantity.)
  Area                (Area.)
  Length              (Length.)
  ReceivedLength      (Received Length.)
  SQFTCost            (Purchase Item Cost per square foot.)

Table: FactInventorySnapshot
Purpose: (This table contains the Inventory position snapshots of the Items (Products) across all Warehouses. It stores the current inventory quantities and values per product per warehouse.)
  InventorySnapshotKey  (Surrogate key. It's the primary key of this table.)
  ProductKey            (Product reference key from DimProduct Table. It refers to the product information of the respective item.)
  WarehouseKey          (Warehouse reference key from DimWarehouse Table. It refers to the warehouse where this inventory is stored.)
  QuantityOnHand        (Total available inventory quantity currently in the warehouse.)
  InventoryValue        (Total monetary value of the inventory on hand.)
  PickingQuantity       (Quantity currently allocated for active picking tickets.)
  SalesOrderQuantity    (Quantity reserved against open sales orders.)
  DamagedQuantity       (Quantity identified as damaged stock.)
  ShowRoomQuantity      (Quantity allocated for showroom display purposes.)
  MissingBinQuantity    (Quantity recorded as missing from bin locations.)
  AverageCost           (Average unit cost of the inventory item in this warehouse.)

Table: FactVendorInvoice
Purpose: (This table contains the master (header level) information of the Vendor (Payable) Invoices. It stores all invoices received from Vendors.)
  VendorInvoiceKey      (Surrogate key. It's the primary key of this table.)
  PayableInvoiceNo      (A unique identification number of the Payable (Vendor) Invoice used in SPARS.)
  VendorKey             (Vendor reference key. Resolved from DimVendors.)
  InvoiceType           (Code classifying the invoice type. Possible values: P = Purchase Invoice, T = Transfer Invoice.)
  PaymentTermKey        (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this vendor invoice.)
  Status                (Current invoice status. Possible values: Close (0), Open (1), Partially Paid (2), Void (3).)
  VendorInvoiceRef      (Vendor's own reference or invoice number as provided by the vendor.)
  VendorInvoiceDateKey  (Date reference key from DimDate Table. It refers to the date on the vendor's original invoice.)
  DueDateKey            (Date reference key from DimDate Table. It refers to the payment due date of this vendor invoice.)
  EntryDateKey          (Date reference key from DimDate Table. It refers to the date when this invoice was entered into SPARS.)
  TotalAmount           (Total vendor invoice amount before any payments or adjustments.)
  PaidAmount            (Amount already paid to the vendor against this invoice.)
  WarehouseKey          (Warehouse reference key from DimWarehouse Table. It refers to the warehouse associated with this vendor invoice.)
  PeriodID              (Accounting period identifier associated with this vendor invoice.)

Table: FactVendorPayments
Purpose: (This table contains the master (header level) information of the Vendor Payments. It stores all payments made to Vendors for procurement and accounts payable analytics.)
  PaymentKey          (Surrogate key. It's the primary key of this table.)
  PaymentNo           (A unique identification number of the Vendor Payment used in SPARS.)
  VendorKey           (Vendor reference key from DimVendors Table. It refers to the vendor to whom this payment was made.)
  DocDateKey          (Date reference key from DimDate Table. It refers to the document date of the payment record.)
  PaymentDateKey      (Date reference key from DimDate Table. It refers to the actual date when the payment was made to the vendor.)
  PaymentAccount      (Bank or cash account that was debited for this payment.)
  DiscountAccount     (GL account where any early payment discount taken is recorded.)
  DocType             (DocType = W ('WireTransfer'), DocType = C ('Check'), DocType = I ('IDC#'), DocType = S ('Cash'), DocType = R ('ReverseEntry'), DocType = H ('ACH'), DocType = D ('CreditCard').)
  Amount              (Total payment amount sent to the vendor.)
  AppliedAmount       (The payment amount that has been applied to outstanding vendor invoices.)
  AppliedDiscount     (Discount amount deducted from the payment at the time of settlement.)
  Status              (Status = B ('Bounced'), Status = C ('Close'), Status = N ('New'), Status = O ('Open'), Status = V ('Void').)
  PaymentType         (PaymentType = P ('Regular Payment'), PaymentType = O ('One Step Payment'), PaymentType = A ('Advance Payment'), PaymentType = N ('Non AP Payment').)
  PeriodID            (Accounting period identifier associated with this vendor payment.)
  VoidDateKey         (Date reference key from DimDate Table. It refers to the document date of the void record.)

Table: FactCustomerReturn
Purpose: (This table contains the master (header level) information of the Customer Returns. It stores all return transactions initiated by customers, supporting returns management.)
  ReturnHeaderKey          (Surrogate key. It's the primary key of this table.)
  CustomerReturnNo         (A unique identification number of the Customer Return used in SPARS.)
  SalesInvoiceNo           (The original Sales Invoice number against which this return was raised. Reference (table FactSalesInvoice column SalesInvoiceNo).)
  CreditMemoNo             (The Credit Memo number issued to the customer as a result of this return.)
  CustomerKey              (Customer reference key from DimCustomer Table. It refers to the customer who initiated this return.)
  DateReceivedKey          (Date reference key from DimDate Table. It refers to the date when the returned items were physically received.)
  CreditDateKey            (Date reference key from DimDate Table. It refers to the date when the credit was issued to the customer for this return.)
  InvoiceDateKey           (Date reference key from DimDate Table. It refers to the date of the original sales invoice associated with this return.)
  ReceiptType              (Type of receipt used to classify how the return was received.)
  ReturnStatus             (Status = 0 ('Closed'), Status = 1 ('Received'), Status = 3 ('New'), Status = 4 ('Confirmed').)
  TotalQty                 (Total quantity of items returned by the customer.)
  TotalAmount              (Total value or credit amount associated with this return.)
  ShippingHandlingAmount   (Shipping and handling charges related to processing this return.)
  QtyToWarehouse           (Quantity of returned items accepted and transferred back into warehouse stock.)
  TotalBales               (Number of bales or packages in the return shipment, applicable for rugs or large items.)

Table: FactCustomerReturnDetail
Purpose: (This table contains the detail (line level) information of the Customer Returns. Each record represents a single product line within a customer return, supporting detailed returns analysis and credit reconciliation.)
  ReturnKey           (Surrogate key. It's the primary key of this table.)
  CustomerReturnNo    (A unique identification number of the Customer Return used in SPARS.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer who initiated this return.)
  DateReceivedKey     (Date reference key from DimDate Table. It refers to the date when the returned items were physically received.)
  ProductKey          (Product reference key from DimProduct Table. It refers to the specific product (item) being returned on this line.)
  ReturnReason        (The reason provided for returning this product line.)
  ReturnQty           (Total quantity of this product physically returned by the customer.)
  CreditQty           (Quantity of this product line that has been approved and credited to the customer.)
  Cost                (The unit cost of the product at the time of the return.)
  Price               (The original selling price of the product at the time of the original sale.)
  Discount            (Discount percentage or amount that was applied to this product line at the time of the original sale.)
  ExtPrice            (Extended price representing the total credit amount for this return line (Quantity × Price after discount).)
  TaxAmount           (Tax amount applied to the credit for this return line.)
  SQFTPrice           (Price or cost per square foot applicable to this return line, primarily used for rugs and area-based products.)

Table: FactCreditMemo
Purpose: (This table contains the master (header level) information of the Credit Memos issued to customers. It stores all credit memo transactions generated as a result of customer returns, adjustments, or other credit-related activities, supporting accounts receivable and customer credit analytics.)
  CreditMemoKey            (Surrogate key. It's the primary key of this table.)
  CreditMemoNo             (A unique identification number of the Credit Memo used in SPARS.)
  CustomerKey              (Customer reference key from DimCustomer Table. It refers to the customer to whom this credit memo was issued.)
  DateKey                  (Date reference key from DimDate Table. It refers to the date when this record was added in SPARS.)
  SalesOrderNO             (The Sales Order number associated with this credit memo. Reference (FactSalesOrders column SalesOrderNo).)
  InvoiceNo                (The original Sales Invoice number against which this credit memo was raised. Reference (Table FactSalesInvoice Column SalesInvoiceNo).)
  CustomerReturnNo         (The Customer Return number linked to this credit memo, if this credit was generated as a result of a return. Reference (Table FactCustomerReturn column CustomerReturnNo).)
  ConsignmentInvoiceNo     (The original Consignment Invoice number against which this credit memo was raised. Reference (Table FactConsignments Column ConsignmentNo).)
  WarehouseKey             (Warehouse reference key from DimWarehouse Table. It refers to the warehouse associated with this credit memo.)
  CreditDateKey            (Date reference key from DimDate Table. It refers to the date when this credit memo record was added in SPARS.)
  InvoiceDateKey           (Date reference key from DimDate Table. It refers to the invoice date of this credit memo document.)
  OrderDateKey             (Date reference key from DimDate Table. It refers to the associated sales order date.)
  ShippedDateKey           (Date reference key from DimDate Table. It refers to the date when the original shipment was made.)
  TotalQty                 (Total quantity of items included on this credit memo.)
  TotalQtyInvoiced         (Total quantity that was originally invoiced on the related sales invoice.)
  TotalMerchandise         (Total value of merchandise only, excluding any service charges.)
  TotalServices            (Total value of services included on this credit memo.)
  TotalAmount              (Total credit memo amount before any adjustments or applications.)
  TaxAmount                (Total tax amount applied to this credit memo.)
  ShippingCharges          (Shipping charges associated with the return or credit.)
  HandlingCharges          (Handling charges associated with processing this credit memo.)
  ServiceCharges           (Service charges applicable to this credit memo.)
  SalesDiscount            (Discount amount applied to this credit memo.)
  PaymentDiscountAmount    (Payment discount amount deducted at the time of credit settlement.)
  AppliedAmount            (Amount of credit that has already been applied against outstanding balances.)
  Status                   (Current status of the credit memo. Possible values: Open (0), Partially Paid (1), Close (2), Void (9).)
  PriceCategoryKey         (Price category reference key from DimPriceCategory Table. It refers to the pricing tier that was applied to this credit memo.)
  PaymentTermKey           (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to any outstanding balance on this credit memo.)

Table: FactCreditMemoDetail
Purpose: (This table contains the detail (line level) information of the Credit Memos issued to customers. Each record represents a single product line within a credit memo, supporting detailed credit analysis and reconciliation against original sales invoices.)
  SalesKey            (Surrogate key. It's the primary key of this table.)
  SalesInvoiceNo      (A unique identification number of the Credit Memo used in SPARS. Links this detail line back to its parent credit memo header in FactCreditMemo.)
  InvoiceLineNumber   (The unique line number identifying this specific line within the credit memo document.)
  WarehouseKey        (Warehouse Reference Key.)
  DateKey             (Date reference key from DimDate Table. It refers to the invoiced date of this credit memo detail line.)
  OrderDateKey        (Date reference key from DimDate Table. It refers to the original order date associated with this credit memo detail line.)
  ProductKey          (Product reference key from DimProduct Table. It refers to the specific product (item) being credited on this line.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer to whom this credit memo line belongs.)
  SalesType           (Sales Type.)
  ItemType            (Item category code classifying the type of item on this credit line. Possible values: O = OAK Item, P = Program Item.)
  Quantity            (Total quantity of this product included on this credit memo line.)
  UnitPrice           (The original selling price per unit of this product at the time of the original sale.)
  UnitCost            (The original cost per unit of this product at the time of the original sale.)
  DiscountAmount      (Discount amount applied to this credit memo detail line.)
  SalesAmount         (Extended credit amount for this line after applying any discounts (Quantity × Unit Price − Discount).)
  TaxAmount           (Tax amount applied to this credit memo detail line.)
  ShippingCharges     (Shipping charges allocated to this specific credit memo detail line.)
  ProfitAmount        (Net profit amount for this credit memo line, calculated as the difference between the sales amount and the cost.)

Table: FactCustomerPayment
Purpose: (This table contains the master (header level) information of the Customer Payments (Cash Receipts). It stores all payments received from customers against their outstanding sales invoices, supporting accounts receivable and cash management analytics.)
  CashReceiptKey      (Cash Receipt Key.)
  CashReceiptNo       (A unique identification number of the Cash Receipt (Customer Payment) used in SPARS.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer who made this payment.)
  SalesInvoiceKey     (The Sales Invoice number against which this payment was received. Reference (Table FactSalesInvoice Column SalesInvoiceNo).)
  DocDateKey          (Date reference key from DimDate Table. It refers to the document date of this cash receipt record.)
  PaymentDateKey      (Date reference key from DimDate Table. It refers to the actual date when the payment was received from the customer.)
  ApprovedDateKey     (Date reference key from DimDate Table. It refers to the date when this payment was approved in SPARS.)
  BounceDateKey       (Date reference key from DimDate Table. It refers to the date when this payment was marked as bounced.)
  CashAccount         (The bank or cash GL account that received this payment.)
  CreditAccount       (The GL account credited for this payment (revenue or receivable account).)
  DiscountAccount     (The GL account where any discount granted to the customer for this payment is recorded.)
  DocType             (DocType = W ('WireTransfer'), DocType = C ('Check'), DocType = I ('IDC#'), DocType = S ('Cash'), DocType = R ('ReverseEntry'), DocType = D ('CreditCard'), DocType = F ('KeyOff'), DocType = H ('ACH').)
  Amount              (Total payment amount received from the customer.)
  AppliedAmount       (The payment amount that has been applied against outstanding customer invoices.)
  AppliedDiscount     (Early payment discount amount granted to the customer and deducted from the payment.)
  Status              (Status = B ('Bounced'), Status = C ('Close'), Status = N ('New'), Status = O ('Open'), Status = V ('Void').)
  PeriodID            (Accounting period identifier associated with this customer payment.)

Table: FactCustomerApplication
Purpose: (This table contains the detail level information of Customer Payment Applications. It records how a single customer payment or credit memo is applied across multiple invoices, supporting detailed accounts receivable reconciliation and cash application analytics.)
  CRBatchApplicationNo    (A unique identification number of the Cash Receipt Batch Application used in SPARS. It groups all application lines belonging to the same batch.)
  LineNo                  (The sequential line number identifying this specific application line within the batch.)
  CustomerKey             (Customer reference key from DimCustomer Table. It refers to the customer whose payment or credit is being applied.)
  SalesInvoice            (The Sales Invoice number to which this payment or credit is being applied. Reference (Table FactSalesInvoice Column SalesInvoiceNo).)
  CashReceipt             (The Cash Receipt (Customer Payment) number being applied to the invoice on this line. Reference (Table FactCustomerPayment column CashReceiptNo).)
  CreditMemo              (The Credit Memo number being applied to the invoice on this line, if the application involves a credit memo instead of a cash payment. Reference (Table FactCreditMemo column CreditMemoNo).)
  DocDateKey              (Date reference key from DimDate Table. It refers to the document date of this batch application record.)
  TransactionDateKey      (Date reference key from DimDate Table. It refers to the actual date when this payment or credit application transaction was processed.)
  ControlAccount          (The GL control or suspense account used to manage the receivable balance for this application.)
  DiscountAccount         (The GL account where any discount taken on this application line is recorded.)
  InvoiceBalance          (The outstanding balance on the invoice before this payment or credit application was processed.)
  AppliedAmount           (The amount of the payment or credit that has been applied to the invoice on this specific line.)
  DiscountAmount          (The discount amount taken by the customer on this specific application line.)
  DocType                 (Document type code classifying the nature of this application (e.g., Payment, Credit Memo, Adjustment).)
  WriteOff                (Amount written off against this invoice application line.)
  PeriodID                (Accounting period identifier associated with this customer payment application.)

Table: FactCustomerDebit
Purpose: (This table contains the summary level information of Customer Credit Memos and Debit Adjustments. It stores all service-based or adjustment-type credit and debit transactions issued to customers that do not involve physical product returns, supporting accounts receivable adjustment and credit management analytics.)
  CreditMemoKey           (Surrogate key. It's the primary key of this table.)
  CustomerDebitNo         (A unique identification number of the Customer Debit or Credit Memo used in SPARS (ERP).)
  CustomerKey             (Customer reference key from DimCustomer Table. It refers to the customer to whom this debit or credit adjustment was issued.)
  InvoiceNo               (The original Sales Invoice number against which this debit or credit adjustment was raised. Reference (Table FactSalesInvoice, column SalesInvoiceNo).)
  WarehouseKey            (Warehouse reference key from DimWarehouse Table. It refers to the warehouse location that issued this credit or debit adjustment.)
  CreditDateKey           (Date reference key from DimDate Table. It refers to the invoice date of this debit or credit adjustment document.)
  InvoiceDateKey          (Date reference key from DimDate Table. It refers to the invoice date of the original sales document associated with this adjustment.)
  OrderDateKey            (Date reference key from DimDate Table. It refers to the original sales order date associated with this debit or credit adjustment.)
  ADDDateKey              (Date reference key from DimDate Table. It refers to the system entry date when this record was added into SPARS.)
  TotalServices           (Total value of services (e.g., cleaning, repair, installation) being credited or debited in this adjustment.)
  TotalAmount             (The final total amount of this debit or credit adjustment document.)
  TaxAmount               (Amount of tax being reversed or adjusted on this document.)
  ShippingCharges         (Shipping costs included in this credit or debit adjustment.)
  HandlingCharges         (Handling fees included in this credit or debit adjustment.)
  ServiceCharges          (Fees for services associated with this debit or credit adjustment.)
  SalesDiscount           (Any additional sales discount amount applied to this adjustment document.)
  PaymentDiscountAmount   (Cash or payment discount amount reversed or applied on this adjustment document.)
  OpenCredit              (The remaining balance of this credit that has not yet been applied to any outstanding invoice.)
  AppliedAmount           (The amount of this credit that has already been applied against outstanding customer invoices.)
  CreditApplied           (Flag or amount indicating the total credit that has been applied from this document.)
  Status                  (Current status of this debit or credit adjustment record. Possible values: Open (0), Partially Paid (1), Close (2), Void (9).)
  InvoiceType             (Internal document type code classifying the nature of this adjustment.)
  SalesType               (Sales classification code identifying the type of sale associated with this adjustment (e.g., SO = Sales Order).)

Table: FactVendorReturn
Purpose: (This table contains the summary (header level) information of Vendor Returns. It stores all return transactions initiated against vendors for goods being sent back, supporting procurement, accounts payable and vendor relationship analytics.)
  VendorReturnKey       (Surrogate key. It's the primary key of this table.)
  VendorReturnNo        (A unique identification number of the Vendor Return used in SPARS.)
  VendorKey             (Vendor reference key from DimVendors Table. It refers to the vendor to whom the goods are being returned.)
  PaymentTermKey        (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this vendor return transaction.)
  InvoiceType           (Code classifying the type of this vendor return document. Value will always be D (Debit Memo / Vendor Return) for all records in this table.)
  Status                (Current status of the vendor return record. Possible values: Close (0), Approved (1), Partially Paid (2), Void (3).)
  VendorInvoiceRef      (The vendor's own reference or invoice number associated with this return transaction, as provided by the vendor.)
  VendorReturnDateKey   (Date reference key from DimDate Table. It refers to the date of the vendor return document.)
  WarehouseKey          (Warehouse reference key from DimWarehouse Table. It refers to the warehouse from which the goods are being returned to the vendor.)
  TotalAmount           (Total value of goods being returned to the vendor on this return document.)
  PaidAmount            (Amount already paid or credited by the vendor.)
  DiscountAvailed       (The actual discount amount that has been taken or applied against this vendor return.)
  DiscountAmount        (Discount amount applied on this vendor return document.)
  PeriodID              (Accounting period identifier associated with this vendor return transaction.)

Table: FactVendorReturnDetail
Purpose: (This table contains the detail (line level) information of the Vendor Returns. Each record represents a single product line within a vendor return document, supporting detailed vendor return analysis, cost reconciliation and inventory adjustments.)
  VendorInvoiceDetailKey (Surrogate key. It's the primary key of this table.)
  VendorReturnNo         (A unique identification number of the Vendor Return used in SPARS. Links this detail line back to its parent return header in FactVendorReturn.)
  Line_No                (The sequential line number identifying this specific line within the vendor return document.)
  VendorKey              (Vendor reference key from DimVendors Table. It refers to the vendor to whom the goods on this line are being returned.)
  ProductKey             (Product reference key from DimProduct Table. It refers to the specific product (item) being returned on this line.)
  DateKey                (Date reference key from DimDate Table. It refers to the date when this return detail record was loaded into the Star Schema.)
  BaleNumber             (The bale or package identifier for this return line, used primarily for rugs or large bundled items.)
  Description            (The item description as recorded on the vendor return invoice line.)
  ItemType               (Item classification code identifying the type of item on this return line. Possible values: O = OAK Item, P = Program Item.)
  VendorStyle            (The vendor's own style code for the item being returned on this line.)
  ReturnQty              (The quantity of this product being returned to the vendor on this line.)
  Cost                   (The unit cost of the product being returned as agreed with the vendor.)
  Discount               (Discount.)
  ExtCost                (Extended cost for this return line, calculated as Cost multiplied by the return quantity.)
  TaxRate                (The tax rate percentage applied to this vendor return detail line.)
  ExtTax                 (Extended tax amount for this return line, calculated based on the TaxRate and ExtCost.)
  SKU                    (The Stock Keeping Unit identifier of the item being returned on this line.)
  PONo                   (The Purchase Order number associated with this vendor return detail line. Reference (Table FactPurchaseOrder column PurchaseOrderNo).)
  POLineNo               (Purchase Order Line Number.)
  POQty                  (Purchase Order Quantity.)
  ReceiveBin             (The warehouse bin location where the returned items are to be received or staged.)
  LotNo                  (The lot number associated with the items being returned on this line, used for traceability.)

Table: FactSalesOrders
Purpose: (This table contains the summary (header level) information of the Sales Orders. It stores all sales order transactions placed by customers, supporting order management, fulfillment tracking and sales performance analytics.)
  SalesOrderKey       (Surrogate key. It's the primary key of this table.)
  SalesOrderNo        (A unique identification number of the Sales Order used in SPARS.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer who placed this sales order.)
  WarehouseKey        (Warehouse reference key from DimWarehouse Table. It refers to the warehouse responsible for fulfilling this sales order.)
  PriceCategoryKey    (Price category reference key from DimPriceCategory Table. It refers to the pricing tier applied to this sales order.)
  PaymentTermKey      (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this sales order.)
  OrderDateKey        (Date reference key from DimDate Table. It refers to the date when this sales order was placed by the customer.)
  ShippingDateKey     (Date reference key from DimDate Table. It refers to the expected or actual shipping date of this sales order.)
  CancelDateKey       (Date reference key from DimDate Table. It refers to the date by which this sales order must be cancelled if not fulfilled.)
  SalesType           (Sales classification code identifying the type of this sales order transaction.)
  Status              (Current status of the sales order. Possible values: Open (1), Partially Paid (2), Close (0), Cancel (8), Void (9).)
  SpecialOrder        (Flag indicating whether this is a special order placed specifically for a customer rather than from regular stock. Possible values: 1 = Yes, 0 = No.)
  TotalQty            (Total quantity of all items included on this sales order.)
  TotalQtyShipped     (Total quantity of items that have been physically shipped against this sales order.)
  TotalMerchandise    (Total value of merchandise only on this sales order, excluding any service charges.)
  TotalServices       (Total value of services included on this sales order.)
  TotalAmount         (Grand total amount of this sales order including merchandise, services, tax and all charges.)
  TaxAmount           (Total tax amount applied to this sales order.)
  ServiceCharges      (Total service charges applied to this sales order.)
  ShippingCharges     (Total shipping charges applied to this sales order.)
  SalesDiscount       (Total sales discount amount applied to this sales order.)
  OpenCredit          (The remaining open credit balance on this sales order that has not yet been applied or settled.)
  PeriodID            (Accounting period identifier associated with this sales order.)
  PaymentDiscount     (Payment discount amount applicable to this sales order if paid within the discount period.)

Table: FactSalesOrderDetail
Purpose: (This table contains the detail (line level) information of the Sales Orders. Each record represents a single product line within a sales order, supporting detailed order analysis, inventory planning, fulfillment tracking and sales performance analytics.)
  SalesOrderDetailKey (Surrogate key. It's the primary key of this table.)
  SalesOrderNo        (A unique identification number of the Sales Order used in SPARS. Links this detail line back to its parent sales order header in FactSalesOrders.)
  Line_No             (Sales Order Detail Line Number.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer who placed this sales order line.)
  ProductKey          (Product reference key from DimProduct Table. It refers to the specific product (item) ordered on this sales order line.)
  WarehouseKey        (Warehouse reference key from DimWarehouse Table. It refers to the warehouse responsible for fulfilling this specific sales order line.)
  PriceCategoryKey    (Price category reference key from DimPriceCategory Table. It refers to the pricing tier applied to this specific sales order line.)
  OrderDateKey        (Date reference key from DimDate Table. It refers to the date when this sales order line was placed.)
  RequiredDateKey     (Date reference key from DimDate Table. It refers to the date by which this sales order line is required to be fulfilled by the customer.)
  ShippingDateKey     (Date reference key from DimDate Table. It refers to the expected or actual shipping date for this specific sales order line.)
  ItemType            (Item classification code identifying the type of item on this sales order detail line. Possible values: O = OAK Item, P = Program Item.)
  SKU                 (The Stock Keeping Unit identifier of the item on this sales order detail line, applicable for OAK type items.)
  OrderQty            (Total quantity of this product requested by the customer on this sales order line.)
  ToShipQty           (Remaining quantity of this product yet to be shipped against this sales order line.)
  ShippedQty          (Shipped Quantity of Sales Order.)
  Cost                (The unit cost of the product on this sales order detail line at the time the order was placed.)
  Price               (The selling price per unit of the product on this sales order detail line.)
  Discount            (Discount percentage or amount applied to this specific sales order detail line.)
  ExtPrice            (Extended price for this sales order detail line, calculated as Quantity multiplied by Unit Price after applying any discount.)
  TaxRate             (The tax rate percentage applied to this sales order detail line.)
  TaxAmount           (The total tax amount calculated and applied to this sales order detail line.)
  SQFTPrice           (Price per square foot applicable to this sales order detail line, primarily used for rugs and area-based products.)

Table: FactPackingSlips
Purpose: (This table contains the summary (header level) information of the Packing Slips. It stores all packing slip documents generated for customer shipments, supporting shipment tracking, fulfillment management and logistics analytics.)
  PackingSlipKey      (Surrogate key. It's the primary key of this table.)
  PackingSlipNo       (A unique identification number of the Packing Slip used in SPARS.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer to whom this packing slip shipment is being sent.)
  SalesOrderNo        (The Sales Order number associated with this packing slip. It links the packing slip back to the originating sales order in FactSalesOrders.)
  WarehouseKey        (Warehouse reference key from DimWarehouse Table. It refers to the warehouse from which this packing slip shipment is being dispatched.)
  DateCreatedKey      (Date reference key from DimDate Table. It refers to the date when this packing slip was created in SPARS.)
  DatePrintedKey      (Date reference key from DimDate Table. It refers to the date when this packing slip was physically printed for shipment processing.)
  SalesInvoiceNo      (The Sales Invoice number associated with this packing slip. It links the packing slip to the corresponding sales invoice in FactSalesInvoice.)
  SaleType            (Sales classification code identifying the type of sale associated with this packing slip.)
  Status              (Current status of the packing slip. Possible values: Open (1), In Shipping (2), Close (0), Void (9).)
  TotalQty            (Total quantity of all items included on this packing slip.)
  TotalBales          (Total number of bales or packages included in this packing slip shipment, primarily used for rugs and large bundled items.)
  TotalWeight         (Total weight of all items included in this packing slip shipment.)
  TotalSQFT           (Total surface area in square feet of all items included in this packing slip shipment, primarily used for rugs and area-based products.)
  TotalCuft           (Total volume in cubic feet of all items included in this packing slip shipment.)
  ShippingCharges     (Total shipping charges applied to this packing slip shipment.)
  HandlingCharges     (Total handling charges applied to processing this packing slip shipment.)
  PeriodID            (Accounting period identifier associated with this packing slip.)

Table: FactPackingSlipDetail
Purpose: (This table contains the detail (line level) information of the Packing Slips. Each record represents a single product line within a packing slip document, supporting detailed shipment analysis, product-level fulfillment tracking and logistics cost allocation analytics.)
  PackingSlipDetailKey  (Surrogate key. It's the primary key of this table.)
  PackingSlipNo         (A unique identification number of the Packing Slip used in SPARS. Links this detail line back to its parent packing slip header in FactPackingSlips.)
  Line_No               (The sequential line number identifying this specific line within the packing slip document.)
  ProductKey            (Product reference key from DimProduct Table. It refers to the specific product (item) being shipped on this packing slip detail line.)
  WarehouseKey          (Warehouse reference key from DimWarehouse Table. It refers to the warehouse from which this specific packing slip detail line is being dispatched.)
  PriceCategoryKey      (Price category reference key from DimPriceCategory Table. It refers to the pricing tier applied to this specific packing slip detail line.)
  ShippedDateKey        (Date reference key from DimDate Table. It refers to the date when the items on this packing slip detail line were physically shipped to the customer.)
  ItemType              (Item classification code identifying the type of item on this packing slip detail line. Possible values: O = OAK Item, P = Program Item.)
  Quantity              (Total quantity of this product included and shipped on this packing slip detail line.)
  Cost                  (The unit cost of the product on this packing slip detail line at the time of shipment.)
  Price                 (The selling price per unit of the product on this packing slip detail line.)
  Discount              (Discount percentage or amount applied to this specific packing slip detail line.)
  ExtPrice              (Extended price for this packing slip detail line, calculated as Quantity multiplied by Unit Price after applying any discount.)
  TaxRate               (The tax rate percentage applied to this packing slip detail line.)
  TaxAmount             (The total tax amount calculated and applied to this packing slip detail line.)
  SQFTPrice             (Price per square foot applicable to this packing slip detail line, primarily used for rugs and area-based products.)
  TrackingNo            (The shipment tracking number assigned to this packing slip detail line, used for carrier tracking and delivery confirmation.)

Table: FactVendorPackingSlips
Purpose: (This table contains the summary (header level) information of the Vendor Packing Slips. It stores all packing slip documents received from vendors against purchase orders, supporting vendor shipment tracking, goods receipt management and procurement analytics.)
  VPackingSlipKey     (Surrogate key. It's the primary key of this table.)
  VPackingSlipNo      (A unique identification number of the Vendor Packing Slip used in SPARS.)
  VendorKey           (Vendor reference key from DimVendors Table. It refers to the vendor who shipped the goods on this vendor packing slip.)
  PurchaseOrderNo     (The Purchase Order number associated with this vendor packing slip. It links the vendor packing slip back to the originating purchase order in FactPurchaseOrder.)
  DateShippedKey      (Date reference key from DimDate Table. It refers to the date when the vendor physically shipped the goods on this packing slip.)
  ArrivalDateKey      (Date reference key from DimDate Table. It refers to the expected or actual date when the vendor shipment arrived or is expected to arrive at the warehouse.)
  VPackingSlipDateKey (Date reference key from DimDate Table. It refers to the date of the vendor packing slip document as issued by the vendor.)
  TotalQuantity       (Total quantity of all items included on this vendor packing slip shipment.)
  TotalAmount         (Total monetary value of all items included on this vendor packing slip shipment.)
  Received            (Flag indicating whether the goods on this vendor packing slip have been physically received at the warehouse. Possible values: 1 = Received, 0 = Not Yet Received.)
  WarehouseKey        (Warehouse reference key from DimWarehouse Table. It refers to the destination warehouse where the vendor shipment is to be received.)
  Status              (Current status of the vendor packing slip. Possible values: Received (2), New (0).)
  PeriodID            (Accounting period identifier associated with this vendor packing slip.)

Table: FactVendorPackingSlipDetail
Purpose: (This table contains the detail (line level) information of the Vendor Packing Slips. Each record represents a single product line within a vendor packing slip document, supporting detailed vendor shipment analysis, product-level goods receipt tracking and procurement cost analytics.)
  VPackingSlipDetailKey  (Surrogate key. It's the primary key of this table.)
  VPackingSlipNo         (A unique identification number of the Vendor Packing Slip used in SPARS. Links this detail line back to its parent vendor packing slip header in FactVendorPackingSlips.)
  Line_No                (The sequential line number identifying this specific line within the vendor packing slip document.)
  ProductKey             (Product reference key from DimProduct Table. It refers to the specific product (item) being received on this vendor packing slip detail line.)
  VendorKey              (Vendor reference key from DimVendors Table. It refers to the vendor who shipped the goods on this packing slip detail line.)
  PurchaseOrderNo        (The Purchase Order number associated with this vendor packing slip detail line. It links the detail line back to the originating purchase order in FactPurchaseOrder.)
  ItemType               (Item classification code identifying the type of item on this vendor packing slip detail line. Possible values: O = OAK Item, P = Program Item.)
  SKU                    (The Stock Keeping Unit identifier of the item on this vendor packing slip detail line, applicable for OAK type items.)
  OrderQty               (The quantity of this product that was originally ordered from the vendor on the associated purchase order line.)
  ShippedQty             (The quantity of this product that was actually shipped by the vendor on this packing slip detail line.)
  Cost                   (The unit cost of the product on this vendor packing slip detail line as agreed with the vendor.)
  ExtCost                (Extended cost for this vendor packing slip detail line, calculated as the unit Cost multiplied by the shipped quantity received.)
  Discount               (Discount percentage or amount applied to this specific vendor packing slip detail line.)
  TaxRate                (The tax rate percentage applied to this vendor packing slip detail line.)
  ExtTax                 (Extended tax amount for this vendor packing slip detail line, calculated based on the TaxRate and ExtCost.)
  SQFTPrice              (Price per square foot applicable to this vendor packing slip detail line, primarily used for rugs and area-based products.)

Table: FactSalesCommission
Purpose: (This table contains the summary level information of the Sales Commissions. It stores all commission records generated for Sales Representatives based on their associated sales invoices, consignments and credit memos, supporting commission calculation, tracking and payment analytics.)
  CommissionKey          (Surrogate key. It's the primary key of this table.)
  CommissionNo           (A unique identification number of the Sales Commission record used in SPARS.)
  SalesInvoiceNo         (The Sales Invoice, Consignment or Credit Memo number associated with this commission record. Links back to the respective fact table depending on the document type.)
  SalesOrderNo           (The Sales Order number associated with this commission record. Reference (Table FactSalesOrders column SalesOrderNo).)
  SalesRepKey            (Sales Representative reference key from DimSalesRep Table. It refers to the sales representative who earned this commission.)
  CustomerIDKey          (Customer reference key from DimCustomer Table. It refers to the customer associated with the sales transaction that generated this commission.)
  PoolID                 (The commission pool identifier grouping this commission record with other related commission records for pool-based commission calculations.)
  InvoiceType            (Document type code classifying the type of sales transaction that generated this commission.)
  Status                 (Current status of this sales commission record.)
  PoolCommission         (The total commission amount calculated at the pool level before individual share distribution.)
  PoolShare              (The percentage share of the pool commission allocated to this specific sales representative.)
  CommissionRate         (The commission rate percentage applied to calculate the commission amount for this sales representative on this transaction.)
  TotalAmount            (The total sales amount of the transaction on which this commission is based.)
  AmountForCommission    (The portion of the total sales amount that is eligible and used as the base for commission calculation.)
  PaidAmount             (The commission amount that has already been paid to the sales representative for this record.)
  CDS                    (Flag indicating whether this commission record is subject to CDS (Commission Discount Structure) rules.)
  MCE                    (Flag indicating whether this commission record is subject to MCE (Minimum Commission Earnings) rules.)
  InvoiceDateKey         (Date reference key from DimDate Table. It refers to the invoice date of the sales transaction that generated this commission.)
  DateKey                (Date reference key from DimDate Table. It refers to the date when this commission record was added in SPARS.)

Table: FactCommissionInvoice
Purpose: (This table contains the summary (header level) information of the Commission Invoices. It stores all commission invoice records generated for Sales Representatives, supporting commission billing, payment tracking and accounts payable analytics for sales representative compensation.)
  CommissionInvoiceKey      (Surrogate key. It's the primary key of this table.)
  CommissionInvoiceNo       (A unique identification number of the Commission Invoice used in SPARS.)
  SalesRepKey               (Sales Representative reference key from DimSalesRep Table. It refers to the sales representative to whom this commission invoice was issued.)
  PaymentTermKey            (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this commission invoice.)
  Status                    (Current status of the commission invoice record. Possible values: Close (0), Open (1), Partially Paid (2), Void (3).)
  CommissionInvoiceRef      (The reference number or identifier associated with this commission invoice, as provided by the sales representative.)
  CommissionInvoiceDateKey  (Date reference key from DimDate Table. It refers to the date on the commission invoice document.)
  InvoiceDateKey            (Date reference key from DimDate Table. It refers to the entry date when this commission invoice was recorded into SPARS.)
  DueDateKey                (Date reference key from DimDate Table. It refers to the payment due date of this commission invoice.)
  TotalAmount               (Total amount of this commission invoice representing the total commission owed to the sales representative.)
  PaidAmount                (The commission amount that has already been paid to the sales representative against this commission invoice.)
  WarehouseKey              (Warehouse reference key from DimWarehouse Table. It refers to the warehouse associated with this commission invoice.)
  PeriodID                  (Accounting period identifier associated with this commission invoice.)

Table: FactCommissionRates
Purpose: (This table contains the summary level information of the Commission Rates. It stores all commission rate configurations assigned to Sales Representatives based on various criteria such as customer, price category, collection and other classifications, supporting commission calculation, rate management and sales representative compensation analytics.)
  CommissionRateKey   (Commission Rate Key. It's the primary key of this table.)
  SalesRepKey         (Sales Representative reference key from DimSalesRep Table. It refers to the sales representative to whom this commission rate configuration applies.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the specific customer for whom this commission rate is applicable.)
  HomeCollection      (Flag or identifier indicating whether this commission rate applies to the home collection of products. Used to differentiate commission rates between home collection and non-home collection products.)
  PricecategoryKey    (Price category reference key from DimPriceCategory Table. It refers to the pricing tier for which this commission rate configuration is applicable.)
  Commission          (The commission rate amount or percentage applicable to the sales representative for transactions matching this rate configuration.)
  CDS                 (Flag or value indicating whether this commission rate record is subject to CDS (Commission Discount Structure) rules.)
  SalesRepCompany     (The company or organization name of the sales representative associated with this commission rate.)
  MasterAgent         (Flag indicating whether this commission rate applies to a Master Agent relationship. Possible values: 1 = Master Agent, 0 = Regular Agent.)
  CollectionType      (The collection type classification for which this commission rate configuration is applicable, used to differentiate commission rates across different product collection types.)

Table: FactConsignments
Purpose: (This table contains the summary (header level) information of the Consignment Invoices. It stores all consignment transactions processed for customers, supporting consignment management, revenue tracking and sales analytics.)
  ConsignmentKey      (Surrogate key. It's the primary key of this table.)
  ConsignmentNo       (A unique identification number of the Consignment Invoice used in SPARS.)
  DateKey             (Date reference key from DimDate Table. It refers to the invoice date of this consignment document.)
  CustomerKey         (Customer reference key from DimCustomer Table. It refers to the customer associated with this consignment transaction.)
  AddressesKey        (Address reference key from DimConsignmentAddresses Table. It refers to the shipping address information associated with this consignment document.)
  Pricecategorykey    (Price category reference key from DimPriceCategory Table. It refers to the pricing tier applied to this consignment document.)
  PaymentTermKey      (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this consignment document.)
  SalesType           (Sales classification code identifying the type of this consignment transaction. Value will always be CO0 (Consignment Invoice) for all records in this table.)
  InvoiceType         (Document type code specifying the invoice category of this consignment document.)
  Status              (Current status of the consignment record. Possible values: Open (0), Partially Paid (1), Close (2), Void (9).)
  TotalQuantity       (Total quantity of all items included in this consignment document.)
  TotalAmount         (Total monetary value of this consignment including all merchandise, services and charges.)
  TaxAmount           (Total tax amount applied to this consignment document.)
  ShippingCharges     (Charges incurred for shipping and transportation of this consignment.)
  HandlingCharges     (Charges related to handling, packaging or processing of this consignment.)
  ServiceCharges      (Additional service-related fees applied to this consignment document.)
  MerchandiseAmount   (Total value of physical goods or items only in this consignment, excluding any services and additional charges.)
  ServicesAmount      (Total value of services included in this consignment document.)
  AppliedAmount       (The amount that has already been applied against this consignment document from customer payments or credits.)
  DiscountAmount      (Total discount applied to the consignment.)
  TotalWeight         (Total weight of all items included in this consignment shipment.)

Table: FactConsignmentDetail
Purpose: (This table contains the detail (line level) information of the Consignment Invoices. Each record represents a single product line within a consignment document, supporting detailed consignment analysis, product-level revenue tracking and profitability analytics.)
  SalesKey              (Surrogate key. It's the primary key of this table.)
  ConsignmentNo         (A unique identification number of the Consignment Invoice used in SPARS. Links this detail line back to its parent consignment header in FactConsignments.)
  LineNumber            (The sequential line number identifying this specific line within the consignment document.)
  DateKey               (Date reference key from DimDate Table. It refers to the invoiced date of this consignment detail line.)
  OrderDateKey          (Date reference key from DimDate Table. It refers to the original order date associated with this consignment detail line.)
  ProductKey            (Product reference key from DimProduct Table. It refers to the specific product (item) included on this consignment detail line.)
  CustomerKey           (Customer reference key from DimCustomer Table. It refers to the customer associated with this consignment detail line.)
  WarehouseKey          (Warehouse reference key from DimWarehouse Table. It refers to the warehouse from which the consigned goods on this line were dispatched.)
  ItemType              (Item classification code identifying the type of item on this consignment detail line. Possible values: O = OAK Item, P = Program Item.)
  Quantity              (Total quantity of this product included on this consignment detail line.)
  UnitPrice             (The selling price per unit of the product on this consignment detail line.)
  UnitCost              (The cost per unit of the product on this consignment detail line at the time of consignment.)
  DiscountAmount        (Discount percentage or amount applied to this specific consignment detail line.)
  SalesAmount           (Total sales amount for this consignment detail line, calculated as Quantity multiplied by Unit Price.)
  TaxAmount             (Tax amount applied to this consignment detail line.)
  ShippingCharges       (Shipping cost allocated to this specific consignment detail line.)
  ProfitAmount          (Net profit earned on this consignment detail line, calculated as the extended sales price minus the total cost of the consigned quantity.)

Table: FactAccountMonthlySummary
Purpose: (This table contains the summary level information of the General Ledger Account Monthly Balances. It stores monthly period-level financial summaries for each GL account, supporting financial reporting, period-over-period analysis, balance sheet and profit & loss statement analytics.)
  AccountMonthlyKey   (Surrogate key. It's the primary key of this table.)
  GLAccountKey        (General Ledger account reference key from DimGLAccounts Table. It refers to the GL account for which this monthly summary is recorded.)
  DateKey             (Date reference key from DimDate Table. It refers to the period start date of this monthly summary record.)
  AccountID           (The business-level natural key or account code of the GL account as used in SPARS.)
  Description         (The name or descriptive title of the GL account for this monthly summary record.)
  PeriodStartDate     (The starting date of the accounting period covered by this monthly summary record.)
  OpeningBalance      (The balance of the GL account at the beginning of this accounting period, before any transactions are applied. NULL values are treated as zero.)
  PTD_Debit           (Total debit transaction amounts posted to this GL account during the current accounting period (Period-To-Date).)
  PTD_Credit          (Total credit transaction amounts posted to this GL account during the current accounting period (Period-To-Date).)
  PTD_Net             (Net movement of this GL account during the current accounting period, calculated as the difference between period debits and credits (Period-To-Date).)
  YTD_Debit           (Cumulative total debit transaction amounts posted to this GL account from the start of the fiscal year up to and including the current period (Year-To-Date).)
  YTD_Credit          (Cumulative total credit transaction amounts posted to this GL account from the start of the fiscal year up to and including the current period (Year-To-Date).)
  YTD_Net             (Cumulative net movement of this GL account from the start of the fiscal year up to and including the current period, calculated as the difference between year-to-date debits and credits.)
  ClosingBalance      (The ending balance of the GL account at the close of this accounting period. Derived during load as Opening Balance plus the net period movement.)



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
          QUERY GUIDELINES  (SALES TEAM ROLE)
================================================================
This user has the SALES TEAM role.
Allowed scope: sales analysis, customer analytics, inventory monitoring,
pricing, and back-order information.
Do NOT generate profitability / margin / cost-only financial analytics.

================================================================
  METRIC DEFINITIONS (CRITICAL)
================================================================
- NEVER use TotalAmount for "sales" or "revenue".
  TotalAmount = MerchandiseAmount + TaxAmount + ShippingCharges + HandlingCharges + ServiceCharges.
- Use TotalAmount only when user explicitly asks for "total invoice amount"
  or "total amount including everything".
- "Net Quantity Sold" = SUM(FSD.Quantity - ISNULL(FCMD.Quantity, 0))
  using FactSalesDetail and FactCreditMemoDetail.
- "Invoice Count" = COUNT(*) from FactSalesInvoice with void/cancelled excluded.
- "Customer Count" / "Vendor Count" = COUNT with Status filter (see DEFAULT FILTERS).

================================================================
  DEFAULT FILTERS (MANDATORY)
================================================================
FactSalesInvoice:
  Exclude void/cancelled/reversed invoices in totals:
  WHERE FSI.Status NOT IN ('Void','Cancelled','Reversed')
  Include status values only when user asks for by-status breakdowns.
DimCustomer:
  For counts: WHERE DC.Status = 'Active'
  For revenue analysis: include all customers.
DimWarehouse:
  WHERE DW.IsActive = 1 when listing/counting active warehouses.
  For historical sales analysis, include all warehouses.
DimProduct:
  WHERE DP.IsDiscontinued = 0 for product analysis (unless user asks about discontinued).
  NOTE: DimProduct.Status values are not reliably populated.
  Do NOT filter on DP.Status = 'Active' — this returns 0 rows.
SalesType:
  Actual values are 'SO0' (Sales) and 'CS0' (Sales from Consignment).
  Do NOT filter on SalesType by default.
NULL grouping:
  Add WHERE grouped_column IS NOT NULL unless user requests NULLs.
Bottom/lower/minimum requests:
  ensure at least one record OR amount > 0.

================================================================
  ANTI-PATTERNS (STRICTLY FORBIDDEN)
================================================================
AP1:
  NEVER JOIN FactSalesInvoice WITH FactSalesDetail in the same aggregation query.
  Each invoice has multiple detail lines; joining causes fan-out and inflated totals.
  Use ONE table per query:
    - FactSalesInvoice for invoice-level metrics (revenue, tax, discount totals, invoice count)
    - FactSalesDetail for product/line analysis
  Return a maximum of 40 rows.
  Round currency/decimal values to 2 decimals.
AP2:
  NEVER use TotalAmount for "sales" or "revenue".
  Use MerchandiseAmount (FactSalesInvoice) or SalesAmount (FactSalesDetail).
AP3:
  FactSalesDetail has Quantity and ReturnQuantity; do not rely on ReturnQuantity alone.
  Net sold quantity = SUM(FSD.Quantity - ISNULL(FCMD.Quantity, 0))
AP4:
  NEVER use DateKey on FactInventorySnapshot (column does not exist).
AP5:
  NEVER use >= YEAR(GETDATE())-N for "last N years".
  Use BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE()).
AP6:
  Do not query wrong fact table for a domain.
  Credit memos -> FactCreditMemo / FactCreditMemoDetail.
AP7:
  NEVER omit status filters when computing totals.
AP8:
  Table name accuracy: FactVendorPayments (with 's'), FactVendorInvoices (with 's').

================================================================
  CONSISTENCY RULES
================================================================
- Same type of question => same table + same metric column.
- "Total sales by quarter" => VW_SalesMonthly.MerchandiseRevenue
  or FactSalesInvoice.MerchandiseAmount.
- "Top customers by revenue" => FactSalesInvoice.MerchandiseAmount.
- "Top products by sales" => FactSalesDetail.SalesAmount.

================================================================
  GENERAL RULES
================================================================
0) ROW LIMITS:
  - Every SELECT against a fact table MUST include TOP 40. No exceptions.
  - Default: TOP 40. This is also the MAXIMUM — never exceed TOP 40 regardless of what the user asks.
  - "top 10" => TOP 10. "top 5" => TOP 5. "show all" => TOP 40.
  - If user requests more than 40 rows, cap it at TOP 40 silently.
  - GROUP BY queries (per-customer, per-product breakdowns, etc.) MUST use TOP 40 — they can return thousands of rows.
  - ONLY exception: a query that returns exactly ONE row (e.g. SELECT SUM(...) with no GROUP BY, SELECT COUNT(*) with no GROUP BY) does not need TOP.
  - Never query FactSalesDetail or FactSalesInvoice raw without TOP.
1) Prefer views/header tables for speed:
  - Monthly/quarterly/yearly totals and invoice counts -> VW_SalesMonthly
  - Warehouse-level sales -> VW_SalesByWarehouse
  - Customer-level revenue -> FactSalesInvoice + DimCustomer
  - Use FactSalesDetail only for product-level/line-level detail.
2) Generate exactly one SELECT (or WITH ... SELECT) per query.
3) Do not use DECLARE/T-SQL variables.
4) Avoid schema-qualified names (dbo.) unless required.

================================================================
  TIME / DATE RULES
================================================================
- For time filtering, join DimDate on DateKey.
- Current period: YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
- Last N years: DD.Year BETWEEN YEAR(GETDATE())-N AND YEAR(GETDATE()).
- Last N months:
  DD.FullDate >= DATEADD(MONTH, -N, GETDATE()) AND DD.FullDate <= GETDATE().
- Monthly sort for window functions:
  ORDER BY (DD.Year * 100 + DD.Month), never (DD.Year, DD.Month) separately.

================================================================
  TABLE RELATIONSHIP RULES
================================================================
- Credit memos:
  FactCreditMemo (header) + FactCreditMemoDetail (lines) via CreditMemoNo.
- Customer payment application:
  FactCustomerApplication + FactCustomerPayment via CashReceiptNo.
- Back-order history:
  DimSalesOrderDetail_Log filtered on BackOrder column.
- Customer debit analysis:
  FactCustomerDebit + DimCustomer via CustomerKey.

================================================================
  SQL QUALITY RULES (CRITICAL)
================================================================
- NULL-safe exclusions: use LEFT JOIN ... IS NULL; avoid NOT IN (subquery).
- For growth/trend/comparison, use LAG/LEAD with absolute and % change.
- Product analysis: exclude discontinued, cross-check inventory.
- FactInventorySnapshot has NO DateKey.
  AvailableQty = QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0)
- For "current" questions, use ROW_NUMBER() to isolate latest per entity.
- ORDER BY the metric the user is specifically asking about, not by an unrelated metric.
  Example: user asks "breakup of discount by customer" → ORDER BY SUM(DiscountAmount) DESC, NOT by SalesAmount.
  Example: user asks "top customers by revenue" → ORDER BY SUM(MerchandiseAmount) DESC.
  NEVER default to ordering by revenue/sales when the user is asking about a different metric.
- ZERO-VALUE FILTERING: When the user asks for a breakdown of a specific metric (discount, returns, etc.),
  ALWAYS add HAVING SUM(metric) > 0 to exclude records where that metric is zero.
- CASE-BASED GROUPING (CRITICAL): When the user asks to "group logically" or "categorize", use a TWO-STEP CTE:
    WITH UniqueValues AS (
        SELECT col, SUM(metric) AS TotalMetric FROM Table WHERE col IS NOT NULL GROUP BY col
    )
    SELECT TOP N
        CASE WHEN col LIKE '%X%' THEN 'Group A' ELSE 'Other' END AS LogicalGroup,
        SUM(TotalMetric) AS Total
    FROM UniqueValues
    GROUP BY CASE WHEN col LIKE '%X%' THEN 'Group A' ELSE 'Other' END
    HAVING SUM(TotalMetric) > 0
    ORDER BY Total DESC
  NEVER include the raw source column in the outer GROUP BY or SELECT — that produces one row per raw value.
  Example: "breakup of discount by customers" → HAVING SUM(FSI.DiscountAmount) > 0
- Add minimum volume thresholds for trend analysis.
- Include rank in top-N outputs.

================================================================
      FEW-SHOT EXAMPLES (FOLLOW EXACT PATTERN)
================================================================

--- Example 1: Quarterly sales (MerchandiseAmount + status filter) ---
Question: "What is total sales of 2025 by quarter?"
SELECT
  DD.Quarter,
  SUM(FSI.MerchandiseAmount) AS SalesRevenue,
  SUM(FSI.TaxAmount) AS TaxCollected,
  SUM(FSI.DiscountAmount) AS DiscountsGiven,
  COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year = 2025
  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
GROUP BY DD.Quarter
ORDER BY DD.Quarter

--- Example 2: Top products by quantity (detail table) ---
Question: "Top 10 products by quantity sold"
SELECT TOP 10
  ROW_NUMBER() OVER (ORDER BY SUM(FSD.Quantity - ISNULL(FCMD.Quantity,0)) DESC) AS Rank,
  DP.ItemID,
  DP.ItemName,
  DP.Category,
  SUM(FSD.Quantity - ISNULL(FCMD.Quantity,0)) AS NetQuantitySold,
  SUM(FSD.SalesAmount) AS TotalSalesAmount,
  SUM(FSD.ProfitAmount) AS TotalProfit
FROM FactSalesDetail FSD
JOIN DimProduct DP ON FSD.ProductKey = DP.ProductKey
LEFT JOIN FactCreditMemoDetail FCMD ON FSD.ProductKey = FCMD.ProductKey
WHERE DP.IsDiscontinued = 0
GROUP BY DP.ItemID, DP.ItemName, DP.Category
ORDER BY NetQuantitySold DESC

--- Example 3: Inventory stock on hand (no DateKey in snapshot) ---
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

--- Example 4: Active customer count ---
Question: "How many customers do we have?"
SELECT COUNT(*) AS ActiveCustomerCount
FROM DimCustomer DC
WHERE DC.Status = 'Active'

--- Example 5: Business summary (header table only; no fan-out) ---
Question: "Summary: total revenue, tax, customer count, invoice count for 2025"
SELECT
  SUM(FSI.MerchandiseAmount) AS TotalRevenue,
  SUM(FSI.TaxAmount) AS TotalTax,
  SUM(FSI.DiscountAmount) AS TotalDiscount,
  COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount,
  COUNT(DISTINCT FSI.CustomerKey) AS UniqueCustomers
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year = 2025
  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')

--- Example 6: Dead stock (no DateKey in snapshot) ---
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
  SUM(FIS.QuantityOnHand) AS TotalQtyOnHand,
  SUM(FIS.InventoryValue) AS TotalInventoryValue,
  AVG(FIS.AverageCost) AS AvgCost,
  COUNT(DISTINCT FIS.BranchKey) AS WarehouseCount
FROM FactInventorySnapshot FIS
JOIN DimProduct DP ON FIS.ProductKey = DP.ProductKey
LEFT JOIN RecentSales RS ON FIS.ProductKey = RS.ProductKey
WHERE RS.ProductKey IS NULL
  AND FIS.QuantityOnHand > 0
  AND DP.IsDiscontinued = 0
GROUP BY DP.ItemID, DP.ItemName, DP.Category, DP.Brand
ORDER BY TotalInventoryValue DESC

--- Example 7: Last 3 years sales (BETWEEN excludes future) ---
Question: "Total sales by year for last 3 years"
SELECT
  DD.Year,
  SUM(FSI.MerchandiseAmount) AS SalesRevenue,
  COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE DD.Year BETWEEN YEAR(GETDATE())-3 AND YEAR(GETDATE())
  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
GROUP BY DD.Year
ORDER BY DD.Year

--- Example 8: Customer retention by region (two-year cohort) ---
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
  COUNT(DISTINCT Y1.CustomerKey) AS Year1_Customers,
  COUNT(DISTINCT Y2.CustomerKey) AS Year2_Customers,
  COUNT(DISTINCT CASE WHEN Y2.CustomerKey IS NOT NULL THEN Y1.CustomerKey END) AS Retained,
  ROUND(
    100.0 * COUNT(DISTINCT CASE WHEN Y2.CustomerKey IS NOT NULL THEN Y1.CustomerKey END)
    / NULLIF(COUNT(DISTINCT Y1.CustomerKey), 0),
    2
  ) AS RetentionRatePct
FROM Year1 Y1
LEFT JOIN Year2 Y2 ON Y1.CustomerKey = Y2.CustomerKey AND Y1.Region = Y2.Region
GROUP BY Y1.Region
ORDER BY RetentionRatePct DESC

--- Example 9: Monthly sales comparison by region ---
Question: "Compare sales performance between NORTHEAST and WESTERN regions by month over past 2 years"
SELECT
  DC.Region,
  DD.Year,
  DD.Month,
  DD.MonthName,
  SUM(FSI.MerchandiseAmount) AS Revenue,
  COUNT(DISTINCT FSI.SalesInvoiceNo) AS InvoiceCount,
  COUNT(DISTINCT FSI.CustomerKey) AS ActiveCustomers
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
WHERE DD.Year BETWEEN YEAR(GETDATE())-2 AND YEAR(GETDATE())-1
  AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
  AND DC.Region IS NOT NULL
  AND DC.Region IN ('NORTHEAST', 'WESTERN')
GROUP BY DC.Region, DD.Year, DD.Month, DD.MonthName
ORDER BY DC.Region, DD.Year * 100 + DD.Month
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
