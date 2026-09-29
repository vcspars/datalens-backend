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
    DW.WarehouseName,
    DW.City AS WarehouseCity,
    DW.State AS WarehouseState,
    DD.Year,
    DD.MonthName,
    COUNT(DISTINCT FSD.SalesInvoiceNo) AS TotalOrders,
    SUM(FSD.Quantity) AS TotalQuantitySold,
    SUM(FSD.SalesAmount) AS TotalSalesAmount,
    SUM(FSD.ProfitAmount) AS TotalProfit,
    SUM(ISNULL(FSD.ShippingCharges,0)) AS TotalShipping
FROM FactSalesDetail FSD
LEFT JOIN DimWarehouse DW ON FSD.WarehouseKey = DW.WarehouseKey
LEFT JOIN DimDate DD ON FSD.DateKey = DD.DateKey
GROUP BY DW.WarehouseID, DW.WarehouseName, DW.City, DW.State, DD.Year, DD.MonthName;

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
  Status              (Current account status of the customer. Possible values: Active, Sales Hold, Credit Hold.)
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
  Status              (Status of the vendor. Possible values: Active, Purchase Hold, Payment Hold.)
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
  CreditCardTerms     (It's a Flag for credit card terms. It has only value only [0 and 1]. If this flag will be enabled (1), then this payment term will be used for Credit Card payments as well. Otherwise if it will be disabled (0), then the respective payment term record will not be used for credit card payments.)

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
  Status                (VARCHAR. Current invoice status. Actual stored string values: 'Open', 'Close', 'Partially Paid', 'Void'. ALWAYS filter using string literals e.g. <> 'Void' — NEVER use integer codes.)
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
  Status                   (VARCHAR. Current status of the credit memo. Actual stored string values: 'Open', 'Partially Paid', 'Close', 'Void'. ALWAYS filter using string literals e.g. <> 'Void' — NEVER use integer codes.)
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
  Status                  (Current status of this debit or credit adjustment record. Possible values: Open, Partially Paid, Close, Void.)
  InvoiceType             (Internal document type code classifying the nature of this adjustment.)
  SalesType               (Sales classification code identifying the type of sale associated with this adjustment (e.g., SO = Sales Order).)

Table: FactVendorReturn
Purpose: (This table contains the summary (header level) information of Vendor Returns. It stores all return transactions initiated against vendors for goods being sent back, supporting procurement, accounts payable and vendor relationship analytics.)
  VendorReturnKey       (Surrogate key. It's the primary key of this table.)
  VendorReturnNo        (A unique identification number of the Vendor Return used in SPARS.)
  VendorKey             (Vendor reference key from DimVendors Table. It refers to the vendor to whom the goods are being returned.)
  PaymentTermKey        (Payment term reference key from DimPaymentTerms Table. It refers to the payment terms applicable to this vendor return transaction.)
  InvoiceType           (Code classifying the type of this vendor return document. Value will always be D (Debit Memo / Vendor Return) for all records in this table.)
  Status                (Current status of the vendor return record. Possible values: Close, Approved, Partially Paid, Void.)
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
  ShippingDateKey     (Date reference key from DimDate Table. IMPORTANT: stores the ACTUAL ship date — only populated AFTER an order is physically shipped. It is NULL for open/unshipped orders. Do NOT use this to filter for "orders due to ship today" or "orders ready to ship". For due/overdue shipment queries use RequiredDateKey from FactSalesOrderDetail instead.)
  CancelDateKey       (Date reference key from DimDate Table. It refers to the date by which this sales order must be cancelled if not fulfilled.)
  SalesType           (Sales classification code identifying the type of this sales order transaction.)
  Status              (VARCHAR. Current status of the sales order. Actual stored string values: 'Open', 'Close', 'Cancel', 'Void', 'Partially Paid'. ALWAYS filter using string literals e.g. NOT IN ('Cancel', 'Void') — NEVER use integer codes.)
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
  Status              (Current status of the packing slip. Possible values: Open , In Shipping, Close , Void .)
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
  Status              (Current status of the vendor packing slip. Possible values: Received, New.)
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
  Status                    (Current status of the commission invoice record. Possible values: Close, Open, Partially Paid, Void.)
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
  Status              (Current status of the consignment record. Possible values: Open, Partially Paid, Close, Void.)
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
o	NEVER use >= YEAR(GETDATE())-N for "last N years" — it includes future data.
o	"Last N years" means exactly N calendar years including the current year.
    Formula: WHERE DD.Year BETWEEN YEAR(GETDATE())-(N-1) AND YEAR(GETDATE())
    Examples:
      "last 3 years"  → BETWEEN YEAR(GETDATE())-2 AND YEAR(GETDATE())   (e.g. 2023,2024,2025)
      "last 5 years"  → BETWEEN YEAR(GETDATE())-4 AND YEAR(GETDATE())   (e.g. 2021,2022,2023,2024,2025)
      "last 10 years" → BETWEEN YEAR(GETDATE())-9 AND YEAR(GETDATE())
    NEVER write YEAR(GETDATE())-N directly for "last N years" — that gives N+1 years.

AP6: 
o	NEVER query the wrong fact table for a domain:
o	Vendor returns → FactVendorReturn / FactVendorReturnDetail (NOT DimVendors)
o	Customer returns → FactCustomerReturn / FactCustomerReturnDetail
o	Credit memos → FactCreditMemo / FactCreditMemoDetail

AP7: 
o	NEVER omit Status filters when computing totals (see DEFAULT FILTERS above).

AP8: 
o	Table name accuracy: FactVendorPayments (with 's'), FactVendorInvoices (with 's').

AP9 — CRITICAL: NEVER JOIN TWO FACT TABLES TO THE SAME DIMENSION IN ONE CTE.
o	Joining FactSalesInvoice AND FactCustomerPayment to DimCustomer in the same CTE
    causes a CARTESIAN EXPLOSION: every invoice row × every payment row per customer.
    A customer with 1,000 invoices and 200 payments = 200,000 rows before MAX() collapses them.
    With millions of rows across all customers this query will run for hours or time out.
o	MANDATORY PATTERN for any query that needs activity from multiple fact tables per entity:
    Step 1 — One CTE per fact table, GROUP BY the key column first:
        SalesActivity AS (
            SELECT CustomerKey, MAX(DD.FullDate) AS LastSaleDate
            FROM FactSalesInvoice FSI
            JOIN DimDate DD ON FSI.DateKey = DD.DateKey
            WHERE FSI.Status NOT IN ('Void','Cancelled','Reversed')
            GROUP BY CustomerKey
        ),
        PaymentActivity AS (
            SELECT CustomerKey, MAX(DD.FullDate) AS LastPaymentDate
            FROM FactCustomerPayment FCP
            JOIN DimDate DD ON FCP.PaymentDateKey = DD.DateKey
            GROUP BY CustomerKey
        )
    Step 2 — Join the pre-aggregated CTEs to the dimension:
        SELECT DC.CustomerKey, SA.LastSaleDate, PA.LastPaymentDate
        FROM DimCustomer DC
        LEFT JOIN SalesActivity   SA ON DC.CustomerKey = SA.CustomerKey
        LEFT JOIN PaymentActivity PA ON DC.CustomerKey = PA.CustomerKey
o	This rule applies to ANY entity (Customer, Vendor, Product, Warehouse) and
    ANY combination of fact tables (invoices + payments, invoices + returns, sales + credit memos, etc.).
o	NEVER collapse two fact-table joins into one CTE. Always one CTE per fact table.

AP10 — NEVER REFERENCE A CTE COMPUTED COLUMN IN ORDER BY WITHOUT REPEATING THE EXPRESSION.
o	SQL Server does not allow ORDER BY to reference a column alias computed in a CTE or sub-query
    that is not present in the outer GROUP BY.
o	WRONG:  ORDER BY LastActivityDate            ← alias from inner CTE, not in outer GROUP BY
o	CORRECT: Repeat the full CASE expression in ORDER BY, or add a numeric sort column:
            ORDER BY CASE WHEN ... THEN 1 WHEN ... THEN 2 ELSE 3 END

AP11 — NEVER SELECT SURROGATE KEYS OR INTERNAL ID COLUMNS IN THE FINAL OUTPUT.
o	Columns ending in 'Key' (CustomerKey, ProductKey, DateKey, VendorKey, WarehouseKey,
    PriceCategoryKey, RegionKey, PaymentTermKey, BillOfLadingKey, RugKey, AddressesKey, etc.)
    are internal database surrogate integers — they are meaningless to a business user.
o	These columns MAY ONLY be used internally for JOINs, GROUP BY, or WHERE clauses.
o	NEVER include any *Key column in the final SELECT list that is shown to the user.
o	WRONG:  SELECT DC.CustomerKey, DC.CustomerName, SUM(FSI.MerchandiseAmount) AS Revenue ...
o	CORRECT: SELECT DC.CustomerName, SUM(FSI.MerchandiseAmount) AS Revenue ...
o	This applies to ALL surrogate/foreign keys across ALL tables regardless of the query type.
o	Exception: Only include a Key column if the user EXPLICITLY asks for it
    (e.g. "show me the customer key/ID", "include the product key").

AP12 — NEVER JOIN FactSalesOrders DIRECTLY TO FactSalesOrderDetail FOR HEADER-LEVEL QUERIES.
o	FactSalesOrders is the ORDER HEADER (one row per order).
    FactSalesOrderDetail is the ORDER DETAIL (many rows per order — one per product line).
    Joining them directly causes the same fan-out explosion as AP1:
    an order with 20 lines becomes 20 rows, multiplied across thousands of orders = millions of rows.
o	FactSalesOrders already contains header-level totals: TotalQty, TotalQtyShipped,
    TotalMerchandise, TotalAmount, Status, ShippingDateKey — use these for order-level queries.
o	Only join FactSalesOrderDetail when you SPECIFICALLY need line-level product detail
    (e.g. "show each product line on the order", "which items are on backorder per order").
o	If you need a date from FactSalesOrderDetail (e.g. RequiredDate) for a header-level query,
    PRE-AGGREGATE it in a CTE first (one row per SalesOrderNo), then join the CTE:
    CORRECT:
        RequiredDates AS (
            SELECT FSOD.SalesOrderNo, MIN(DD.FullDate) AS MinRequiredDate
            FROM   FactSalesOrderDetail FSOD
            JOIN   DimDate DD ON FSOD.RequiredDateKey = DD.DateKey
            GROUP BY FSOD.SalesOrderNo
        )
        ...
        LEFT JOIN RequiredDates RD ON FSO.SalesOrderNo = RD.SalesOrderNo
    WRONG: LEFT JOIN FactSalesOrderDetail FSOD ON FSO.SalesOrderNo = FSOD.SalesOrderNo
o	STATUS REMINDER: FactSalesOrders.Status is VARCHAR — always use NOT IN ('Cancel', 'Void'),
    NEVER integer codes.
o	SHIPPING DATE REMINDER: FactSalesOrders.ShippingDateKey is the ACTUAL (post-shipment) date.
    For "orders due to ship / can ship today" queries, filter on RequiredDateKey from
    FactSalesOrderDetail (via pre-aggregated CTE), not on ShippingDateKey.
    Pattern: WHERE RD.MinRequiredDate <= CAST(GETDATE() AS DATE)
             AND FSO.TotalQty > ISNULL(FSO.TotalQtyShipped, 0)

================================================================
  QUERY PERFORMANCE RULES  (prevent long-running / timed-out queries)
================================================================
These rules must be applied to EVERY query. A slow query that times out is worse than no answer.

PERF1 — PRE-AGGREGATE EACH FACT TABLE IN ITS OWN CTE BEFORE JOINING (aggregation/summary queries only).
  When the goal is to compute a summary metric per entity (e.g. last activity date, total spend,
  total payments per customer), never join two or more fact tables to the same dimension in a
  single FROM/JOIN block. Reduce each fact table to one row per key in its own CTE first, then
  join the pre-aggregated CTEs to the dimension.
  This rule applies to aggregation/summary queries. It does NOT apply to row-level detail queries
  where you need individual matching rows from two tables (e.g. "show each invoice with its
  payment", "list all credit memos with their original invoice").

PERF2 — NEVER USE SELECT * OR RETRIEVE ALL COLUMNS FROM LARGE TABLES.
  FactSalesDetail (3.4M rows), FactSalesInvoice (1M+ rows), FactCustomerPayment, FactCreditMemo
  are all large tables. Always project only the columns you need and always apply TOP N.

PERF3 — FILTER EARLY, NOT LATE.
  Apply date filters, Status filters, and WHERE clauses inside CTEs (as close to the table scan
  as possible), never only in the outermost SELECT. This lets SQL Server use index seeks.
  GOOD: CTE with WHERE DD.Year = 2025  →  small intermediate result
  BAD:  Join everything then WHERE Year = 2025 in the outer SELECT  →  full table scan

PERF4 — PREFER DATEADD RANGE COMPARISONS OVER DATEDIFF FOR DATE FILTERING.
  When filtering rows by a date range, prefer range comparisons over DATEDIFF where both
  approaches give the same result — range comparisons are SARG-able (index-friendly):
    PREFER:  col >= DATEADD(MONTH, -12, GETDATE())
    AVOID:   DATEDIFF(MONTH, col, GETDATE()) <= 12  (scans every row, cannot use index)
  DATEDIFF is still acceptable when you genuinely need an exact month-count value in a
  SELECT or CASE expression (e.g. computing "X months overdue" as a display column).
  Do not change existing working DATEDIFF logic unless rewriting the query from scratch.

PERF5 — AVOID CORRELATED SUB-QUERIES INSIDE SELECT OR WHERE.
  A sub-query like SELECT (SELECT MAX(...) FROM Fact WHERE key = outer.key) runs once per row.
  Replace with a pre-aggregated CTE joined once.

PERF6 — LIMIT SCHEMA INSPECTION CALLS.
  Do not call sql_db_schema repeatedly for tables whose schema you already know from
  the current conversation or from the DB knowledge provided in this prompt.
  Look up schema only when you genuinely need an unfamiliar table.

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
Financial statement rules (Critical)
================================================================

SOURCE TABLES FOR FINANCIAL STATEMENTS:
- FactAccountMonthlySummary  — stores monthly GL account balances. Join on AccountID to COAMaping.
- COAMaping                  — Chart of Account mapping. Provides grouping columns for reporting.
- DimDate                    — Join FactAccountMonthlySummary.DateKey to DimDate.DateKey for period filtering.

JOIN PATTERN (always use this):
  FROM FactAccountMonthlySummary FAM
  JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
  JOIN DimDate DD ON FAM.DateKey = DD.DateKey

BALANCE SHEET — VERIFIED column mapping (confirmed by live DB test):
- Amount column  : ClosingBalance from FactAccountMonthlySummary.
- Sign rule      : CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
  (Main >= 2000 = Liabilities & Equity accounts — flip sign for correct BS presentation)

CRITICAL — column-to-template level mapping (verified against live data):
  BalanceSheet_MainGroups  → line items inside "Main Grouped" template (Current Assets, Non Current Assets, Current Liabilities, Non Current Liabilities, Equity, Retained Earnings, Contribution, Distributions, Profit & Loss)
  BalanceSheet_SubGroups   → line items inside "Sub Grouped" template (Accounts Receivable, Cash and Cash Equivalents, Accounts Payable, Short Term Loans, etc.)
  BalanceSheet_Details     → line items inside "Detailed" template (individual account names, e.g. ACCOUNT RECEIVABLE, PETTY CASH, ACCOUNT PAYABLE-VENDOR, etc.)

- Main Grouped   : Derived group (Assets/L&E) as section header + BalanceSheet_MainGroups as line items within each section.
    SELECT derived_main_group AS [Section], CM.BalanceSheet_MainGroups AS [Line Item], SUM(amount)
    GROUP BY derived_main_group, CM.BalanceSheet_MainGroups
    Filter: AND CM.BalanceSheet_MainGroups IS NOT NULL AND LEN(CM.BalanceSheet_MainGroups) > 0
    → Returns rows like: Assets | Current Assets | 15,523,012.25

- Sub Grouped    : Derived group + BalanceSheet_MainGroups (section header) + BalanceSheet_SubGroups (line items):
    SELECT derived_main_group AS [Section], CM.BalanceSheet_MainGroups AS [Sub Group], CM.BalanceSheet_SubGroups AS [Line Item], SUM(amount)
    GROUP BY derived_main_group, CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups
    Filter: AND CM.BalanceSheet_SubGroups IS NOT NULL AND LEN(CM.BalanceSheet_SubGroups) > 0
    → Returns rows like: Assets | Current Assets | Accounts Receivable | 3,774,607.91

- Detailed       : Derived group + BalanceSheet_MainGroups + BalanceSheet_SubGroups + BalanceSheet_Details (individual accounts):
    SELECT derived_main_group AS [Section], CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups, CM.BalanceSheet_Details, SUM(amount)
    GROUP BY derived_main_group, CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups, CM.BalanceSheet_Details
    Filter: AND CM.BalanceSheet_Details IS NOT NULL AND LEN(CM.BalanceSheet_Details) > 0

P&L STATEMENT — VERIFIED column mapping (confirmed by live DB test):
- Amount column  : PTD_Net from FactAccountMonthlySummary, multiplied by -1.
- Expression     : SUM(FAM.PTD_Net * -1) AS [Amount]
  NEVER use YTD_Net for P&L — always use PTD_Net.

- Main Grouped   : GROUP BY CM.PLStatementMainGroups → returns [Group, Amount], 6 possible rows:
    Sales, Cost Of Goods Sold, Operating Expenses, Other Income/Expenses, Interest Expenses, Taxes
    Filter: AND CM.PLStatementMainGroups IS NOT NULL AND LEN(CM.PLStatementMainGroups) > 0

- Sub Grouped    : GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups → returns [Main Group, Sub Group, Amount]
    Filter: AND CM.PLStatementSubGroups IS NOT NULL AND LEN(CM.PLStatementSubGroups) > 0

- Detailed       : GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups, CM.PLStatementDetails → returns [Main Group, Sub Group, Account, Amount]
    Filter: AND CM.PLStatementDetails IS NOT NULL AND LEN(CM.PLStatementDetails) > 0

COMPUTED P&L LINES (NOT from DB — derive from query results and insert into the formatted output):
  Gross Profit/(Loss)     = Sales amount + Cost Of Goods Sold amount  (COGS is stored as negative)
  Operating Profit/(Loss) = Gross Profit/(Loss) + Operating Expenses amount  (expenses stored as negative)
  Net Profit/(Loss)       = Operating Profit/(Loss) + Other Income/Expenses + Interest Expenses + Taxes
                            (all expense groups stored as negative; add all values directly)
  If a group has no data for the period, treat its amount as 0.00.
  For Sub Grouped / Detailed: compute section totals as SUM of all line items in that section.

PERIOD FILTERING:
- For a specific year+month  : WHERE DD.Year = [year] AND DD.Month = [month]
- For a full year (YTD)      : WHERE DD.Year = [year]
- For current period         : WHERE DD.Year = YEAR(GETDATE()) AND DD.Month = MONTH(GETDATE())
- Always filter out NULL grouping columns: AND CM.BalanceSheet_MainGroups IS NOT NULL (or PLStatementMainGroups)

NO TOP LIMIT on financial statements — always return ALL rows (no TOP N).


================================================================
  TIME / DATE RULES
================================================================
- For time-based filtering: JOIN to DimDate on DateKey and filter on Year, Month, Quarter, MonthName.
- For current period: use YEAR(GETDATE()), MONTH(GETDATE()), DATEPART(QUARTER, GETDATE()).
- For last N years: WHERE DD.Year BETWEEN YEAR(GETDATE())-(N-1) AND YEAR(GETDATE()).
   "Last N years" = N calendar years INCLUDING the current year.
   Examples: last 5 years → BETWEEN YEAR(GETDATE())-4 AND YEAR(GETDATE())
             last 3 years → BETWEEN YEAR(GETDATE())-2 AND YEAR(GETDATE())
   NEVER use YEAR(GETDATE())-N for "last N years" — that gives N+1 years total.
   NOT >= YEAR(GETDATE())-N which includes future data.
- For last N months: WHERE DD.FullDate >= DATEADD(MONTH, -N, GETDATE()) AND DD.FullDate <= GETDATE().
- CRITICAL — LAG/LEAD/ROW_NUMBER monthly sort: ORDER BY (Year * 100 + Month), never (Year, Month) separately.
- CRITICAL — "LATEST AVAILABLE MONTH" = previous calendar month (DATEADD(MONTH,-1,GETDATE())):
  The current calendar month is almost always incomplete (data still coming in).
  When user says "latest available month", "most recent month", or "last complete month",
  use DATEADD(MONTH, -1, GETDATE()) to target the previous full month — NOT MONTH(GETDATE()).
  This resolves to a scalar constant so SQL Server can use index seeks (fast).
  Pattern:
    AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
    AND DD.Year  = YEAR(DATEADD(MONTH, -1, GETDATE()))
  For YoY comparison add both years:
    AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
    AND DD.Year IN (YEAR(DATEADD(MONTH,-1,GETDATE())), YEAR(DATEADD(MONTH,-1,GETDATE()))-1)
  NEVER use a CTE cross-join (JOIN ON 1=1) to pass dynamic date values — it prevents
  index seeks and causes full table scans on million-row fact tables.


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
================================================================
  STATUS VALUES & INTENT-BASED FILTER RULES  (part of SQL QUALITY RULES)
================================================================
All Status columns listed below are VARCHAR. NEVER use integer codes.

── A. STATUS VALUE CATALOG ─────────────────────────────────────────────
  FactSalesOrders.Status    : 'Open' | 'Partially Paid' | 'Close' | 'Cancel' | 'Void'
  FactSalesInvoice.Status   : 'Open' | 'Partially Paid' | 'Close' | 'Void' | 'Cancelled' | 'Reversed'
  FactCreditMemo.Status     : 'Open' | 'Partially Paid' | 'Close' | 'Void'
  FactVendorInvoice.Status  : 'Open' | 'Partially Paid' | 'Close' | 'Void'
  FactVendorPayments        : No Status column — voided = VoidDateKey IS NOT NULL
                              Default exclude: WHERE FVP.VoidDateKey IS NULL
  FactCustomerPayment       : No Status column — use as-is (no exclusion filter needed)
  FactCustomerReturn        : No Status column — use as-is
  FactConsignments          : No Status column — use as-is

── B. INTENT DETECTION — classify BEFORE writing any WHERE clause ───────
  Read the user's question and assign ONE of these intents:

  INTENT-1 [ANALYTICS]   — keywords: revenue, sales, total, profit, trend, summary,
                            comparison, forecast, how much, how many (total count),
                            YoY, monthly, quarterly, annual, report, statement, margin
                            → Exclude only invalidated records (Void / Cancelled / Reversed).
                              Include Open, Partially Paid, and Close.

  INTENT-2 [OPERATIONAL] — keywords: open, pending, ready, can be shipped, due,
                            outstanding, unpaid, not yet shipped, backlog, awaiting,
                            current, today, what needs to, actionable, active orders
                            → Include ONLY 'Open' and 'Partially Paid'.
                              Exclude Close, Cancel, Void entirely.

  INTENT-3 [COMPLETED]   — keywords: closed, fulfilled, completed, shipped, paid,
                            delivered, settled, done, processed, finalized
                            → Include ONLY 'Close'.
                              Exclude Open, Partially Paid, Cancel, Void.

  INTENT-4 [INVALID]     — keywords: cancelled, voided, reversed, rejected,
                            how many were cancelled, cancellation rate
                            → Include ONLY Cancel / Void / Reversed as relevant.
                              Exclude all active and completed records.

  INTENT-5 [FULL HISTORY] — keywords: all, every, including cancelled, full history,
                             regardless of status, even voided
                             → Apply NO status filter. Fetch everything.

  AMBIGUOUS RULE: If intent is unclear (no keywords match), default to INTENT-1
  [ANALYTICS] — exclude only Void/Cancelled/Reversed. NEVER default to INTENT-2
  or INTENT-3 unless the user's question clearly indicates active/open or completed.

── C. FILTER TEMPLATES ──────────────────────────────────────────────────

  INTENT-1 [ANALYTICS] — default for most queries:
    FactSalesOrders   → AND FSO.Status NOT IN ('Cancel', 'Void')
    FactSalesInvoice  → AND FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
    FactCreditMemo    → AND FCM.Status <> 'Void'
    FactVendorInvoice → AND FVI.Status <> 'Void'
    FactVendorPayments → AND FVP.VoidDateKey IS NULL

  INTENT-2 [OPERATIONAL] — open/pending/active/ready-to-ship queries:
    FactSalesOrders   → AND FSO.Status IN ('Open', 'Partially Paid')
    FactSalesInvoice  → AND FSI.Status IN ('Open', 'Partially Paid')
    FactCreditMemo    → AND FCM.Status IN ('Open', 'Partially Paid')
    FactVendorInvoice → AND FVI.Status IN ('Open', 'Partially Paid')
    FactVendorPayments → AND FVP.VoidDateKey IS NULL

  INTENT-3 [COMPLETED] — closed/fulfilled/paid queries:
    FactSalesOrders   → AND FSO.Status = 'Close'
    FactSalesInvoice  → AND FSI.Status = 'Close'
    FactCreditMemo    → AND FCM.Status = 'Close'
    FactVendorInvoice → AND FVI.Status = 'Close'

  INTENT-4 [INVALID] — cancelled/voided/reversed queries:
    FactSalesOrders   → AND FSO.Status IN ('Cancel', 'Void')
    FactSalesInvoice  → AND FSI.Status IN ('Void', 'Cancelled', 'Reversed')
    FactCreditMemo    → AND FCM.Status = 'Void'
    FactVendorInvoice → AND FVI.Status = 'Void'
    FactVendorPayments → AND FVP.VoidDateKey IS NOT NULL

  INTENT-5 [FULL HISTORY]: No status filter applied.

── D. OVERRIDE RULE ─────────────────────────────────────────────────────
  If the user explicitly names a status value in their question
  (e.g. "show Void invoices", "only Open orders", "all Cancelled transactions"),
  use that exact value directly — override all intent detection above.
  The user's explicit mention ALWAYS takes priority over the default intent filter.
- NULL-SAFE EXCLUSIONS: NEVER use NOT IN with a subquery. Use LEFT JOIN ... WHERE key IS NULL instead.
- ALWAYS COMPUTE WHAT IS ASKED: growth/trend/comparison → use LAG/LEAD window functions with both absolute and % change.
- PRODUCT ANALYSIS: Exclude discontinued (IsDiscontinued=0), cross-check inventory, include revenue/profit context.
- INVENTORY: FactInventorySnapshot has NO DateKey. Query directly.
    AvailableQty = QuantityOnHand - ISNULL(PickingQuantity,0) - ISNULL(SalesOrderQuantity,0).
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
      FINANCIAL STATEMENT OUTPUT RULES:
!! OVERRIDE — These rules take ABSOLUTE priority over all other output format rules !!
For ANY financial statement request (Balance Sheet, P&L, Income Statement, Profit & Loss),
output the statement as a TWO-COLUMN markdown table preserving the exact hierarchy below.

TABLE FORMAT RULES:
- Two columns only: | Description | Amount ($) |
- Header rows (Assets, Liabilities & Equity, Operating Expenses, etc.) → bold text, no amount: | **Assets** | |
- Sub-group rows (Current Assets, Property And Equipment, etc.) → bold text, no amount: | **Current Assets** | |
- Line item rows → indented with 4 spaces: |     Accounts Receivable | 1,234.56 |
- Total rows → bold text with amount: | **Total Assets** | 1,234,567.89 |
- Separator rows between sections → empty row: | | |
- Right-align the Amount column (---:), left-align Description (:---)
- No SQL. No summary sentence. No extra text before or after the table.
- NEVER show [value] — replace every [value] with the actual computed number.
- If a line item has no data, show 0.00.
- Numbers: 2 decimal places with thousands separators (e.g. 1,234,567.89).
- Negative numbers shown with a minus sign: -123,456.78
================================================================
------------------------
Balance Sheet Templates:- 
------------------------

*Balance Sheet Main Grouping/Grouped*
(One row per BalanceSheet_MainGroups value, grouped under Assets or Liabilities & Equity sections)

| Description | Amount ($) |
|:---|---:|
| **Assets** | |
|     Current Assets | [value] |
|     Non Current Assets | [value] |
| **Total Assets** | [value] |
| | |
| **Liabilities & Equity** | |
|     Current Liabilities | [value] |
|     Non Current Liabilities | [value] |
|     Equity | [value] |
|     Retained Earnings | [value] |
|     Contribution | [value] |
|     Distributions | [value] |
|     Profit & Loss | [value] |
| **Total Liabilities & Equity** | [value] |

*Balance Sheet Main Grouped — Multi-Month (2+ months requested)*
(Same structure but one amount column per month, side-by-side. Use SQL Example 7.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Assets** | | |
|     Current Assets | [value] | [value] |
|     Non Current Assets | [value] | [value] |
| **Total Assets** | [computed] | [computed] |
| | | |
| **Liabilities & Equity** | | |
|     Current Liabilities | [value] | [value] |
|     Non Current Liabilities | [value] | [value] |
|     Equity | [value] | [value] |
|     Retained Earnings | [value] | [value] |
|     Contribution | [value] | [value] |
|     Distributions | [value] | [value] |
|     Profit & Loss | [value] | [value] |
| **Total Liabilities & Equity** | [computed] | [computed] |


*Balance Sheet Sub Grouping*
(Section = Assets/L&E derived; Sub Group = BalanceSheet_MainGroups; Line Item = BalanceSheet_SubGroups)

| Description | Amount ($) |
|:---|---:|
| **Assets** | |
| **Current Assets** | |
|     Accounts Receivable | [value] |
|     Cash and Cash Equivalents | [value] |
|     Intercompanies | [value] |
|     Inventory | [value] |
|     Loans Payable - Related Parties | [value] |
|     Management Fees Receivable | [value] |
|     Other Receivables | [value] |
|     Prepaid Expenses | [value] |
| **Current Assets Total** | [value] |
| | |
| **Non Current Assets** | |
|     Furniture & Equipment | [value] |
|     Intangible & Other Assets | [value] |
|     Investments | [value] |
|     Leasehold Improvements | [value] |
|     Loans Receivable - Related Parties | [value] |
|     Loans Receivable Members and Former Members | [value] |
|     Long term notes receivable | [value] |
|     Other Receivables | [value] |
|     ROU Assets - Operating | [value] |
|     Transportations Equipment | [value] |
| **Non Current Assets Total** | [value] |
| | |
| **Total Assets** | [value] |
| | |
| **Liabilities & Equity** | |
| **Current Liabilities** | |
|     Accounts Payable | [value] |
|     Accrued Expenses | [value] |
|     Contract Liabilities | [value] |
|     Current Lease Liabilities | [value] |
|     Loans Payable - Related Parties | [value] |
|     Loans Receivable - Related Parties | [value] |
|     Loans Receivable Members and Former Members | [value] |
|     Management Fees Payable | [value] |
|     Short Term Note Payable - Related Party | [value] |
| **Current Liabilities Total** | [value] |
| | |
| **Non Current Liabilities** | |
|     Accrued Expenses | [value] |
|     Distributions | [value] |
|     Lease Liabilities - Non Current | [value] |
|     Loans Receivable - Related Parties | [value] |
| **Non Current Liabilities Total** | [value] |
| | |
| **Equity** | |
|     Additional Paid-in Capital | [value] |
|     Common Stock | [value] |
|     Loans Payable - Related Parties | [value] |
|     Member's Equity | [value] |
| **Equity Total** | [value] |
| | |
| **Retained Earnings** | |
|     Retained Earnings | [value] |
|     Unrealized Gain on Available for Sale Securities | [value] |
| **Retained Earnings Total** | [value] |
| | |
| **Contribution** | |
|     Loans Payable - Related Parties | [value] |
|     Distributions | [value] |
|     Profit & Loss | [value] |
| **Contribution Total** | [value] |
| | |
| **Total Liabilities & Equity** | [value] |

*Balance Sheet Sub Grouped — Multi-Month (2+ months requested)*
(Same structure but one amount column per month, side-by-side. Use SQL Example 8.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Assets** | | |
| **Current Assets** | | |
|     Accounts Receivable | [value] | [value] |
|     Cash and Cash Equivalents | [value] | [value] |
|     Intercompanies | [value] | [value] |
|     Inventory | [value] | [value] |
|     Loans Payable - Related Parties | [value] | [value] |
|     Management Fees Receivable | [value] | [value] |
|     Other Receivables | [value] | [value] |
|     Prepaid Expenses | [value] | [value] |
| **Current Assets Total** | [computed] | [computed] |
| | | |
| **Non Current Assets** | | |
|     Furniture & Equipment | [value] | [value] |
|     Intangible & Other Assets | [value] | [value] |
|     Investments | [value] | [value] |
|     Leasehold Improvements | [value] | [value] |
|     Loans Receivable - Related Parties | [value] | [value] |
|     Loans Receivable Members and Former Members | [value] | [value] |
|     Long term notes receivable | [value] | [value] |
|     Other Receivables | [value] | [value] |
|     ROU Assets - Operating | [value] | [value] |
|     Transportations Equipment | [value] | [value] |
| **Non Current Assets Total** | [computed] | [computed] |
| | | |
| **Total Assets** | [computed] | [computed] |
| | | |
| **Liabilities & Equity** | | |
| **Current Liabilities** | | |
|     Accounts Payable | [value] | [value] |
|     Accrued Expenses | [value] | [value] |
|     Contract Liabilities | [value] | [value] |
|     Current Lease Liabilities | [value] | [value] |
|     Loans Payable - Related Parties | [value] | [value] |
|     Loans Receivable - Related Parties | [value] | [value] |
|     Loans Receivable Members and Former Members | [value] | [value] |
|     Management Fees Payable | [value] | [value] |
|     Short Term Note Payable - Related Party | [value] | [value] |
| **Current Liabilities Total** | [computed] | [computed] |
| | | |
| **Non Current Liabilities** | | |
|     Accrued Expenses | [value] | [value] |
|     Distributions | [value] | [value] |
|     Lease Liabilities - Non Current | [value] | [value] |
|     Loans Receivable - Related Parties | [value] | [value] |
| **Non Current Liabilities Total** | [computed] | [computed] |
| | | |
| **Equity** | | |
|     Additional Paid-in Capital | [value] | [value] |
|     Common Stock | [value] | [value] |
|     Loans Payable - Related Parties | [value] | [value] |
|     Member's Equity | [value] | [value] |
| **Equity Total** | [computed] | [computed] |
| | | |
| **Retained Earnings** | | |
|     Retained Earnings | [value] | [value] |
|     Unrealized Gain on Available for Sale Securities | [value] | [value] |
| **Retained Earnings Total** | [computed] | [computed] |
| | | |
| **Contribution** | | |
|     Loans Payable - Related Parties | [value] | [value] |
|     Distributions | [value] | [value] |
|     Profit & Loss | [value] | [value] |
| **Contribution Total** | [computed] | [computed] |
| | | |
| **Total Liabilities & Equity** | [computed] | [computed] |


*Balance Sheet Detailed*
(4-level nesting — individual accounts listed under each Sub Group section)

| Description | Amount ($) |
|:---|---:|
| **Assets** | |
| **Current Assets** | |
|     1173279 B.C. LTD. (SAFAVIEH HO | [value] |
|     68 Campbell St, Inc | [value] |
|     Accounts Receivable | [value] |
|     Accounts Receivable - Pacific | [value] |
|     Accounts Receivable - Related Entities | [value] |
|     Accounts Receivable (NAV) | [value] |
|     Accounts Receivable (Top-Line) | [value] |
|     Accrued Customs & Duties | [value] |
|     Accrued Freight-In | [value] |
|     Allowance for Bad Debt | [value] |
|     AR - Before Acquisition | [value] |
|     AUGUSTA HOME CC PAYMENT | [value] |
|     Cash-Citibank | [value] |
|     Cash-Citibank CD | [value] |
|     Cash-Citibank Payroll | [value] |
|     Cash-Peoples Bank | [value] |
|     Cash-Peoples Bank CD | [value] |
|     Cash-Santander Bank | [value] |
|     Cash-Signature Bank | [value] |
|     Cash-TD Bank | [value] |
|     Citibank | [value] |
|     Citibank - Payroll | [value] |
|     Citibank #2 (7652) | [value] |
|     DECOR MARCHE LLC CITIBANK | [value] |
|     Employee Loans Receivable | [value] |
|     Exchange | [value] |
|     Inv Control - Cons to Cust | [value] |
|     Inv Control - Cost Change | [value] |
|     Inv Control - Cust Return | [value] |
|     Inv Control - Inventory Adj | [value] |
|     Inv Control - Physical Count | [value] |
|     Inv Control - Purchase | [value] |
|     Inv Control - Sale to Cust | [value] |
|     Inv Control - Vendor Return | [value] |
|     Inv Control - WHS Transfer | [value] |
|     Inventory | [value] |
|     Inventory Adjustment | [value] |
|     Inventory Non Rug | [value] |
|     Inventory Rug | [value] |
|     inventory write-down | [value] |
|     Investment Account - Cash | [value] |
|     LUXE LIVING SHOP LLC CITIBANK | [value] |
|     Management Fees Receivable | [value] |
|     Other Receivable | [value] |
|     Petty Cash | [value] |
|     Prepaid Expenses | [value] |
|     Prepaid Insurance | [value] |
|     Prepaid Inventory | [value] |
|     Prepaid NJ Corp Tax | [value] |
|     RETAIL DECOR MARCHE CITIBANK | [value] |
|     SAFAVIEH INC. - CREDIT CARD | [value] |
|     Safavieh Int Visa | [value] |
|     SAFAVIEH INT'L - CREDIT CARD | [value] |
|     Safavieh LTD (CAD) | [value] |
|     Safavieh LTD USD | [value] |
|     Safavieh Toronto | [value] |
|     SEI (AUGUSTA HOME) | [value] |
|     Shipment Clearing | [value] |
|     Transfers | [value] |
|     WHS CC PAYMENTS | [value] |
|     YARAGHI LLC - AMEX CARD | [value] |
|     YARAGHI LLC - CREDIT CARD | [value] |
|     YARAGHI LLC - PEOPLE'S BANK | [value] |
|     YARAGHI LLC - PEOPLE'S BANK CHECKING | [value] |
|     Yaraghi LLC - Santander Bank | [value] |
|     Yaraghi LLC - Signature Bank | [value] |
|     YARAGHI LLC - TD BANK | [value] |
| **Current Assets Total** | [value] |
| | |
| **Non Current Assets** | |
|     102 Norwest Court | [value] |
|     1073 Northern Blvd | [value] |
|     110 East Rt 4 | [value] |
|     110 Route 110 | [value] |
|     111 Cokesbury LLC | [value] |
|     1170 Northern Blvd | [value] |
|     1200 Route 523 | [value] |
|     125 Commerce Way | [value] |
|     150 Knowlton Way | [value] |
|     150 Thompson St LLC | [value] |
|     18 School Street | [value] |
|     1950 Benton Blvd. LLC | [value] |
|     1991 Northampton Street | [value] |
|     2 Channel Drive | [value] |
|     200 Atlantic Street LLC | [value] |
|     210 Atlantic | [value] |
|     2410 Northampton | [value] |
|     252 Atlantic | [value] |
|     2695 Plainfield Road LLC | [value] |
|     28 Washington St. | [value] |
|     3200 Baytown LLC | [value] |
|     380 Bloomsbury | [value] |
|     393 Oyster Bay Road | [value] |
|     442 Mt Pleasant | [value] |
|     45 Hartsdale | [value] |
|     455 Jimmy DeLoach | [value] |
|     605 Jimmy Deloach | [value] |
|     64 Nardozzi | [value] |
|     7580 Cherry Avenue | [value] |
|     76 Highlands Blvd | [value] |
|     7630 Cherry Avenue | [value] |
|     Accrued Interest Receivable | [value] |
|     Accum Deprec-Equipment | [value] |
|     Accum Deprec-LHI | [value] |
|     Accum Deprec-Office Furniture & Fixtures | [value] |
|     Accum Deprec-Transportation | [value] |
|     Allpoints LLC | [value] |
|     Atlantic (CT3) | [value] |
|     Atlantic Realty | [value] |
|     Augusta Home LLC | [value] |
|     Augusta Home LLC - SEI | [value] |
|     Brand ROU Asset | [value] |
|     Broadway LLC | [value] |
|     Contribution Receivable | [value] |
|     Danbury | [value] |
|     Decor Marche | [value] |
|     Decor Market | [value] |
|     Distributions Receivable | [value] |
|     Do not use | [value] |
|     Due From Saf Home Furn Ltd. | [value] |
|     Due to Hong Kong | [value] |
|     Due to/from India | [value] |
|     Due to/from Jonathan Y Designs | [value] |
|     Due to/from Safavieh Holding | [value] |
|     Due to/from Yaraghi Studios LLC | [value] |
|     Equipment | [value] |
|     Equipment-Do not use | [value] |
|     Farmingdale (LI) | [value] |
|     Glen Cove (LI-other3) | [value] |
|     Harbor Park | [value] |
|     Hartsdale (NY) | [value] |
|     Home Trends | [value] |
|     Home Trends LLC | [value] |
|     Intercompanies | [value] |
|     Investments | [value] |
|     Isfahan | [value] |
|     Leasehold Improvements | [value] |
|     Lindsay Market | [value] |
|     Livingston | [value] |
|     Loan - Safavieh Limited | [value] |
|     Loan-David Shalbaf | [value] |
|     LOAN-FARZAD RAHMANAN | [value] |
|     Loan-Safavieh Turkey | [value] |
|     LT Note Receivable Yaraghi Realty | [value] |
|     Luxe Living | [value] |
|     Madison | [value] |
|     New Rochelle LLC | [value] |
|     Note Receivable - Augusta Home | [value] |
|     Notes Receivable LT | [value] |
|     Notes Receivable ST | [value] |
|     Office Furniture & Fixtures | [value] |
|     Other deposits | [value] |
|     Pacific | [value] |
|     Paramus | [value] |
|     Rogers Road LLC | [value] |
|     ROU Asset - Operating Leases | [value] |
|     Safavieh 59 (Soho) | [value] |
|     Safavieh Group | [value] |
|     Safavieh Home | [value] |
|     Safavieh INC | [value] |
|     Safavieh International | [value] |
|     Safavieh Turkey | [value] |
|     Savannah Intl Trade | [value] |
|     Security Deposits | [value] |
|     Stamford Town Center LLC | [value] |
|     Subscription Receivable | [value] |
|     Tradeport East LLC | [value] |
|     Tradeport West LLC | [value] |
|     Transportation Equipment | [value] |
|     Whitestown 500 South LLC | [value] |
|     Yaraghi Holdings LLC | [value] |
|     Yaraghi LLC | [value] |
|     Yaraghi Realty | [value] |
| **Non Current Assets Total** | [value] |
| | |
| **Total Assets** | [value] |
| | |
| **Liabilities & Equity** | |
| **Current Liabilities** | |
|     Accounts Payable | [value] |
|     Accounts Payable - Related Entities | [value] |
|     Accounts Payable - Yaraghi LLC | [value] |
|     Accrued Expenses | [value] |
|     Accrued Interest Payable | [value] |
|     Accrued Inventory Purchase | [value] |
|     Accrued P/R | [value] |
|     Customer Deposits (Intl) | [value] |
|     Due to Alexander | [value] |
|     Due to Amanda | [value] |
|     Due to Andrew Sasan | [value] |
|     Due to Ashley Parvin | [value] |
|     Due to Brandon Chase | [value] |
|     Due to Darioush | [value] |
|     Due to Jacqueline | [value] |
|     Due to Jason M. | [value] |
|     Due to Katayoun | [value] |
|     Due to Kavon Christian | [value] |
|     Due to Kianoush/Jonathan | [value] |
|     Due to Kids (Loans) | [value] |
|     Due to Koorosh | [value] |
|     Due to Ryan | [value] |
|     Due to Tiffany | [value] |
|     Federal Taxes Withholding Payable | [value] |
|     L/P Ahmad | [value] |
|     L/P Arash | [value] |
|     L/P Cyrus | [value] |
|     L/P Majid | [value] |
|     L/P Moshen | [value] |
|     Loans Payable-Members | [value] |
|     Management Fees Payable | [value] |
|     Note Payable - Yaraghi LLC | [value] |
|     Note Payable ST - SCS Hong Kong | [value] |
|     NYS Transit Payable | [value] |
|     Operating Lease Liability - ST | [value] |
|     Payable Clearing | [value] |
|     Refund Liability | [value] |
|     Royalty Liability - ST | [value] |
|     Sales Tax Payable | [value] |
|     Subscription Payable | [value] |
| **Current Liabilities Total** | [value] |
| | |
| **Non Current Liabilities** | |
|     Distributions Payable | [value] |
|     Loan | [value] |
|     Loan-Ahmad | [value] |
|     Operating Lease Liability - LT | [value] |
|     Royalty Liability - LT | [value] |
| **Non Current Liabilities Total** | [value] |
| | |
| **Equity** | |
|     Accum Adjustments Account | [value] |
|     Capital Stock | [value] |
|     Members Equity | [value] |
|     Paid In Capital | [value] |
| **Equity Total** | [value] |
| | |
| **Retained Earnings** | |
|     Retained Earnings | [value] |
|     Unrealized Gain/Loss on Investment | [value] |
| **Retained Earnings Total** | [value] |
| | |
| **Contribution** | |
|     Contribution (Y.F. Trust) | [value] |
|     Contribution (Y.F. Trust) - Alexander | [value] |
|     Contribution (Y.F. Trust) - Amanda | [value] |
|     Contribution (Y.F. Trust) - Andrew | [value] |
|     Contribution (Y.F. Trust) - Ashley | [value] |
|     Contribution (Y.F. Trust) - Brandon | [value] |
|     Contribution (Y.F. Trust) - Darioush | [value] |
|     Contribution (Y.F. Trust) - Jacqueline | [value] |
|     Contribution (Y.F. Trust) - Jason | [value] |
|     Contribution (Y.F. Trust) - Jonathan | [value] |
|     Contribution (Y.F. Trust) - Katayoun | [value] |
|     Contribution (Y.F. Trust) - Kavon | [value] |
|     Contribution (Y.F. Trust) - Koorosh | [value] |
|     Contribution (Y.F. Trust) - Ryan | [value] |
|     Contribution (Y.F. Trust) - Tiffany | [value] |
|     Contributions | [value] |
|     Contributions - Ahmad | [value] |
|     Contributions - Arash | [value] |
|     Contributions - Cyrus | [value] |
|     Contributions - Majid | [value] |
|     Contributions - Mohsen | [value] |
|     Contributions-Ahmad | [value] |
|     Contributions-Arash | [value] |
|     Contributions-Cyrus | [value] |
|     Contributions-Majid | [value] |
|     Contributions-Mohsen | [value] |
| **Contribution Total** | [value] |
| | |
| **Distributions** | |
|     Distributions | [value] |
|     Distributions-Ahmad | [value] |
|     Distributions-Ahmad Trust | [value] |
|     Distributions-Alexander | [value] |
|     Distributions-Alexander Trust | [value] |
|     Distributions-Amanda | [value] |
|     Distributions-Amanda Trust | [value] |
|     Distributions-Andrew | [value] |
|     Distributions-Andrew Trust | [value] |
|     Distributions-Arash | [value] |
|     Distributions-Arash Trust | [value] |
|     Distributions-Ashley | [value] |
|     Distributions-Ashley Trust | [value] |
|     Distributions-Brandon | [value] |
|     Distributions-Brandon Trust | [value] |
|     Distributions-Cyrus | [value] |
|     Distributions-Cyrus Trust | [value] |
|     Distributions-Darioush | [value] |
|     Distributions-Darioush Trust | [value] |
|     Distributions-DO NOT USE | [value] |
|     Distributions-Jacqueline | [value] |
|     Distributions-Jacqueline Trust | [value] |
|     Distributions-Jason | [value] |
|     Distributions-Jason Trust | [value] |
|     Distributions-Jonathan | [value] |
|     Distributions-Jonathan Trust | [value] |
|     Distributions-Katayoun | [value] |
|     Distributions-Katayoun Trust | [value] |
|     Distributions-Kavon | [value] |
|     Distributions-Kavon Trust | [value] |
|     Distributions-Koorosh | [value] |
|     Distributions-Koorosh Trust | [value] |
|     Distributions-Majid | [value] |
|     Distributions-Majid Trust | [value] |
|     Distributions-Mohsen | [value] |
|     Distributions-Mohsen Trust | [value] |
|     Distributions-Ryan | [value] |
|     Distributions-Ryan Trust | [value] |
|     Distributions-Tiffany | [value] |
|     Distributions-Tiffany Trust | [value] |
|     Distributions-Trust | [value] |
| **Distributions Total** | [value] |
| | |
| **Profit & Loss** | |
|     Profit & Loss | [value] |
| **Profit & Loss Total** | [value] |
| | |
| **Total Liabilities & Equity** | [value] |

*Balance Sheet Detailed — Multi-Month (2+ months requested)*
(Same account-level structure but one amount column per month, side-by-side. Use SQL Example 9.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Assets** | | |
| **Current Assets** | | |
|     1173279 B.C. LTD. (SAFAVIEH HO | [value] | [value] |
|     68 Campbell St, Inc | [value] | [value] |
|     Accounts Receivable | [value] | [value] |
|     Accounts Receivable - Pacific | [value] | [value] |
|     Accounts Receivable - Related Entities | [value] | [value] |
|     Accounts Receivable (NAV) | [value] | [value] |
|     Accounts Receivable (Top-Line) | [value] | [value] |
|     Accrued Customs & Duties | [value] | [value] |
|     Accrued Freight-In | [value] | [value] |
|     Allowance for Bad Debt | [value] | [value] |
|     AR - Before Acquisition | [value] | [value] |
|     AUGUSTA HOME CC PAYMENT | [value] | [value] |
|     Cash-Citibank | [value] | [value] |
|     Cash-Citibank CD | [value] | [value] |
|     Cash-Citibank Payroll | [value] | [value] |
|     Cash-Peoples Bank | [value] | [value] |
|     Cash-Peoples Bank CD | [value] | [value] |
|     Cash-Santander Bank | [value] | [value] |
|     Cash-Signature Bank | [value] | [value] |
|     Cash-TD Bank | [value] | [value] |
|     Citibank | [value] | [value] |
|     Citibank - Payroll | [value] | [value] |
|     Citibank #2 (7652) | [value] | [value] |
|     DECOR MARCHE LLC CITIBANK | [value] | [value] |
|     Employee Loans Receivable | [value] | [value] |
|     Exchange | [value] | [value] |
|     Inv Control - Cons to Cust | [value] | [value] |
|     Inv Control - Cost Change | [value] | [value] |
|     Inv Control - Cust Return | [value] | [value] |
|     Inv Control - Inventory Adj | [value] | [value] |
|     Inv Control - Physical Count | [value] | [value] |
|     Inv Control - Purchase | [value] | [value] |
|     Inv Control - Sale to Cust | [value] | [value] |
|     Inv Control - Vendor Return | [value] | [value] |
|     Inv Control - WHS Transfer | [value] | [value] |
|     Inventory | [value] | [value] |
|     Inventory Adjustment | [value] | [value] |
|     Inventory Non Rug | [value] | [value] |
|     Inventory Rug | [value] | [value] |
|     inventory write-down | [value] | [value] |
|     Investment Account - Cash | [value] | [value] |
|     LUXE LIVING SHOP LLC CITIBANK | [value] | [value] |
|     Management Fees Receivable | [value] | [value] |
|     Other Receivable | [value] | [value] |
|     Petty Cash | [value] | [value] |
|     Prepaid Expenses | [value] | [value] |
|     Prepaid Insurance | [value] | [value] |
|     Prepaid Inventory | [value] | [value] |
|     Prepaid NJ Corp Tax | [value] | [value] |
|     RETAIL DECOR MARCHE CITIBANK | [value] | [value] |
|     SAFAVIEH INC. - CREDIT CARD | [value] | [value] |
|     Safavieh Int Visa | [value] | [value] |
|     SAFAVIEH INT'L - CREDIT CARD | [value] | [value] |
|     Safavieh LTD (CAD) | [value] | [value] |
|     Safavieh LTD USD | [value] | [value] |
|     Safavieh Toronto | [value] | [value] |
|     SEI (AUGUSTA HOME) | [value] | [value] |
|     Shipment Clearing | [value] | [value] |
|     Transfers | [value] | [value] |
|     WHS CC PAYMENTS | [value] | [value] |
|     YARAGHI LLC - AMEX CARD | [value] | [value] |
|     YARAGHI LLC - CREDIT CARD | [value] | [value] |
|     YARAGHI LLC - PEOPLE'S BANK | [value] | [value] |
|     YARAGHI LLC - PEOPLE'S BANK CHECKING | [value] | [value] |
|     Yaraghi LLC - Santander Bank | [value] | [value] |
|     Yaraghi LLC - Signature Bank | [value] | [value] |
|     YARAGHI LLC - TD BANK | [value] | [value] |
| **Current Assets Total** | [computed] | [computed] |
| | | |
| **Non Current Assets** | | |
|     102 Norwest Court | [value] | [value] |
|     1073 Northern Blvd | [value] | [value] |
|     110 East Rt 4 | [value] | [value] |
|     110 Route 110 | [value] | [value] |
|     111 Cokesbury LLC | [value] | [value] |
|     1170 Northern Blvd | [value] | [value] |
|     1200 Route 523 | [value] | [value] |
|     125 Commerce Way | [value] | [value] |
|     150 Knowlton Way | [value] | [value] |
|     150 Thompson St LLC | [value] | [value] |
|     18 School Street | [value] | [value] |
|     1950 Benton Blvd. LLC | [value] | [value] |
|     1991 Northampton Street | [value] | [value] |
|     2 Channel Drive | [value] | [value] |
|     200 Atlantic Street LLC | [value] | [value] |
|     210 Atlantic | [value] | [value] |
|     2410 Northampton | [value] | [value] |
|     252 Atlantic | [value] | [value] |
|     2695 Plainfield Road LLC | [value] | [value] |
|     28 Washington St. | [value] | [value] |
|     3200 Baytown LLC | [value] | [value] |
|     380 Bloomsbury | [value] | [value] |
|     393 Oyster Bay Road | [value] | [value] |
|     442 Mt Pleasant | [value] | [value] |
|     45 Hartsdale | [value] | [value] |
|     455 Jimmy DeLoach | [value] | [value] |
|     605 Jimmy Deloach | [value] | [value] |
|     64 Nardozzi | [value] | [value] |
|     7580 Cherry Avenue | [value] | [value] |
|     76 Highlands Blvd | [value] | [value] |
|     7630 Cherry Avenue | [value] | [value] |
|     Accrued Interest Receivable | [value] | [value] |
|     Accum Deprec-Equipment | [value] | [value] |
|     Accum Deprec-LHI | [value] | [value] |
|     Accum Deprec-Office Furniture & Fixtures | [value] | [value] |
|     Accum Deprec-Transportation | [value] | [value] |
|     Allpoints LLC | [value] | [value] |
|     Atlantic (CT3) | [value] | [value] |
|     Atlantic Realty | [value] | [value] |
|     Augusta Home LLC | [value] | [value] |
|     Augusta Home LLC - SEI | [value] | [value] |
|     Brand ROU Asset | [value] | [value] |
|     Broadway LLC | [value] | [value] |
|     Contribution Receivable | [value] | [value] |
|     Danbury | [value] | [value] |
|     Decor Marche | [value] | [value] |
|     Decor Market | [value] | [value] |
|     Distributions Receivable | [value] | [value] |
|     Do not use | [value] | [value] |
|     Due From Saf Home Furn Ltd. | [value] | [value] |
|     Due to Hong Kong | [value] | [value] |
|     Due to/from India | [value] | [value] |
|     Due to/from Jonathan Y Designs | [value] | [value] |
|     Due to/from Safavieh Holding | [value] | [value] |
|     Due to/from Yaraghi Studios LLC | [value] | [value] |
|     Equipment | [value] | [value] |
|     Equipment-Do not use | [value] | [value] |
|     Farmingdale (LI) | [value] | [value] |
|     Glen Cove (LI-other3) | [value] | [value] |
|     Harbor Park | [value] | [value] |
|     Hartsdale (NY) | [value] | [value] |
|     Home Trends | [value] | [value] |
|     Home Trends LLC | [value] | [value] |
|     Intercompanies | [value] | [value] |
|     Investments | [value] | [value] |
|     Isfahan | [value] | [value] |
|     Leasehold Improvements | [value] | [value] |
|     Lindsay Market | [value] | [value] |
|     Livingston | [value] | [value] |
|     Loan - Safavieh Limited | [value] | [value] |
|     Loan-David Shalbaf | [value] | [value] |
|     LOAN-FARZAD RAHMANAN | [value] | [value] |
|     Loan-Safavieh Turkey | [value] | [value] |
|     LT Note Receivable Yaraghi Realty | [value] | [value] |
|     Luxe Living | [value] | [value] |
|     Madison | [value] | [value] |
|     New Rochelle LLC | [value] | [value] |
|     Note Receivable - Augusta Home | [value] | [value] |
|     Notes Receivable LT | [value] | [value] |
|     Notes Receivable ST | [value] | [value] |
|     Office Furniture & Fixtures | [value] | [value] |
|     Other deposits | [value] | [value] |
|     Pacific | [value] | [value] |
|     Paramus | [value] | [value] |
|     Rogers Road LLC | [value] | [value] |
|     ROU Asset - Operating Leases | [value] | [value] |
|     Safavieh 59 (Soho) | [value] | [value] |
|     Safavieh Group | [value] | [value] |
|     Safavieh Home | [value] | [value] |
|     Safavieh INC | [value] | [value] |
|     Safavieh International | [value] | [value] |
|     Safavieh Turkey | [value] | [value] |
|     Savannah Intl Trade | [value] | [value] |
|     Security Deposits | [value] | [value] |
|     Stamford Town Center LLC | [value] | [value] |
|     Subscription Receivable | [value] | [value] |
|     Tradeport East LLC | [value] | [value] |
|     Tradeport West LLC | [value] | [value] |
|     Transportation Equipment | [value] | [value] |
|     Whitestown 500 South LLC | [value] | [value] |
|     Yaraghi Holdings LLC | [value] | [value] |
|     Yaraghi LLC | [value] | [value] |
|     Yaraghi Realty | [value] | [value] |
| **Non Current Assets Total** | [computed] | [computed] |
| | | |
| **Total Assets** | [computed] | [computed] |
| | | |
| **Liabilities & Equity** | | |
| **Current Liabilities** | | |
|     Accounts Payable | [value] | [value] |
|     Accounts Payable - Related Entities | [value] | [value] |
|     Accounts Payable - Yaraghi LLC | [value] | [value] |
|     Accrued Expenses | [value] | [value] |
|     Accrued Interest Payable | [value] | [value] |
|     Accrued Inventory Purchase | [value] | [value] |
|     Accrued P/R | [value] | [value] |
|     Customer Deposits (Intl) | [value] | [value] |
|     Due to Alexander | [value] | [value] |
|     Due to Amanda | [value] | [value] |
|     Due to Andrew Sasan | [value] | [value] |
|     Due to Ashley Parvin | [value] | [value] |
|     Due to Brandon Chase | [value] | [value] |
|     Due to Darioush | [value] | [value] |
|     Due to Jacqueline | [value] | [value] |
|     Due to Jason M. | [value] | [value] |
|     Due to Katayoun | [value] | [value] |
|     Due to Kavon Christian | [value] | [value] |
|     Due to Kianoush/Jonathan | [value] | [value] |
|     Due to Kids (Loans) | [value] | [value] |
|     Due to Koorosh | [value] | [value] |
|     Due to Ryan | [value] | [value] |
|     Due to Tiffany | [value] | [value] |
|     Federal Taxes Withholding Payable | [value] | [value] |
|     L/P Ahmad | [value] | [value] |
|     L/P Arash | [value] | [value] |
|     L/P Cyrus | [value] | [value] |
|     L/P Majid | [value] | [value] |
|     L/P Moshen | [value] | [value] |
|     Loans Payable-Members | [value] | [value] |
|     Management Fees Payable | [value] | [value] |
|     Note Payable - Yaraghi LLC | [value] | [value] |
|     Note Payable ST - SCS Hong Kong | [value] | [value] |
|     NYS Transit Payable | [value] | [value] |
|     Operating Lease Liability - ST | [value] | [value] |
|     Payable Clearing | [value] | [value] |
|     Refund Liability | [value] | [value] |
|     Royalty Liability - ST | [value] | [value] |
|     Sales Tax Payable | [value] | [value] |
|     Subscription Payable | [value] | [value] |
| **Current Liabilities Total** | [computed] | [computed] |
| | | |
| **Non Current Liabilities** | | |
|     Distributions Payable | [value] | [value] |
|     Loan | [value] | [value] |
|     Loan-Ahmad | [value] | [value] |
|     Operating Lease Liability - LT | [value] | [value] |
|     Royalty Liability - LT | [value] | [value] |
| **Non Current Liabilities Total** | [computed] | [computed] |
| | | |
| **Equity** | | |
|     Accum Adjustments Account | [value] | [value] |
|     Capital Stock | [value] | [value] |
|     Members Equity | [value] | [value] |
|     Paid In Capital | [value] | [value] |
| **Equity Total** | [computed] | [computed] |
| | | |
| **Retained Earnings** | | |
|     Retained Earnings | [value] | [value] |
|     Unrealized Gain/Loss on Investment | [value] | [value] |
| **Retained Earnings Total** | [computed] | [computed] |
| | | |
| **Contribution** | | |
|     Contribution (Y.F. Trust) | [value] | [value] |
|     Contribution (Y.F. Trust) - Alexander | [value] | [value] |
|     Contribution (Y.F. Trust) - Amanda | [value] | [value] |
|     Contribution (Y.F. Trust) - Andrew | [value] | [value] |
|     Contribution (Y.F. Trust) - Ashley | [value] | [value] |
|     Contribution (Y.F. Trust) - Brandon | [value] | [value] |
|     Contribution (Y.F. Trust) - Darioush | [value] | [value] |
|     Contribution (Y.F. Trust) - Jacqueline | [value] | [value] |
|     Contribution (Y.F. Trust) - Jason | [value] | [value] |
|     Contribution (Y.F. Trust) - Jonathan | [value] | [value] |
|     Contribution (Y.F. Trust) - Katayoun | [value] | [value] |
|     Contribution (Y.F. Trust) - Kavon | [value] | [value] |
|     Contribution (Y.F. Trust) - Koorosh | [value] | [value] |
|     Contribution (Y.F. Trust) - Ryan | [value] | [value] |
|     Contribution (Y.F. Trust) - Tiffany | [value] | [value] |
|     Contributions | [value] | [value] |
|     Contributions - Ahmad | [value] | [value] |
|     Contributions - Arash | [value] | [value] |
|     Contributions - Cyrus | [value] | [value] |
|     Contributions - Majid | [value] | [value] |
|     Contributions - Mohsen | [value] | [value] |
|     Contributions-Ahmad | [value] | [value] |
|     Contributions-Arash | [value] | [value] |
|     Contributions-Cyrus | [value] | [value] |
|     Contributions-Majid | [value] | [value] |
|     Contributions-Mohsen | [value] | [value] |
| **Contribution Total** | [computed] | [computed] |
| | | |
| **Distributions** | | |
|     Distributions | [value] | [value] |
|     Distributions-Ahmad | [value] | [value] |
|     Distributions-Ahmad Trust | [value] | [value] |
|     Distributions-Alexander | [value] | [value] |
|     Distributions-Alexander Trust | [value] | [value] |
|     Distributions-Amanda | [value] | [value] |
|     Distributions-Amanda Trust | [value] | [value] |
|     Distributions-Andrew | [value] | [value] |
|     Distributions-Andrew Trust | [value] | [value] |
|     Distributions-Arash | [value] | [value] |
|     Distributions-Arash Trust | [value] | [value] |
|     Distributions-Ashley | [value] | [value] |
|     Distributions-Ashley Trust | [value] | [value] |
|     Distributions-Brandon | [value] | [value] |
|     Distributions-Brandon Trust | [value] | [value] |
|     Distributions-Cyrus | [value] | [value] |
|     Distributions-Cyrus Trust | [value] | [value] |
|     Distributions-Darioush | [value] | [value] |
|     Distributions-Darioush Trust | [value] | [value] |
|     Distributions-DO NOT USE | [value] | [value] |
|     Distributions-Jacqueline | [value] | [value] |
|     Distributions-Jacqueline Trust | [value] | [value] |
|     Distributions-Jason | [value] | [value] |
|     Distributions-Jason Trust | [value] | [value] |
|     Distributions-Jonathan | [value] | [value] |
|     Distributions-Jonathan Trust | [value] | [value] |
|     Distributions-Katayoun | [value] | [value] |
|     Distributions-Katayoun Trust | [value] | [value] |
|     Distributions-Kavon | [value] | [value] |
|     Distributions-Kavon Trust | [value] | [value] |
|     Distributions-Koorosh | [value] | [value] |
|     Distributions-Koorosh Trust | [value] | [value] |
|     Distributions-Majid | [value] | [value] |
|     Distributions-Majid Trust | [value] | [value] |
|     Distributions-Mohsen | [value] | [value] |
|     Distributions-Mohsen Trust | [value] | [value] |
|     Distributions-Ryan | [value] | [value] |
|     Distributions-Ryan Trust | [value] | [value] |
|     Distributions-Tiffany | [value] | [value] |
|     Distributions-Tiffany Trust | [value] | [value] |
|     Distributions-Trust | [value] | [value] |
| **Distributions Total** | [computed] | [computed] |
| | | |
| **Profit & Loss** | | |
|     Profit & Loss | [value] | [value] |
| **Profit & Loss Total** | [computed] | [computed] |
| | | |
| **Total Liabilities & Equity** | [computed] | [computed] |


------------------------
P&L Statement Templates:-
------------------------

*P&L Statement / Income Statement Main Grouped*
(SQL returns [Group, Amount]. Bot computes Gross Profit, Operating Profit, Net Profit.)

CRITICAL LABEL RULES — NEVER rename or substitute any group name from the SQL result:
  - "Cost Of Goods Sold"   → NEVER write as "Cost Of Sales", "COGS", or any other alias
  - "Operating Expenses"   → NEVER split into sub-lines or rename; show as a single bold line
  - "Interest Expenses"    → NEVER write as "Finance Charges", "Interest Expense", or any other alias
  - "Other Income/Expenses"→ NEVER write as "Other Income", "Other Income/Expense", or any variation
  - "Taxes"                → NEVER write as "Income Taxes", "Tax Expense", or any other alias
  - Use the EXACT string returned by SQL for every row. If a group has no data (0 or absent), still show the row as 0.00.

| Description | Amount ($) |
|:---|---:|
| **Sales** | [value] |
| **Cost Of Goods Sold** | [value] |
| **Gross Profit/(Loss)** | [Sales minus Cost Of Goods Sold] |
| | |
| **Operating Expenses** | [value] |
| **Operating Profit/(Loss)** | [Gross Profit minus Operating Expenses] |
| | |
| **Other Income/Expenses** | [value] |
| **Interest Expenses** | [value] |
| **Taxes** | [value] |
| **Net Profit/(Loss)** | [Operating Profit plus Other Income/Expenses minus Interest Expenses minus Taxes] |

*P&L Main Grouped — Multi-Month (2+ months requested)*
(Same structure but one amount column per month, side-by-side. Use SQL Example 10.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Sales** | [value] | [value] |
| **Cost Of Goods Sold** | [value] | [value] |
| **Gross Profit/(Loss)** | [computed] | [computed] |
| | | |
| **Operating Expenses** | [value] | [value] |
| **Operating Profit/(Loss)** | [computed] | [computed] |
| | | |
| **Other Income/Expenses** | [value] | [value] |
| **Interest Expenses** | [value] | [value] |
| **Taxes** | [value] | [value] |
| **Net Profit/(Loss)** | [computed] | [computed] |


*P&L Statement / Income Statement Sub Grouped*
(SQL returns [Main Group, Sub Group, Amount]. Bot computes section totals and Gross/Operating/Net Profit.)

| Description | Amount ($) |
|:---|---:|
| **Sales** | |
|     Gross Sales | [value] |
|     Intercompany Sales/Purchases | [value] |
|     Returns | [value] |
|     Discount | [value] |
|     Advertising & Promotion | [value] |
|     Bad Debt | [value] |
|     Cash Receipt Transfer | [value] |
|     Commission | [value] |
|     Defective | [value] |
| **Sales Total** | [sum of Sales sub-groups] |
| | |
| **Cost of Goods Sold** | |
|     Cost of Goods Sold | [value] |
|     Customs and Duties | [value] |
|     Freight-In | [value] |
|     Intercompany Sales/Purchases | [value] |
|     Inventory Adjustment | [value] |
|     Inventory Valuation Adjustment | [value] |
|     Management Fee Expense/Income | [value] |
|     Wash & Repairs | [value] |
| **Cost of Goods Sold Total** | [sum of Cost of Goods Sold sub-groups] |
| | |
| **Gross Profit/(Loss)** | [Sales Total minus Cost of Goods Sold Total] |
| | |
| **Operating Expenses** | |
|     401k - Retirement Expense | [value] |
|     Advertising and Promotion Expenses | [value] |
|     Bad Debt Expense | [value] |
|     Bank Charges, License & Permits and Misc | [value] |
|     Commissions Expense | [value] |
|     Computer Expense | [value] |
|     Credit Card Charges | [value] |
|     Delivery Expenses | [value] |
|     Depreciation and Amortization Expense | [value] |
|     Entertainment & Meals Expense | [value] |
|     Health Insurance | [value] |
|     Income Tax and Filing Fees Expense | [value] |
|     Insurance | [value] |
|     Light Heat Power | [value] |
|     Office Expense | [value] |
|     Postage | [value] |
|     Professional Fees | [value] |
|     Rent Expense | [value] |
|     Repairs and Maintenance Expense | [value] |
|     Royalties | [value] |
|     Salaries and Wages | [value] |
|     Security Expense | [value] |
|     Telephone Expense | [value] |
|     Travel Expense | [value] |
|     Warehouse Supplies and Expense | [value] |
| **Operating Expenses Total** | [sum of Operating Expenses sub-groups] |
| | |
| **Operating Profit/(Loss)** | [Gross Profit minus Operating Expenses Total] |
| | |
| **Other Income/Expenses** | |
|     Dividend Income | [value] |
|     Gain/Loss on Investment | [value] |
|     Interest Income | [value] |
|     Management Fee Expense/Income | [value] |
|     Other Income | [value] |
|     Realized Gain/Loss on Investments | [value] |
|     Unrealized Gains/Losses | [value] |
| **Other Income/Expenses Total** | [sum of Other Income/Expenses sub-groups] |
| | |
| **Interest Expenses** | |
|     Interest Expense | [value] |
| **Interest Expenses Total** | [sum of Interest Expenses sub-groups] |
| | |
| **Taxes** | |
|     Income Tax and Filing Fees Expense | [value] |
| **Taxes Total** | [sum of Taxes sub-groups] |
| | |
| **Net Profit/(Loss)** | [Operating Profit plus Other Income/Expenses Total plus Interest Expenses Total plus Taxes Total] |

*P&L Sub Grouped — Multi-Month (2+ months requested)*
(Same structure but one amount column per month, side-by-side. Use SQL Example 11.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Sales** | | |
|     Gross Sales | [value] | [value] |
|     Intercompany Sales/Purchases | [value] | [value] |
|     Returns | [value] | [value] |
|     Discount | [value] | [value] |
|     Advertising & Promotion | [value] | [value] |
|     Bad Debt | [value] | [value] |
|     Cash Receipt Transfer | [value] | [value] |
|     Commission | [value] | [value] |
|     Defective | [value] | [value] |
| **Sales Total** | [computed] | [computed] |
| | | |
| **Cost of Goods Sold** | | |
|     Cost of Goods Sold | [value] | [value] |
|     Customs and Duties | [value] | [value] |
|     Freight-In | [value] | [value] |
|     Intercompany Sales/Purchases | [value] | [value] |
|     Inventory Adjustment | [value] | [value] |
|     Inventory Valuation Adjustment | [value] | [value] |
|     Management Fee Expense/Income | [value] | [value] |
|     Wash & Repairs | [value] | [value] |
| **Cost of Goods Sold Total** | [computed] | [computed] |
| | | |
| **Gross Profit/(Loss)** | [computed] | [computed] |
| | | |
| **Operating Expenses** | | |
|     401k - Retirement Expense | [value] | [value] |
|     Advertising and Promotion Expenses | [value] | [value] |
|     Bad Debt Expense | [value] | [value] |
|     Bank Charges, License & Permits and Misc | [value] | [value] |
|     Commissions Expense | [value] | [value] |
|     Computer Expense | [value] | [value] |
|     Credit Card Charges | [value] | [value] |
|     Delivery Expenses | [value] | [value] |
|     Depreciation and Amortization Expense | [value] | [value] |
|     Entertainment & Meals Expense | [value] | [value] |
|     Health Insurance | [value] | [value] |
|     Income Tax and Filing Fees Expense | [value] | [value] |
|     Insurance | [value] | [value] |
|     Light Heat Power | [value] | [value] |
|     Office Expense | [value] | [value] |
|     Postage | [value] | [value] |
|     Professional Fees | [value] | [value] |
|     Rent Expense | [value] | [value] |
|     Repairs and Maintenance Expense | [value] | [value] |
|     Royalties | [value] | [value] |
|     Salaries and Wages | [value] | [value] |
|     Security Expense | [value] | [value] |
|     Telephone Expense | [value] | [value] |
|     Travel Expense | [value] | [value] |
|     Warehouse Supplies and Expense | [value] | [value] |
| **Operating Expenses Total** | [computed] | [computed] |
| | | |
| **Operating Profit/(Loss)** | [computed] | [computed] |
| | | |
| **Other Income/Expenses** | | |
|     Dividend Income | [value] | [value] |
|     Gain/Loss on Investment | [value] | [value] |
|     Interest Income | [value] | [value] |
|     Management Fee Expense/Income | [value] | [value] |
|     Other Income | [value] | [value] |
|     Realized Gain/Loss on Investments | [value] | [value] |
|     Unrealized Gains/Losses | [value] | [value] |
| **Other Income/Expenses Total** | [computed] | [computed] |
| | | |
| **Interest Expenses** | | |
|     Interest Expense | [value] | [value] |
| **Interest Expenses Total** | [computed] | [computed] |
| | | |
| **Taxes** | | |
|     Income Tax and Filing Fees Expense | [value] | [value] |
| **Taxes Total** | [computed] | [computed] |
| | | |
| **Net Profit/(Loss)** | [computed] | [computed] |


*P&L Statement / Income Statement Detailed*
(SQL returns [Main Group, Sub Group, Account, Amount]. Bot computes section totals and Gross/Operating/Net Profit lines.)

| Description | Amount ($) |
|:---|---:|
| **Sales** | |
|     Sales | [value] |
|     Sales Discount | [value] |
|     Sales Discount - Albertsons | [value] |
|     Sales Discount - Amz Marketplace | [value] |
|     Sales Discount - Bison Commerce | [value] |
|     Sales Discount - Bob'S Discount Ecomm A/C | [value] |
|     Sales Discount - Gordon Co | [value] |
|     Sales Discount - Home Depot Pr | [value] |
|     Sales Discount - Jc Penny | [value] |
|     Sales Discount - Lowe'S | [value] |
|     Sales Discount - Nebraska / Home Maker | [value] |
|     Sales Discount - Pier 1 | [value] |
|     Sales Discount - Rugs Direct | [value] |
|     Sales Discount - Wayfair Ca | [value] |
|     Sales Discount - Wm Marketplace | [value] |
|     Sales Discount - Zulily | [value] |
|     Sales Discount -Rug& Home Group | [value] |
|     Sales Discount -Weekends Only | [value] |
|     Sales Discount-Amazon | [value] |
|     Sales Discount-Amazon Ca | [value] |
|     Sales Discount-Ashley Furnit | [value] |
|     Sales Discount-Bealls | [value] |
|     Sales Discount-Bed Bath & Beyo | [value] |
|     Sales Discount-Cost Plus Wor | [value] |
|     Sales Discount-Faire | [value] |
|     Sales Discount-Groupon | [value] |
|     Sales Discount-Hayneedle | [value] |
|     Sales Discount-Home Depot | [value] |
|     Sales Discount-Home Roots | [value] |
|     Sales Discount-Kirkland | [value] |
|     Sales Discount-Macys | [value] |
|     Sales Discount-Menards | [value] |
|     Sales Discount-Mink & Sons | [value] |
|     Sales Discount-Old Time Potte | [value] |
|     Sales Discount-Others | [value] |
|     Sales Discount-Overstock | [value] |
|     Sales Discount-Plush Rugs | [value] |
|     Sales Discount-Pottery Barn | [value] |
|     Sales Discount-Qvc | [value] |
|     Sales Discount-Walmart | [value] |
|     Sales Discount-Wayfair | [value] |
|     Sales Returns (Not Received) | [value] |
|     Sales-Price Differences | [value] |
|     Sales-Short Shipment Deduction | [value] |
|     Serv-Drop Ship Fees | [value] |
|     Services & Other Charges | [value] |
|     Shipping & Handling | [value] |
|     Charge Back | [value] |
|     Claim Receipts From Customers | [value] |
|     Claim Receipts-Home Depot | [value] |
|     Prior Sales Returns | [value] |
|     Returns On Sales | [value] |
|     Returns Shipping & Service Cha | [value] |
| **Total Sales** | [computed] |
| | |
| **Cost Of Goods Sold** | |
|     Cost Of Goods Sold | [value] |
|     Box Program Job Work Costs | [value] |
|     Damaged-Discarded Inventory | [value] |
|     Designing & Development Expens | [value] |
|     Dhl-Sample Mailing Expense | [value] |
|     Domestic Trucking Line Freight | [value] |
|     Domestic Trucking Line Freight - Lvt | [value] |
|     Fab Floors-Clearing & Forwarding Expense | [value] |
|     Fedex/Ups Additional Handling | [value] |
|     Fedex/Ups Shipping Expense | [value] |
|     Freight - Pillow-Poufs | [value] |
|     Freight Cap Promotions Expense | [value] |
|     Freight Costs-Replacements Etc | [value] |
|     Freight Damage Loss/Gain A/C | [value] |
|     Freight Discount On Lr | [value] |
|     Import - Prepaid Import Costs | [value] |
|     Import Clearing And Forwarding | [value] |
|     Import-Air Freight | [value] |
|     Import-Cargo Insurance | [value] |
|     Import-Container Storage -Detention Chgs | [value] |
|     Import-Container Truck Freight | [value] |
|     Import-Customs Clearance Cost | [value] |
|     Import-Customs Documents Chgs | [value] |
|     Import-Ocean Freight | [value] |
|     Import-State Custom Duty | [value] |
|     Import-Tariffs | [value] |
|     Insert - Pillow | [value] |
|     Insert Materials Cost | [value] |
|     Insert-Pouf / Pet Beds Filling | [value] |
|     Inventory Adjustment Account | [value] |
|     Labelling & Ticketing Expense | [value] |
|     Merchandising&Inspection Fee | [value] |
|     Obsolete Inventory | [value] |
|     Packing Expense | [value] |
|     Processing Charge | [value] |
|     Purchase Discount | [value] |
|     Rug Cleaning | [value] |
|     Rug Surging, Cutting,Repairng | [value] |
|     Temporary Labor Expenses | [value] |
|     Third Party Warehouse Charges | [value] |
|     Truck-Trailer Rent Costs | [value] |
|     Upc Code Purchase | [value] |
|     Us Customs Bond Fee | [value] |
|     Use 5051-004 Import  Duty | [value] |
|     Vendor Defective Reimbursement | [value] |
| **Total Cost Of Goods Sold** | [computed] |
| | |
| **Gross Profit/(Loss)** | [computed] |
| | |
| **Operating Expenses** | |
| **General & Administrative** | |
|     Auto Expenses | [value] |
|     Auto Expenses-Auto Insurance | [value] |
|     Auto Expenses-Fuel | [value] |
|     Auto Expenses-Repairs & Maint. | [value] |
|     Auto Expenses-Tag Fees Etc. | [value] |
|     Auto Reimbursement Exp ?? | [value] |
|     Car Insurance | [value] |
|     Cash Discounts | [value] |
|     Cb Compliance-Amazon | [value] |
|     Cb Compliance-Big Lots | [value] |
|     Cb Compliance-Home Depot | [value] |
|     Cb Compliance-Kirklands | [value] |
|     Cb Compliance-Overstock | [value] |
|     Cb Compliance-Walmart | [value] |
|     Cb-Bealls Compliance Charge Back | [value] |
|     Cb-Compliance - Zulily | [value] |
|     Cb-Compliance -Others | [value] |
|     Cb-Compliance-Amazon Ca | [value] |
|     Cb-Compliance-Bed Bath | [value] |
|     Cb-Customer Compliance - Nfm | [value] |
|     Cb-Customer Compliance - Pottery Barn | [value] |
|     Cb-Damage Allowance | [value] |
|     Cb-Damage Allownace-Amazon | [value] |
|     Cb-Shipping Allowance | [value] |
|     Cb-Shipping Allowance-Amazon | [value] |
|     Cell Phone | [value] |
|     Charge Back | [value] |
|     Chargeback Customer Compliance | [value] |
|     Comm - Amy Bruce | [value] |
|     Comm - Ashutosh Laddha | [value] |
|     Comm - Bill Robertson | [value] |
|     Comm - Billy Waynerich | [value] |
|     Comm - Black Goswick | [value] |
|     Comm - Bridget Favaloro | [value] |
|     Comm - Charless Reason | [value] |
|     Comm - Christine Reagon | [value] |
|     Comm - Dan Statuto | [value] |
|     Comm - Daren Kozlowski | [value] |
|     Comm - David Mceleven | [value] |
|     Comm - Eric Fleat | [value] |
|     Comm - Jeanin Maxey | [value] |
|     Comm - Jim Caserio | [value] |
|     Comm - Jim Swan | [value] |
|     Comm - John Mccaul | [value] |
|     Comm - Joseph Gray | [value] |
|     Comm - Kim Susan White | [value] |
|     Comm - M K Inc. | [value] |
|     Comm - Marvin Junior | [value] |
|     Comm - Mike V. Kehnast | [value] |
|     Comm - Natalie Smith | [value] |
|     Comm  Peyton Gay | [value] |
|     Comm - Ramona D Myrick | [value] |
|     Comm - Reverse Atlanta | [value] |
|     Comm - Richard Leckbee | [value] |
|     Comm - Robin Grassi | [value] |
|     Comm - Russell Givens | [value] |
|     Comm - Taylor Malore | [value] |
|     Comm - Teressa Huff | [value] |
|     Comm - Tony Speirs | [value] |
|     Comm - Victor Hugo | [value] |
|     Comm- Emil Qirilla | [value] |
|     Comm -Mike Thomson | [value] |
|     Comm-Dointe Tyree Johnson | [value] |
|     Commi  - V-Von Sales | [value] |
|     Commi - Joe Barkley | [value] |
|     Commission | [value] |
|     Commission -Stacy Garcia | [value] |
|     Computer Accessories & Supplie | [value] |
|     Computer Server Restoration | [value] |
|     Designing And Development | [value] |
|     Donations | [value] |
|     Dues And Subscriptions | [value] |
|     Employee Benefit Plan Contribu | [value] |
|     Employee Insurances | [value] |
|     Employees Holiday Celeberation | [value] |
|     Fab Floors-Dues & Subscriptions | [value] |
|     General Expenses | [value] |
|     Insurance Administrative Fees | [value] |
|     Insurance-Auto | [value] |
|     Insurance-Commercial | [value] |
|     Insurance-Commercial Policies | [value] |
|     Insurance-Dental & Vision | [value] |
|     Insurance-Medical | [value] |
|     Insurance-Receivables Credit Coverage | [value] |
|     Insurance-Workmen'S Comp. | [value] |
|     Insurnace-Workmens Compensatio | [value] |
|     Internet & Cable | [value] |
|     Inventory Adjustment | [value] |
|     Misscellaneous | [value] |
|     Office Expenses | [value] |
|     Office Supplies | [value] |
|     Postage & Delivery | [value] |
|     Printing & Stationary | [value] |
|     Recruitment & Training | [value] |
|     Repairs & Maintance | [value] |
|     Royalties | [value] |
|     Royalties - Stacy Garcia | [value] |
|     Royalties -Evette Rios | [value] |
|     Royalties-London Fog | [value] |
|     Sample Mailing Charges | [value] |
|     Security Expenses | [value] |
|     Service Charge | [value] |
|     Small Balances Written Off | [value] |
|     Software Monthly Fees | [value] |
|     Software Upgrade & Maintainanc | [value] |
|     Supplement Insurance | [value] |
|     Telephone Expenses | [value] |
|     Use 6000-004 -Car Tag Renewal | [value] |
|     Use 8002-Bad Debt | [value] |
|     Use A/C 6020-000 Ware. Eqp Rep | [value] |
|     Utilities | [value] |
|     Utilities - Electricity, Gas & Water | [value] |
|     Utilities - Lawn Maintenance | [value] |
|     Utilities - Office Cleaning | [value] |
|     Utilities - Pest Control | [value] |
|     Utilities - Propane Gas Tanks | [value] |
|     Utilities - Security Monitoring | [value] |
|     Utilities - Trash Removal & Recycling | [value] |
|     Warehouse Equipment Repairs | [value] |
|     Warehouse Insurance | [value] |
|     404-749-4832 | [value] |
|     706-218-8089 -Cell Phone Vbl | [value] |
|     706-259-0155 -Lr Office | [value] |
|     706-280-4301-Chris | [value] |
|     706-280-5055 - Cell Phone Skl | [value] |
|     706-459-8358 -Cell Phone Rl | [value] |
|     706-483-1673 -Cell Phone Colle | [value] |
|     706-847-4479 -Vonage Office | [value] |
|     Edi Services | [value] |
|     Ele-.Equipment Lease Expenses | [value] |
|     Ele-Linde V15 Lease Expense | [value] |
|     Ele-Toshiba Printer Lease Expe | [value] |
|     Ele-Y2020 Servers Lease Expens | [value] |
|     Ele-Yale Picker Lease Expenses | [value] |
| **Total General & Administrative** | [computed] |

| | |
| **Selling Expenses** | |
|     401K-Lr Contribution | [value] |
|     Accounting | [value] |
|     Advertising Display Rack | [value] |
|     Advertising Expenses | [value] |
|     Advertising-Amazon | [value] |
|     Advertising-Faire | [value] |
|     Advertising-Home Depot | [value] |
|     Advertising-Houzz | [value] |
|     Advertising-Others | [value] |
|     Advertising-Overstock | [value] |
|     Advertising-Walmart | [value] |
|     Advertising-Wayfair | [value] |
|     Advertising-Wm Marketplace | [value] |
|     Advertising-Zulily | [value] |
|     Amortization | [value] |
|     Atlanta Showroom | [value] |
|     Atlanta Showroom Exp-Advt. | [value] |
|     Atlanta Showroom Expenses | [value] |
|     Atlanta Showroom Exp-Food | [value] |
|     Atlanta Showroom Exp-General | [value] |
|     Atlanta Showroom Exp-Hotel | [value] |
|     Atlanta Showroom Exp-Rent | [value] |
|     Atlanta Showroom Exp-Traval | [value] |
|     Atlanta Showroom Exp-Trucking | [value] |
|     Atlanta Showroom Exp-Utility | [value] |
|     Bad & Doubtful Debts | [value] |
|     Bonus | [value] |
|     Car Rental | [value] |
|     Catalog Printing-Mailing Exp. | [value] |
|     Consulting | [value] |
|     Depreciation Expense | [value] |
|     Dnu-User 7540-701-Adv Amazon | [value] |
|     Ecommerce Product Listing | [value] |
|     Exhibition | [value] |
|     FUTA | [value] |
|     Guest House Rent | [value] |
|     High Point - Advertising | [value] |
|     High Point - Food Expense | [value] |
|     High Point - General Expense | [value] |
|     High Point - Hotel Exepnse | [value] |
|     High Point - Rent Expense | [value] |
|     High Point - Showroom Expenses | [value] |
|     High Point - Travel Expense | [value] |
|     High Point - Trucking | [value] |
|     High Point - Utility Expense | [value] |
|     Hp Show.Rent Old A/C.Use 7612- | [value] |
|     L R 401K Contribution A/C | [value] |
|     Legal Fees | [value] |
|     Loss On Sale Of Assets | [value] |
|     Marketing Consultancy | [value] |
|     Marketing Consultancy - Joe Barkley | [value] |
|     Marketing Expenses | [value] |
|     Nfa Rebate | [value] |
|     Outs.-G.K.Laddha | [value] |
|     Outs.-Rajendra Maheshwari | [value] |
|     Outs.-Soumya Maheshwari | [value] |
|     Payroll | [value] |
|     Payroll Ss & Medicare | [value] |
|     Pocket Folders | [value] |
|     Pr - Amy Roberts | [value] |
|     Pr - Arthur M Thompson | [value] |
|     Pr - Eddie Davis | [value] |
|     Pr - G K Laddha | [value] |
|     Pr - Johnny Meendez | [value] |
|     Pr - Katika Hadden | [value] |
|     Pr - Kenneth R Morgan | [value] |
|     Pr - Krishna Laddha | [value] |
|     Pr - Mellisa Fowler | [value] |
|     Pr - Mellisa Johnson | [value] |
|     Pr - Paulene C Cochran | [value] |
|     Pr - Pratik Bhatter | [value] |
|     Pr - Rajani Laddha | [value] |
|     Pr - Seteve E Stultz | [value] |
|     Pr - Stacey Carpenter | [value] |
|     Pr - Tracy R Lovain | [value] |
|     Pr - Vaibhav Laddha | [value] |
|     Pr - Vinamra Laddha | [value] |
|     Pr - Zubair Faridi | [value] |
|     Product Photo Images Ai | [value] |
|     Professional Fees | [value] |
|     Promotional Expenses | [value] |
|     Promotional Expenses-Nebraska Furniture Mart | [value] |
|     Promotional Expenses-Ox Bay | [value] |
|     Promotional Expenses-Rc Willey | [value] |
|     Promotional Expenses-Wayfair | [value] |
|     Promotional Exp-Home Depot | [value] |
|     Provision For Expenses | [value] |
|     R.C. Willey Advertisement | [value] |
|     Rent | [value] |
|     Sampling Expense | [value] |
|     Social Media-Email Marketing | [value] |
|     Software Monthly Fee | [value] |
|     SUTA | [value] |
|     Travel Conveyance,Toll,Parking | [value] |
|     Travel Ticketing Exp Account | [value] |
|     Travel-Hotel Expense | [value] |
|     Traveling Expenses_Food | [value] |
|     Travel-Visa-Medical-Misc Exp. | [value] |
|     Use 6970-Business Cards | [value] |
|     Use 7730 - Visa Fees | [value] |
|     Warehouse Rent | [value] |
|     Warehouse Rent-Lr Realty | [value] |
|     Warehouse Rent-Lr2-3012 Parque | [value] |
|     Warehouse Rent-Lr3-3002 Parque | [value] |
|     Warehouse Rent-Lr4-3351 Box Dr | [value] |
|     Website | [value] |
|     Website - Ecom Data Management | [value] |
|     Websites Crawling-Uploading | [value] |
|     Weekends Only Advertisement | [value] |
|     Xtra | [value] |
| **Total Selling Expenses** | [computed] |
| | |
| **Total Operating Expenses** | [computed] |
| **Operating Profit /(Loss)** | [computed] |
| | |
| **Interest Expenses** | |
|     Bank Service Charge | [value] |
|     Bank Wire Transfer Charges | [value] |
|     Camry Interest -2013 | [value] |
|     Credit Card Interest & Fees | [value] |
|     Credit Card Payment Processing | [value] |
|     Drip Capital Loan Interest | [value] |
|     Eidl Loan Interest | [value] |
|     Fc-Interest On Lease | [value] |
|     Finance Charge | [value] |
|     Firstbank Interest | [value] |
|     Fistbank 2Nd Line Interest | [value] |
|     Import - Bank Document Collect | [value] |
|     Ltl Equip.2019 A/C 2570037503 | [value] |
|     Ltl-Equip.2021 A/C 2570065987 | [value] |
|     Mb-Eqb 300 Loan Interest A/C | [value] |
|     Mercedes Car- Interest A/C | [value] |
|     Other Interest-Financial Charg | [value] |
|     Prius Loan Interest - 2017 | [value] |
|     Prius Loan Interest -2016 | [value] |
|     Prius Loan Interest Expenses | [value] |
|     Regions Bank Int. On Eq Loan | [value] |
|     Regions Bank Interest | [value] |
|     Regions Loan Fees | [value] |
|     Sienna 2015 Loan Interest | [value] |
|     Warehouse Equipment Loan Inter | [value] |
| **Total Interest Expenses** | [computed] |
| | |
| **Other Income/Expenses** | |
|     Other Income | [value] |
|     Profit On Sale Of Asset | [value] |
|     OIN-PPP Loan Forgiven | [value] |
|     Other Income-Interest Received | [value] |
|     Restocking Fee | [value] |
|     Other Income-Bad Debts Recovered | [value] |
|     Abnormal Income | [value] |
|     Free To Use | [value] |
|     Interest Income | [value] |
| **Total Other Income/Expenses** | [computed] |
| | |
| **Taxes** | |
|     State | [value] |
|     Property Tax | [value] |
|     Licenses-Tax-Permit-Penalties | [value] |
|     Business Licenses & Permits | [value] |
|     Taxes | [value] |
| **Total Taxes** | [computed] |
| | |
| **Net Profit /(Loss)** | [computed] |

*P&L Detailed — Multi-Month (2+ months requested)*
(Same account-level structure but one amount column per month, side-by-side. Use SQL Example 12.)

| Description | [Month1 Year] ($) | [Month2 Year] ($) |
|:---|---:|---:|
| **Sales** | | |
|     Sales | [value] | [value] |
|     Sales Discount | [value] | [value] |
|     Sales Discount - Albertsons | [value] | [value] |
|     Sales Discount - Amz Marketplace | [value] | [value] |
|     Sales Discount - Bison Commerce | [value] | [value] |
|     Sales Discount - Bob'S Discount Ecomm A/C | [value] | [value] |
|     Sales Discount - Gordon Co | [value] | [value] |
|     Sales Discount - Home Depot Pr | [value] | [value] |
|     Sales Discount - Jc Penny | [value] | [value] |
|     Sales Discount - Lowe'S | [value] | [value] |
|     Sales Discount - Nebraska / Home Maker | [value] | [value] |
|     Sales Discount - Pier 1 | [value] | [value] |
|     Sales Discount - Rugs Direct | [value] | [value] |
|     Sales Discount - Wayfair Ca | [value] | [value] |
|     Sales Discount - Wm Marketplace | [value] | [value] |
|     Sales Discount - Zulily | [value] | [value] |
|     Sales Discount -Rug& Home Group | [value] | [value] |
|     Sales Discount -Weekends Only | [value] | [value] |
|     Sales Discount-Amazon | [value] | [value] |
|     Sales Discount-Amazon Ca | [value] | [value] |
|     Sales Discount-Ashley Furnit | [value] | [value] |
|     Sales Discount-Bealls | [value] | [value] |
|     Sales Discount-Bed Bath & Beyo | [value] | [value] |
|     Sales Discount-Cost Plus Wor | [value] | [value] |
|     Sales Discount-Faire | [value] | [value] |
|     Sales Discount-Groupon | [value] | [value] |
|     Sales Discount-Hayneedle | [value] | [value] |
|     Sales Discount-Home Depot | [value] | [value] |
|     Sales Discount-Home Roots | [value] | [value] |
|     Sales Discount-Kirkland | [value] | [value] |
|     Sales Discount-Macys | [value] | [value] |
|     Sales Discount-Menards | [value] | [value] |
|     Sales Discount-Mink & Sons | [value] | [value] |
|     Sales Discount-Old Time Potte | [value] | [value] |
|     Sales Discount-Others | [value] | [value] |
|     Sales Discount-Overstock | [value] | [value] |
|     Sales Discount-Plush Rugs | [value] | [value] |
|     Sales Discount-Pottery Barn | [value] | [value] |
|     Sales Discount-Qvc | [value] | [value] |
|     Sales Discount-Walmart | [value] | [value] |
|     Sales Discount-Wayfair | [value] | [value] |
|     Sales Returns (Not Received) | [value] | [value] |
|     Sales-Price Differences | [value] | [value] |
|     Sales-Short Shipment Deduction | [value] | [value] |
|     Serv-Drop Ship Fees | [value] | [value] |
|     Services & Other Charges | [value] | [value] |
|     Shipping & Handling | [value] | [value] |
|     Charge Back | [value] | [value] |
|     Claim Receipts From Customers | [value] | [value] |
|     Claim Receipts-Home Depot | [value] | [value] |
|     Prior Sales Returns | [value] | [value] |
|     Returns On Sales | [value] | [value] |
|     Returns Shipping & Service Cha | [value] | [value] |
| **Total Sales** | [computed] | [computed] |
| | | |
| **Cost Of Goods Sold** | | |
|     Cost Of Goods Sold | [value] | [value] |
|     Box Program Job Work Costs | [value] | [value] |
|     Damaged-Discarded Inventory | [value] | [value] |
|     Designing & Development Expens | [value] | [value] |
|     Dhl-Sample Mailing Expense | [value] | [value] |
|     Domestic Trucking Line Freight | [value] | [value] |
|     Domestic Trucking Line Freight - Lvt | [value] | [value] |
|     Fab Floors-Clearing & Forwarding Expense | [value] | [value] |
|     Fedex/Ups Additional Handling | [value] | [value] |
|     Fedex/Ups Shipping Expense | [value] | [value] |
|     Freight - Pillow-Poufs | [value] | [value] |
|     Freight Cap Promotions Expense | [value] | [value] |
|     Freight Costs-Replacements Etc | [value] | [value] |
|     Freight Damage Loss/Gain A/C | [value] | [value] |
|     Freight Discount On Lr | [value] | [value] |
|     Import - Prepaid Import Costs | [value] | [value] |
|     Import Clearing And Forwarding | [value] | [value] |
|     Import-Air Freight | [value] | [value] |
|     Import-Cargo Insurance | [value] | [value] |
|     Import-Container Storage -Detention Chgs | [value] | [value] |
|     Import-Container Truck Freight | [value] | [value] |
|     Import-Customs Clearance Cost | [value] | [value] |
|     Import-Customs Documents Chgs | [value] | [value] |
|     Import-Ocean Freight | [value] | [value] |
|     Import-State Custom Duty | [value] | [value] |
|     Import-Tariffs | [value] | [value] |
|     Insert - Pillow | [value] | [value] |
|     Insert Materials Cost | [value] | [value] |
|     Insert-Pouf / Pet Beds Filling | [value] | [value] |
|     Inventory Adjustment Account | [value] | [value] |
|     Labelling & Ticketing Expense | [value] | [value] |
|     Merchandising&Inspection Fee | [value] | [value] |
|     Obsolete Inventory | [value] | [value] |
|     Packing Expense | [value] | [value] |
|     Processing Charge | [value] | [value] |
|     Purchase Discount | [value] | [value] |
|     Rug Cleaning | [value] | [value] |
|     Rug Surging, Cutting,Repairng | [value] | [value] |
|     Temporary Labor Expenses | [value] | [value] |
|     Third Party Warehouse Charges | [value] | [value] |
|     Truck-Trailer Rent Costs | [value] | [value] |
|     Upc Code Purchase | [value] | [value] |
|     Us Customs Bond Fee | [value] | [value] |
|     Use 5051-004 Import  Duty | [value] | [value] |
|     Vendor Defective Reimbursement | [value] | [value] |
| **Total Cost Of Goods Sold** | [computed] | [computed] |
| | | |
| **Gross Profit/(Loss)** | [computed] | [computed] |
| | | |
| **Operating Expenses** | | |
| **General & Administrative** | | |
|     Auto Expenses | [value] | [value] |
|     Auto Expenses-Auto Insurance | [value] | [value] |
|     Auto Expenses-Fuel | [value] | [value] |
|     Auto Expenses-Repairs & Maint. | [value] | [value] |
|     Auto Expenses-Tag Fees Etc. | [value] | [value] |
|     Auto Reimbursement Exp ?? | [value] | [value] |
|     Car Insurance | [value] | [value] |
|     Cash Discounts | [value] | [value] |
|     Cb Compliance-Amazon | [value] | [value] |
|     Cb Compliance-Big Lots | [value] | [value] |
|     Cb Compliance-Home Depot | [value] | [value] |
|     Cb Compliance-Kirklands | [value] | [value] |
|     Cb Compliance-Overstock | [value] | [value] |
|     Cb Compliance-Walmart | [value] | [value] |
|     Cb-Bealls Compliance Charge Back | [value] | [value] |
|     Cb-Compliance - Zulily | [value] | [value] |
|     Cb-Compliance -Others | [value] | [value] |
|     Cb-Compliance-Amazon Ca | [value] | [value] |
|     Cb-Compliance-Bed Bath | [value] | [value] |
|     Cb-Customer Compliance - Nfm | [value] | [value] |
|     Cb-Customer Compliance - Pottery Barn | [value] | [value] |
|     Cb-Damage Allowance | [value] | [value] |
|     Cb-Damage Allownace-Amazon | [value] | [value] |
|     Cb-Shipping Allowance | [value] | [value] |
|     Cb-Shipping Allowance-Amazon | [value] | [value] |
|     Cell Phone | [value] | [value] |
|     Charge Back | [value] | [value] |
|     Chargeback Customer Compliance | [value] | [value] |
|     Comm - Amy Bruce | [value] | [value] |
|     Comm - Ashutosh Laddha | [value] | [value] |
|     Comm - Bill Robertson | [value] | [value] |
|     Comm - Billy Waynerich | [value] | [value] |
|     Comm - Black Goswick | [value] | [value] |
|     Comm - Bridget Favaloro | [value] | [value] |
|     Comm - Charless Reason | [value] | [value] |
|     Comm - Christine Reagon | [value] | [value] |
|     Comm - Dan Statuto | [value] | [value] |
|     Comm - Daren Kozlowski | [value] | [value] |
|     Comm - David Mceleven | [value] | [value] |
|     Comm - Eric Fleat | [value] | [value] |
|     Comm - Jeanin Maxey | [value] | [value] |
|     Comm - Jim Caserio | [value] | [value] |
|     Comm - Jim Swan | [value] | [value] |
|     Comm - John Mccaul | [value] | [value] |
|     Comm - Joseph Gray | [value] | [value] |
|     Comm - Kim Susan White | [value] | [value] |
|     Comm - M K Inc. | [value] | [value] |
|     Comm - Marvin Junior | [value] | [value] |
|     Comm - Mike V. Kehnast | [value] | [value] |
|     Comm - Natalie Smith | [value] | [value] |
|     Comm  Peyton Gay | [value] | [value] |
|     Comm - Ramona D Myrick | [value] | [value] |
|     Comm - Reverse Atlanta | [value] | [value] |
|     Comm - Richard Leckbee | [value] | [value] |
|     Comm - Robin Grassi | [value] | [value] |
|     Comm - Russell Givens | [value] | [value] |
|     Comm - Taylor Malore | [value] | [value] |
|     Comm - Teressa Huff | [value] | [value] |
|     Comm - Tony Speirs | [value] | [value] |
|     Comm - Victor Hugo | [value] | [value] |
|     Comm- Emil Qirilla | [value] | [value] |
|     Comm -Mike Thomson | [value] | [value] |
|     Comm-Dointe Tyree Johnson | [value] | [value] |
|     Commi  - V-Von Sales | [value] | [value] |
|     Commi - Joe Barkley | [value] | [value] |
|     Commission | [value] | [value] |
|     Commission -Stacy Garcia | [value] | [value] |
|     Computer Accessories & Supplie | [value] | [value] |
|     Computer Server Restoration | [value] | [value] |
|     Designing And Development | [value] | [value] |
|     Donations | [value] | [value] |
|     Dues And Subscriptions | [value] | [value] |
|     Employee Benefit Plan Contribu | [value] | [value] |
|     Employee Insurances | [value] | [value] |
|     Employees Holiday Celeberation | [value] | [value] |
|     Fab Floors-Dues & Subscriptions | [value] | [value] |
|     General Expenses | [value] | [value] |
|     Insurance Administrative Fees | [value] | [value] |
|     Insurance-Auto | [value] | [value] |
|     Insurance-Commercial | [value] | [value] |
|     Insurance-Commercial Policies | [value] | [value] |
|     Insurance-Dental & Vision | [value] | [value] |
|     Insurance-Medical | [value] | [value] |
|     Insurance-Receivables Credit Coverage | [value] | [value] |
|     Insurance-Workmen'S Comp. | [value] | [value] |
|     Insurnace-Workmens Compensatio | [value] | [value] |
|     Internet & Cable | [value] | [value] |
|     Inventory Adjustment | [value] | [value] |
|     Misscellaneous | [value] | [value] |
|     Office Expenses | [value] | [value] |
|     Office Supplies | [value] | [value] |
|     Postage & Delivery | [value] | [value] |
|     Printing & Stationary | [value] | [value] |
|     Recruitment & Training | [value] | [value] |
|     Repairs & Maintance | [value] | [value] |
|     Royalties | [value] | [value] |
|     Royalties - Stacy Garcia | [value] | [value] |
|     Royalties -Evette Rios | [value] | [value] |
|     Royalties-London Fog | [value] | [value] |
|     Sample Mailing Charges | [value] | [value] |
|     Security Expenses | [value] | [value] |
|     Service Charge | [value] | [value] |
|     Small Balances Written Off | [value] | [value] |
|     Software Monthly Fees | [value] | [value] |
|     Software Upgrade & Maintainanc | [value] | [value] |
|     Supplement Insurance | [value] | [value] |
|     Telephone Expenses | [value] | [value] |
|     Use 6000-004 -Car Tag Renewal | [value] | [value] |
|     Use 8002-Bad Debt | [value] | [value] |
|     Use A/C 6020-000 Ware. Eqp Rep | [value] | [value] |
|     Utilities | [value] | [value] |
|     Utilities - Electricity, Gas & Water | [value] | [value] |
|     Utilities - Lawn Maintenance | [value] | [value] |
|     Utilities - Office Cleaning | [value] | [value] |
|     Utilities - Pest Control | [value] | [value] |
|     Utilities - Propane Gas Tanks | [value] | [value] |
|     Utilities - Security Monitoring | [value] | [value] |
|     Utilities - Trash Removal & Recycling | [value] | [value] |
|     Warehouse Equipment Repairs | [value] | [value] |
|     Warehouse Insurance | [value] | [value] |
|     404-749-4832 | [value] | [value] |
|     706-218-8089 -Cell Phone Vbl | [value] | [value] |
|     706-259-0155 -Lr Office | [value] | [value] |
|     706-280-4301-Chris | [value] | [value] |
|     706-280-5055 - Cell Phone Skl | [value] | [value] |
|     706-459-8358 -Cell Phone Rl | [value] | [value] |
|     706-483-1673 -Cell Phone Colle | [value] | [value] |
|     706-847-4479 -Vonage Office | [value] | [value] |
|     Edi Services | [value] | [value] |
|     Ele-.Equipment Lease Expenses | [value] | [value] |
|     Ele-Linde V15 Lease Expense | [value] | [value] |
|     Ele-Toshiba Printer Lease Expe | [value] | [value] |
|     Ele-Y2020 Servers Lease Expens | [value] | [value] |
|     Ele-Yale Picker Lease Expenses | [value] | [value] |
| **Total General & Administrative** | [computed] | [computed] |
| | | |
| **Selling Expenses** | | |
|     401K-Lr Contribution | [value] | [value] |
|     Accounting | [value] | [value] |
|     Advertising Display Rack | [value] | [value] |
|     Advertising Expenses | [value] | [value] |
|     Advertising-Amazon | [value] | [value] |
|     Advertising-Faire | [value] | [value] |
|     Advertising-Home Depot | [value] | [value] |
|     Advertising-Houzz | [value] | [value] |
|     Advertising-Others | [value] | [value] |
|     Advertising-Overstock | [value] | [value] |
|     Advertising-Walmart | [value] | [value] |
|     Advertising-Wayfair | [value] | [value] |
|     Advertising-Wm Marketplace | [value] | [value] |
|     Advertising-Zulily | [value] | [value] |
|     Amortization | [value] | [value] |
|     Atlanta Showroom | [value] | [value] |
|     Atlanta Showroom Exp-Advt. | [value] | [value] |
|     Atlanta Showroom Expenses | [value] | [value] |
|     Atlanta Showroom Exp-Food | [value] | [value] |
|     Atlanta Showroom Exp-General | [value] | [value] |
|     Atlanta Showroom Exp-Hotel | [value] | [value] |
|     Atlanta Showroom Exp-Rent | [value] | [value] |
|     Atlanta Showroom Exp-Traval | [value] | [value] |
|     Atlanta Showroom Exp-Trucking | [value] | [value] |
|     Atlanta Showroom Exp-Utility | [value] | [value] |
|     Bad & Doubtful Debts | [value] | [value] |
|     Bonus | [value] | [value] |
|     Car Rental | [value] | [value] |
|     Catalog Printing-Mailing Exp. | [value] | [value] |
|     Consulting | [value] | [value] |
|     Depreciation Expense | [value] | [value] |
|     Dnu-User 7540-701-Adv Amazon | [value] | [value] |
|     Ecommerce Product Listing | [value] | [value] |
|     Exhibition | [value] | [value] |
|     FUTA | [value] | [value] |
|     Guest House Rent | [value] | [value] |
|     High Point - Advertising | [value] | [value] |
|     High Point - Food Expense | [value] | [value] |
|     High Point - General Expense | [value] | [value] |
|     High Point - Hotel Exepnse | [value] | [value] |
|     High Point - Rent Expense | [value] | [value] |
|     High Point - Showroom Expenses | [value] | [value] |
|     High Point - Travel Expense | [value] | [value] |
|     High Point - Trucking | [value] | [value] |
|     High Point - Utility Expense | [value] | [value] |
|     Hp Show.Rent Old A/C.Use 7612- | [value] | [value] |
|     L R 401K Contribution A/C | [value] | [value] |
|     Legal Fees | [value] | [value] |
|     Loss On Sale Of Assets | [value] | [value] |
|     Marketing Consultancy | [value] | [value] |
|     Marketing Consultancy - Joe Barkley | [value] | [value] |
|     Marketing Expenses | [value] | [value] |
|     Nfa Rebate | [value] | [value] |
|     Outs.-G.K.Laddha | [value] | [value] |
|     Outs.-Rajendra Maheshwari | [value] | [value] |
|     Outs.-Soumya Maheshwari | [value] | [value] |
|     Payroll | [value] | [value] |
|     Payroll Ss & Medicare | [value] | [value] |
|     Pocket Folders | [value] | [value] |
|     Pr - Amy Roberts | [value] | [value] |
|     Pr - Arthur M Thompson | [value] | [value] |
|     Pr - Eddie Davis | [value] | [value] |
|     Pr - G K Laddha | [value] | [value] |
|     Pr - Johnny Meendez | [value] | [value] |
|     Pr - Katika Hadden | [value] | [value] |
|     Pr - Kenneth R Morgan | [value] | [value] |
|     Pr - Krishna Laddha | [value] | [value] |
|     Pr - Mellisa Fowler | [value] | [value] |
|     Pr - Mellisa Johnson | [value] | [value] |
|     Pr - Paulene C Cochran | [value] | [value] |
|     Pr - Pratik Bhatter | [value] | [value] |
|     Pr - Rajani Laddha | [value] | [value] |
|     Pr - Seteve E Stultz | [value] | [value] |
|     Pr - Stacey Carpenter | [value] | [value] |
|     Pr - Tracy R Lovain | [value] | [value] |
|     Pr - Vaibhav Laddha | [value] | [value] |
|     Pr - Vinamra Laddha | [value] | [value] |
|     Pr - Zubair Faridi | [value] | [value] |
|     Product Photo Images Ai | [value] | [value] |
|     Professional Fees | [value] | [value] |
|     Promotional Expenses | [value] | [value] |
|     Promotional Expenses-Nebraska Furniture Mart | [value] | [value] |
|     Promotional Expenses-Ox Bay | [value] | [value] |
|     Promotional Expenses-Rc Willey | [value] | [value] |
|     Promotional Expenses-Wayfair | [value] | [value] |
|     Promotional Exp-Home Depot | [value] | [value] |
|     Provision For Expenses | [value] | [value] |
|     R.C. Willey Advertisement | [value] | [value] |
|     Rent | [value] | [value] |
|     Sampling Expense | [value] | [value] |
|     Social Media-Email Marketing | [value] | [value] |
|     Software Monthly Fee | [value] | [value] |
|     SUTA | [value] | [value] |
|     Travel Conveyance,Toll,Parking | [value] | [value] |
|     Travel Ticketing Exp Account | [value] | [value] |
|     Travel-Hotel Expense | [value] | [value] |
|     Traveling Expenses_Food | [value] | [value] |
|     Travel-Visa-Medical-Misc Exp. | [value] | [value] |
|     Use 6970-Business Cards | [value] | [value] |
|     Use 7730 - Visa Fees | [value] | [value] |
|     Warehouse Rent | [value] | [value] |
|     Warehouse Rent-Lr Realty | [value] | [value] |
|     Warehouse Rent-Lr2-3012 Parque | [value] | [value] |
|     Warehouse Rent-Lr3-3002 Parque | [value] | [value] |
|     Warehouse Rent-Lr4-3351 Box Dr | [value] | [value] |
|     Website | [value] | [value] |
|     Website - Ecom Data Management | [value] | [value] |
|     Websites Crawling-Uploading | [value] | [value] |
|     Weekends Only Advertisement | [value] | [value] |
|     Xtra | [value] | [value] |
| **Total Selling Expenses** | [computed] | [computed] |
| | | |
| **Total Operating Expenses** | [computed] | [computed] |
| **Operating Profit /(Loss)** | [computed] | [computed] |
| | | |
| **Interest Expenses** | | |
|     Bank Service Charge | [value] | [value] |
|     Bank Wire Transfer Charges | [value] | [value] |
|     Camry Interest -2013 | [value] | [value] |
|     Credit Card Interest & Fees | [value] | [value] |
|     Credit Card Payment Processing | [value] | [value] |
|     Drip Capital Loan Interest | [value] | [value] |
|     Eidl Loan Interest | [value] | [value] |
|     Fc-Interest On Lease | [value] | [value] |
|     Finance Charge | [value] | [value] |
|     Firstbank Interest | [value] | [value] |
|     Fistbank 2Nd Line Interest | [value] | [value] |
|     Import - Bank Document Collect | [value] | [value] |
|     Ltl Equip.2019 A/C 2570037503 | [value] | [value] |
|     Ltl-Equip.2021 A/C 2570065987 | [value] | [value] |
|     Mb-Eqb 300 Loan Interest A/C | [value] | [value] |
|     Mercedes Car- Interest A/C | [value] | [value] |
|     Other Interest-Financial Charg | [value] | [value] |
|     Prius Loan Interest - 2017 | [value] | [value] |
|     Prius Loan Interest -2016 | [value] | [value] |
|     Prius Loan Interest Expenses | [value] | [value] |
|     Regions Bank Int. On Eq Loan | [value] | [value] |
|     Regions Bank Interest | [value] | [value] |
|     Regions Loan Fees | [value] | [value] |
|     Sienna 2015 Loan Interest | [value] | [value] |
|     Warehouse Equipment Loan Inter | [value] | [value] |
| **Total Interest Expenses** | [computed] | [computed] |
| | | |
| **Other Income/Expenses** | | |
|     Other Income | [value] | [value] |
|     Profit On Sale Of Asset | [value] | [value] |
|     OIN-PPP Loan Forgiven | [value] | [value] |
|     Other Income-Interest Received | [value] | [value] |
|     Restocking Fee | [value] | [value] |
|     Other Income-Bad Debts Recovered | [value] | [value] |
|     Abnormal Income | [value] | [value] |
|     Free To Use | [value] | [value] |
|     Interest Income | [value] | [value] |
| **Total Other Income/Expenses** | [computed] | [computed] |
| | | |
| **Taxes** | | |
|     State | [value] | [value] |
|     Property Tax | [value] | [value] |
|     Licenses-Tax-Permit-Penalties | [value] | [value] |
|     Business Licenses & Permits | [value] | [value] |
|     Taxes | [value] | [value] |
| **Total Taxes** | [computed] | [computed] |
| | | |
| **Net Profit /(Loss)** | [computed] | [computed] |


================================================================
      FEW-SHOT EXAMPLES (FOLLOW EXACT PATTERN)
================================================================

================================================================
  MULTI-MONTH PRESENTATION RULE (MANDATORY)
================================================================
When a request covers MORE THAN ONE month (e.g. "April 2024 to May 2024",
"compare March vs April", "Q1 2024", "last 3 months"), you MUST:
  1. Use the multi-month SQL examples (7–12) with conditional aggregation.
  2. Present a SINGLE unified table where:
       - First column  = Description / Account name
       - Remaining columns = one per month, labelled [MonthName Year ($)]
  3. NEVER repeat the full statement twice (once per month). One table only.
  4. Still compute and show subtotals / section totals in every month column.

Example 2-month table layout (use this exact structure for ALL 6 templates):

| Description | April 2024 ($) | May 2024 ($) |
|:---|---:|---:|
| **Assets** | | |
| **Current Assets** | | |
| **Accounts Receivable** | | |
|     ACCOUNT RECEIVABLE | [value] | [value] |
| **Total Current Assets** | [computed] | [computed] |
| **Total Assets** | [computed] | [computed] |
| | | |
| **Liabilities & Equity** | | |
| **Total Liabilities & Equity** | [computed] | [computed] |

================================================================

================================================================
  ANNUAL / MULTI-YEAR PRESENTATION RULE (MANDATORY)
================================================================
When a request covers FULL YEARS or compares multiple years (e.g.
"annual P&L for 2023 and 2024", "compare 2022 vs 2023 vs 2024",
"yearly balance sheet", "3-year trend", "2023–2025"), you MUST:

SQL RULES:
  1. For P&L / Income Statement: aggregate using SUM(FAM.PTD_Net * -1)
     and GROUP BY DD.Year. Do NOT use ClosingBalance for P&L.
  2. For Balance Sheet: use ClosingBalance for December (Month=12) of each year,
     or the last available month of each year.
  3. Add DD.Year to the SELECT and GROUP BY — one row per [line item + year].
  4. Filter: WHERE DD.Year IN (year1, year2, ...) — list all requested years.

PRESENTATION RULES (CRITICAL — NEVER dump raw SQL rows):
  1. PIVOT the SQL result into a SINGLE unified table where:
       - First column  = Description (line item / account name)
       - Remaining columns = one per YEAR, labelled [YYYY ($)]
  2. NEVER output one row per (line item, year) pair — that is the raw SQL
     result format and must NOT be shown to the user.
  3. NEVER produce a header like "| Description | 2023 ($) | 2024 ($) |"
     and then put raw SQL rows with 4 columns underneath it. The number of
     data columns MUST match the number of header columns exactly.
  4. Each line item appears EXACTLY ONCE as a row, with each year's value
     in its own column — the same pivot logic used for multi-month tables.
  5. Still compute and show all subtotals / section totals for every year column.
  6. Format all numbers with commas and 2 decimal places (e.g. 1,234,567.89).
     Show negative values as negative (e.g. -885,898.77).

Example 3-year P&L Sub Grouped layout (apply same logic to ALL templates):

| Description | 2023 ($) | 2024 ($) | 2025 ($) |
|:---|---:|---:|---:|
| **Sales** | | | |
|     Gross Sales | 14,180,958.87 | 11,954,540.29 | 13,335,853.04 |
|     Discount | -885,898.77 | -641,485.38 | -591,203.15 |
|     Returns | -374,441.88 | -483,414.52 | -540,336.59 |
|     SHIPPING & HANDLING | 296,226.57 | 403,096.11 | 706,504.57 |
|     (... other Sales sub-groups ...) | [value] | [value] | [value] |
| **Total Sales** | [computed] | [computed] | [computed] |
| | | | |
| **Cost Of Goods Sold** | | | |
|     Cost of Goods Sold | -6,937,928.37 | -5,354,339.69 | -6,058,195.36 |
|     Freight | -337,360.62 | -382,890.92 | -713,295.51 |
|     (... other COGS sub-groups ...) | [value] | [value] | [value] |
| **Total Cost Of Goods Sold** | [computed] | [computed] | [computed] |
| | | | |
| **Gross Profit/(Loss)** | [computed] | [computed] | [computed] |
| | | | |
| **Operating Expenses** | | | |
| **General & Administrative** | | | |
|     Commission | -333,375.87 | -332,887.07 | -592,920.14 |
|     (... other G&A sub-groups ...) | [value] | [value] | [value] |
| **Total General & Administrative** | [computed] | [computed] | [computed] |
| | | | |
| **Selling Expenses** | | | |
|     Payroll | -1,715,380.03 | -1,620,770.11 | -1,685,327.49 |
|     Marketing Expenses | -607,404.13 | -624,350.31 | -644,039.24 |
|     (... other Selling sub-groups ...) | [value] | [value] | [value] |
| **Total Selling Expenses** | [computed] | [computed] | [computed] |
| | | | |
| **Total Operating Expenses** | [computed] | [computed] | [computed] |
| **Operating Profit /(Loss)** | [computed] | [computed] | [computed] |
| | | | |
| **Interest Expenses** | -414,636.60 | -467,563.52 | -413,787.39 |
| **Other Income/Expenses** | 0.00 | 0.77 | 21,984.66 |
| **Taxes** | -8,875.25 | -9,409.97 | -8,223.21 |
| **Net Profit /(Loss)** | [computed] | [computed] | [computed] |

SAME RULE APPLIES TO ALL OTHER MULTI-PERIOD COMPARISONS:
  - Quarterly comparisons (Q1 vs Q2 vs Q3 vs Q4): one column per quarter,
    labelled [Q1 YYYY ($)], [Q2 YYYY ($)], etc.
  - Half-year comparisons (H1 vs H2): one column per half, labelled
    [H1 YYYY ($)], [H2 YYYY ($)].
  - Any aggregation period: the column header describes the period,
    but the row structure is always a single pivoted table — NEVER raw SQL rows.

================================================================

--- Financial Statement Example 1: Balance Sheet Main Grouped (VERIFIED) ---
Question: "Show me the balance sheet" / "Balance sheet main grouped" / "Balance sheet summary" / "Balance sheet for [month] [year]"
-- Main Grouped: Section = Assets/L&E derived from Main column; Line Item = BalanceSheet_MainGroups values (Current Assets, Non Current Assets, Current Liabilities, Non Current Liabilities, Equity, Retained Earnings, Contribution, Distributions, Profit & Loss)
-- Returns multiple rows per section — NOT just 2 rows. Each BalanceSheet_MainGroups value is one line item under its section.
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Section],
    CM.BalanceSheet_MainGroups                                                        AS [Line Item],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END)                                             AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_MainGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_MainGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups
ORDER BY [Section], [Line Item]

--- Financial Statement Example 2: Balance Sheet Sub Grouped (VERIFIED) ---
Question: "Balance sheet sub grouped" / "Grouped balance sheet" / "Balance sheet with sub groups"
-- Sub Grouped: Section = Assets/L&E, Sub Group = BalanceSheet_MainGroups (section header), Line Item = BalanceSheet_SubGroups values
-- Returns rows like: Assets | Current Assets | Accounts Receivable | [value]
-- Sub Groups under Assets: Current Assets (8 items), Non Current Assets (10 items)
-- Sub Groups under Liabilities & Equity: Current Liabilities (9 items), Non Current Liabilities (4 items), Equity (4 items), Retained Earnings (2 items), Contribution (3 items)
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Section],
    CM.BalanceSheet_MainGroups                                                        AS [Sub Group],
    CM.BalanceSheet_SubGroups                                                         AS [Line Item],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END)                                             AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_SubGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_SubGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups
ORDER BY [Section], [Sub Group], [Line Item]

--- Financial Statement Example 3: Balance Sheet Detailed (VERIFIED) ---
Question: "Detailed balance sheet" / "Balance sheet detail" / "Full balance sheet"
-- Detailed = Assets/Liabilities + BalanceSheet_MainGroups + BalanceSheet_SubGroups + BalanceSheet_Details (individual accounts)
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Main Group],
    CM.BalanceSheet_MainGroups                                                        AS [Sub Group],
    CM.BalanceSheet_SubGroups                                                         AS [Detail Group],
    CM.BalanceSheet_Details                                                           AS [Account],
    SUM(CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000
             THEN FAM.ClosingBalance * -1
             ELSE FAM.ClosingBalance END)                                             AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE DD.Year  = YEAR(GETDATE())
  AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
  AND CM.BalanceSheet_Details IS NOT NULL
  AND CM.BalanceSheet_Details <> ''
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups, CM.BalanceSheet_Details
ORDER BY [Main Group], [Sub Group], [Detail Group], [Account]

--- Financial Statement Example 7: Balance Sheet Main Grouped MULTI-MONTH (VERIFIED) ---
Question: "Balance sheet from April 2024 to May 2024" / "Balance sheet for [month1] and [month2]" / "Compare balance sheet [month] vs [month]" / "Balance sheet [month] [year] to [month] [year]"
-- RULE: When multiple months are requested, use conditional aggregation — ONE column per month. NEVER add PeriodStartDate to GROUP BY. NEVER return a tall table.
-- Column names = month+year label e.g. [April 2024], [May 2024]. PeriodStartDate = first day of month 'YYYY-MM-01'.
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Section],
    CM.BalanceSheet_MainGroups                                                        AS [Line Item],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.BalanceSheet_MainGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_MainGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups
ORDER BY [Section], [Line Item]

--- Financial Statement Example 8: Balance Sheet Sub Grouped MULTI-MONTH (VERIFIED) ---
Question: "Balance sheet sub grouped from [month1] to [month2]" / "Sub grouped balance sheet comparison [month] vs [month]"
-- RULE: Conditional aggregation — one column per month, PeriodStartDate NOT in GROUP BY.
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Section],
    CM.BalanceSheet_MainGroups                                                        AS [Sub Group],
    CM.BalanceSheet_SubGroups                                                         AS [Line Item],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.BalanceSheet_SubGroups IS NOT NULL
  AND LEN(CM.BalanceSheet_SubGroups) > 0
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups
ORDER BY [Section], [Sub Group], [Line Item]

--- Financial Statement Example 9: Balance Sheet Detailed MULTI-MONTH (VERIFIED) ---
Question: "Detailed balance sheet from [month1] to [month2]" / "Full balance sheet [month] vs [month]" / "Detailed balance sheet [month] [year] and [month] [year]"
-- RULE: Conditional aggregation — one column per month, PeriodStartDate NOT in GROUP BY.
SELECT
    CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
         ELSE 'Liabilities & Equity' END                                              AS [Main Group],
    CM.BalanceSheet_MainGroups                                                        AS [Sub Group],
    CM.BalanceSheet_SubGroups                                                         AS [Detail Group],
    CM.BalanceSheet_Details                                                           AS [Account],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01'
             THEN CASE WHEN TRY_CAST(CM.Main AS INT) >= 2000 THEN FAM.ClosingBalance * -1 ELSE FAM.ClosingBalance END
             ELSE 0 END)                                                              AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
JOIN DimDate DD    ON FAM.DateKey   = DD.DateKey
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.BalanceSheet_Details IS NOT NULL
  AND CM.BalanceSheet_Details <> ''
GROUP BY CASE WHEN TRY_CAST(CM.Main AS INT) < 2000 THEN 'Assets'
              ELSE 'Liabilities & Equity' END,
         CM.BalanceSheet_MainGroups, CM.BalanceSheet_SubGroups, CM.BalanceSheet_Details
ORDER BY [Main Group], [Sub Group], [Detail Group], [Account]

--- Financial Statement Example 4: P&L / Income Statement Main Grouped (VERIFIED) ---
Question: "Show me the P&L" / "Income statement" / "Profit and loss" / "P&L main grouped" / "Income statement for [month] [year]" / "Profit and loss summary" / "Grouped P&L"
-- Use PTD_Net * -1 (NEVER YTD_Net). Filter on FAM.PeriodStartDate directly — do NOT use DimDate join or DateKey for P&L.
-- Returns up to 7 groups: Sales, Cost Of Goods Sold, General & Administrative, Selling Expenses, Finance Charges, Other Income/Expense, Taxes
-- Bot must compute: Gross Profit = Sales + Cost Of Goods Sold; Total Operating Expenses = G&A + Selling; Operating Profit = Gross Profit - Total Operating Expenses; Net Profit = Operating Profit + Interest Expenses + Other Income/Expenses + Taxes
-- CRITICAL: Map SQL group names to display names: "Finance Charges" → display as "Interest Expenses"; "Other Income/Expense" → display as "Other Income/Expenses"; G&A + Selling → grouped under "Operating Expenses". Show 0.00 for groups with no data.
-- Present in this fixed order: Sales → Cost Of Goods Sold → Gross Profit → Operating Expenses section → Total Operating Expenses → Operating Profit → Interest Expenses → Other Income/Expenses → Taxes → Net Profit
SELECT
    CM.PLStatementMainGroups                  AS [Group],
    SUM(FAM.PTD_Net * -1)                     AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate = DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0)
  AND CM.PLStatementMainGroups IS NOT NULL
  AND LEN(CM.PLStatementMainGroups) > 0
GROUP BY CM.PLStatementMainGroups
ORDER BY CM.PLStatementMainGroups

--- Financial Statement Example 5: P&L / Income Statement Sub Grouped (VERIFIED) ---
Question: "P&L sub grouped" / "Income statement sub grouped" / "P&L with sub groups" / "Detailed income statement by category" / "Profit and loss sub grouped"
-- Returns [Main Group, Sub Group, Amount]. Bot must present hierarchy with section totals and computed lines.
-- Filter on FAM.PeriodStartDate directly — do NOT use DimDate join or DateKey for P&L.
SELECT
    CM.PLStatementMainGroups                  AS [Main Group],
    CM.PLStatementSubGroups                   AS [Sub Group],
    SUM(FAM.PTD_Net * -1)                     AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate = DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0)
  AND CM.PLStatementSubGroups IS NOT NULL
  AND LEN(CM.PLStatementSubGroups) > 0
GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups
ORDER BY CM.PLStatementMainGroups, CM.PLStatementSubGroups

--- Financial Statement Example 6: P&L / Income Statement Detailed (VERIFIED) ---
Question: "Detailed P&L" / "Detailed income statement" / "Full income statement" / "Full P&L" / "Detailed profit and loss"
-- Returns [Main Group, Sub Group, Account, Amount]. 3-level nesting. Bot must compute totals and computed lines.
-- Filter on FAM.PeriodStartDate directly — do NOT use DimDate join or DateKey for P&L.
SELECT
    CM.PLStatementMainGroups                  AS [Main Group],
    CM.PLStatementSubGroups                   AS [Sub Group],
    CM.PLStatementDetails                     AS [Account],
    SUM(FAM.PTD_Net * -1)                     AS [Amount]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate = DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0)
  AND CM.PLStatementDetails IS NOT NULL
  AND LEN(CM.PLStatementDetails) > 0
GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups, CM.PLStatementDetails
ORDER BY CM.PLStatementMainGroups, CM.PLStatementSubGroups, CM.PLStatementDetails

--- Financial Statement Example 10: P&L Main Grouped MULTI-MONTH (VERIFIED) ---
Question: "P&L from April 2024 to May 2024" / "Income statement for [month1] and [month2]" / "Compare P&L [month] vs [month]" / "Profit and loss [month] [year] to [month] [year]"
-- RULE: When multiple months are requested, use conditional aggregation — ONE column per month. NEVER add PeriodStartDate to GROUP BY. Filter: PeriodStartDate IN (...). Use PTD_Net * -1.
-- Column names = month+year label e.g. [April 2024], [May 2024]. PeriodStartDate = first day of month 'YYYY-MM-01'.
-- CRITICAL: Map SQL group names to display names: "Finance Charges" → "Interest Expenses"; "Other Income/Expense" → "Other Income/Expenses"; G&A + Selling → grouped under "Operating Expenses". Never rename "Cost Of Goods Sold" or "Taxes".
SELECT
    CM.PLStatementMainGroups                  AS [Group],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.PLStatementMainGroups IS NOT NULL
  AND LEN(CM.PLStatementMainGroups) > 0
GROUP BY CM.PLStatementMainGroups
ORDER BY CM.PLStatementMainGroups

--- Financial Statement Example 11: P&L Sub Grouped MULTI-MONTH (VERIFIED) ---
Question: "P&L sub grouped from [month1] to [month2]" / "Income statement sub grouped [month] vs [month]"
-- RULE: Conditional aggregation — one column per month, PeriodStartDate NOT in GROUP BY. Use PTD_Net * -1.
SELECT
    CM.PLStatementMainGroups                  AS [Main Group],
    CM.PLStatementSubGroups                   AS [Sub Group],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.PLStatementSubGroups IS NOT NULL
  AND LEN(CM.PLStatementSubGroups) > 0
GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups
ORDER BY CM.PLStatementMainGroups, CM.PLStatementSubGroups

--- Financial Statement Example 12: P&L Detailed MULTI-MONTH (VERIFIED) ---
Question: "Detailed P&L from [month1] to [month2]" / "Full income statement [month] vs [month]" / "Detailed profit and loss [month] [year] and [month] [year]"
-- RULE: Conditional aggregation — one column per month, PeriodStartDate NOT in GROUP BY. Use PTD_Net * -1.
SELECT
    CM.PLStatementMainGroups                  AS [Main Group],
    CM.PLStatementSubGroups                   AS [Sub Group],
    CM.PLStatementDetails                     AS [Account],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-04-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [April 2024],
    SUM(CASE WHEN FAM.PeriodStartDate = '2024-05-01' THEN FAM.PTD_Net * -1 ELSE 0 END)  AS [May 2024]
FROM FactAccountMonthlySummary FAM
JOIN COAMaping CM ON FAM.AccountID = CM.AccountID
WHERE FAM.PeriodStartDate IN ('2024-04-01', '2024-05-01')
  AND CM.PLStatementDetails IS NOT NULL
  AND LEN(CM.PLStatementDetails) > 0
GROUP BY CM.PLStatementMainGroups, CM.PLStatementSubGroups, CM.PLStatementDetails
ORDER BY CM.PLStatementMainGroups, CM.PLStatementSubGroups, CM.PLStatementDetails

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

--- Example 15: Latest available month YoY revenue loss per customer (optimized — no cross-join, index-friendly) ---
Question: "Calculate total monthly revenue loss across all major accounts based on latest available month vs same month last year"
-- Last complete month = previous calendar month (e.g. March 2026 when today is April 2026)
-- DATEADD(MONTH,-1,GETDATE()) resolves to a scalar constant — SQL Server can use index seeks directly
WITH RevenueByAccount AS (
    SELECT
        DC.CustomerID,
        DC.CustomerName,
        DD.Year,
        DD.Month,
        SUM(FSI.MerchandiseAmount) AS Revenue
    FROM FactSalesInvoice FSI
    JOIN DimCustomer DC ON FSI.CustomerKey = DC.CustomerKey
    JOIN DimDate DD     ON FSI.DateKey = DD.DateKey
    WHERE FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
      AND DD.Month = MONTH(DATEADD(MONTH, -1, GETDATE()))
      AND DD.Year  IN (
            YEAR(DATEADD(MONTH, -1, GETDATE())),
            YEAR(DATEADD(MONTH, -1, GETDATE())) - 1
          )
    GROUP BY DC.CustomerID, DC.CustomerName, DD.Year, DD.Month
),
CurrentMonth AS (
    SELECT CustomerID, CustomerName, Revenue AS Revenue_Current
    FROM RevenueByAccount
    WHERE Year = YEAR(DATEADD(MONTH, -1, GETDATE()))
),
PriorYearMonth AS (
    SELECT CustomerID, CustomerName, Revenue AS Revenue_Prior
    FROM RevenueByAccount
    WHERE Year = YEAR(DATEADD(MONTH, -1, GETDATE())) - 1
)
-- Use PriorYear as base so customers who bought last year but not this year are captured (100% loss)
SELECT TOP 40
    P.CustomerID,
    P.CustomerName,
    P.Revenue_Prior                                                        AS [Prior Year Revenue ($)],
    ISNULL(C.Revenue_Current, 0)                                          AS [Current Month Revenue ($)],
    (P.Revenue_Prior - ISNULL(C.Revenue_Current, 0))                     AS [Revenue Loss ($)],
    ROUND(
        100.0 * (P.Revenue_Prior - ISNULL(C.Revenue_Current, 0))
        / NULLIF(P.Revenue_Prior, 0),
    2)                                                                     AS [Loss % (%)]
FROM PriorYearMonth P
LEFT JOIN CurrentMonth C ON P.CustomerID = C.CustomerID
WHERE (P.Revenue_Prior - ISNULL(C.Revenue_Current, 0)) > 0
ORDER BY [Revenue Loss ($)] DESC

--- Example 16: YoY monthly comparison for a specific month (hardcoded month — status filter mandatory) ---
Question: "Monthly sales for January 2026 vs January 2025 with % change"
SELECT
    DD.Year,
    DD.Month,
    DD.MonthName,
    SUM(FSI.MerchandiseAmount)                                                         AS [Revenue ($)],
    COUNT(DISTINCT FSI.SalesInvoiceNo)                                                 AS [Invoice Count],
    LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year)                            AS [Prior Year Revenue ($)],
    (SUM(FSI.MerchandiseAmount) - LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year))
                                                                                       AS [YoY Change ($)],
    ROUND(100.0 * (SUM(FSI.MerchandiseAmount) - LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year))
          / NULLIF(ABS(LAG(SUM(FSI.MerchandiseAmount)) OVER (ORDER BY DD.Year)), 0), 2) AS [YoY Change (%)]
FROM FactSalesInvoice FSI
JOIN DimDate DD ON FSI.DateKey = DD.DateKey
WHERE FSI.Status NOT IN ('Void', 'Cancelled', 'Reversed')
  AND DD.Month = 1
  AND DD.Year IN (2025, 2026)
GROUP BY DD.Year, DD.Month, DD.MonthName
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
