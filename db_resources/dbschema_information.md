# VISIONARY COMPUTER SOLUTIONS (PVT) LTD

# STAR SCHEMA DOCUMENTATION FOR DATA LENS

---

## Technical Documentation

A stylized teal and green logo resembling an eye or a swirling wave with a green sphere at the center.

**Prepared By:**

**Zahid Iqbal & Muhammad Numan**
**2/24/2026**

# Table of Contents

**Star Schema Documentation for Data Lens.........................................................................................................................3**

**Definition of Star Schema..................................................................................................................................................3**

**Implementation Overview.......................................................................................................................................................4**

**a) What We Have Implemented...................................................................................................................................4**

**b) How Data is Inserted into the Star Schema Tables......................................................................................4**

**c) How the Tables Were Created................................................................................................................................5**

**c.1. Identify Core Business Areas............................................................................................................................5**

**c.2. Identify Supporting Information.......................................................................................................................5**

**All Schema Tables.....................................................................................................................................................................7**

**1. Dimension Tables........................................................................................................................................................7**

**a) DimCustomer..............................................................................................................................................................7**

**b) DimDate.......................................................................................................................................................................8**

**c) DimProduct.................................................................................................................................................................8**

**d) DimVendors................................................................................................................................................................9**

**e) DimWarehouse........................................................................................................................................................10**

**f) DimInvoiceAddresses............................................................................................................................................11**

**g) DimPaymentTerms................................................................................................................................................11**

**h) DimPriceCategory...................................................................................................................................................12**

**i) DimSalesOrderDetail_Log.....................................................................................................................................12**

**2. Fact Tables...................................................................................................................................................................13**

**a) FactSalesInvoice......................................................................................................................................................13**

**b) FactSalesDetail.........................................................................................................................................................14**

**c) FactPurchaseOrder................................................................................................................................................15**

**d) FactPurchaseDetail................................................................................................................................................16**

**e) FactInventorySnapshot.........................................................................................................................................17**

**a) FactVendorInvoices...............................................................................................................................................18**

**b) FactVendorPayments............................................................................................................................................19**

**c) FactCustomerReturn.............................................................................................................................................20**

**d) FactCustomerReturnDetail..................................................................................................................................21**

**e) FactCreditMemo......................................................................................................................................................22**

**f) FactCreditMemoDetail..........................................................................................................................................23**

Page 2 of 34

g) FactCustomerPayment.........................................................................................................................................24
h) FactCustomerApplication....................................................................................................................................25
i) FactVendorInvoiceDetail.....................................................................................................................................26
j) FactCustomerDebit.................................................................................................................................................27
k) FactVendorReturn..................................................................................................................................................28
l) FactVendorReturnDetail......................................................................................................................................29
**All Schema Views.....................................................................................................................................................................31**
a) VW_SalesByWarehouse.........................................................................................................................................31
b) VW_SalesMonthly...................................................................................................................................................32
c) VW_CustomerCreditYearly..................................................................................................................................32
d) VW_CustomerPayment.........................................................................................................................................33
e) VW_VendorReturnQtyMonthly..........................................................................................................................33

# Star Schema Documentation for Data Lens

## Definition of Star Schema
A Star Schema is the simplest form of a data warehouse schema. It consists of Fact Tables connected to Dimension Tables, optimized for analytics and reporting.

It consists of one central **fact table** that stores measurable transactional data, connected to multiple surrounding **dimension tables** that store descriptive information.

This star schema is designed for:
* Sales Analysis
* Purchase Analysis
* Inventory Monitoring
* Profitability Reporting
* Customer & Vendor Analytics
* Customer Returns & Payments
* Vendor Returns & Payments
* Back Order Information

## Implementation Overview
### a) What We Have Implemented

Page 3 of 34

We have designed and implemented a **Star Schema Data Warehouse** to transform raw transactional ERP data into a structured analytical model.

*   Dimension Tables (Master/Reference data)
*   Fact Tables (Transactional data)
*   Surrogate Key architecture relationships for accuracy
*   Optimized reporting structure

### b) How Data is Inserted into the Star Schema Tables.

To populate the Star Schema tables, we implemented an automated data loading process using a scheduled service job.

First, we inserted all existing (historical) data into the Dimension tables and Fact tables. This included all past customers, products, vendors, sales, purchases, and inventory records.

After completing the full initial data load,

When the job runs daily, it:

*   [ ] Inserts new master data into Dimension tables (if any new customer, product, etc. is created)
*   [ ] Inserts new daily transactions into Fact tables
*   [ ] Updates the Data Warehouse with the latest ERP data

Page 4 of 34

### c) How the Tables Were Created

#### c.1. Identify Core Business Areas

We first identified the main areas of the business that require reporting:

*   Sales
*   Purchase
*   Inventory
*   Customer Payments & Returns
*   Vendor Payments & Returns

Each of these business areas was converted into a **Fact Table**, which stores measurable data

#### c.2. Identify Supporting Information

Next, we identified supporting information required to analyze those numbers, such as:

*   Customer details
*   Product details
*   Vendor details
*   Date
*   Warehouse location
*   Shipping address

These became **Dimension Tables**.

→ **Here is a comprehensive example how we to created.**

Example Dim Table:

**DimCustomer**

*   **CustomerKey** → System-generated internal ID (Primary Key)
*   **CustomerID** → ERP customer ID
*   **CustomerName** → Name of customer
*   **City** → Location
*   **CustomerType** → Retail / Wholesale

**DimDate:**

*   **DateKey** → System-generated internal ID (Primary Key)
*   **FullDate** → Date
*   **Year** → Year
*   **Quarter** → Quarter
*   **Month** → Month
*   **MonthName** → MonthName

Example Fact Table: **FactSales**

*   **SalesKey** → System-generated ID
*   **CustomerKey** → Links to DimCustomer

Page **5** of **34**

*   **DateKey** → Links to DimDate
*   **InvoiceNumber** → ERP invoice reference
*   **InvoiceDate** → Date of sale
*   **TotalQuantity** → Units sold
*   **TotalAmount** → Total sale value

### Use Example:

```sql
INSERT INTO FactSales(SalesInvoiceNo, DateKey, CustomerKey, TotalQuantity, TotalAmount)
SELECT
    SI.SalesInvoiceNo,
    DD.DateKey,
    DC.CustomerKey,
    SI.TotalQty,
    SI.TotalAmount,
FROM SalesInvoice SI
JOIN DimDate DD       ON SI.InvoiceDate = DD.FullDate
JOIN DimCustomer DC   ON SI.CustomerID = DC.CustomerID
```

## All Schema Tables

### 1. Dimension Tables

#### a) DimCustomer

**Purpose:** Customer master data used for sales and receivable analytics.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>CustomerKey</th>
        <th>Surrogate key uniquely identifying a customer record.</th>
    </tr>
  </tbody>
</table>

Page 6 of 34

<table>
  <tbody>
    <tr>
        <td>CustomerID</td>
        <td>Business identifier from source systems.</td>
    </tr>
    <tr>
        <td>CustomerCode</td>
        <td>Alternate reference code.</td>
    </tr>
    <tr>
        <td>CustomerName</td>
        <td>Full customer or company name.</td>
    </tr>
    <tr>
        <td>CustomerType</td>
        <td>Retail, Wholesale, or other classification.</td>
    </tr>
    <tr>
        <td>Category</td>
        <td>Segmentation grouping.</td>
    </tr>
    <tr>
        <td>Class</td>
        <td>Internal classification.</td>
    </tr>
    <tr>
        <td>City</td>
        <td>Customer city.</td>
    </tr>
    <tr>
        <td>State</td>
        <td>Customer state or province.</td>
    </tr>
    <tr>
        <td>Country</td>
        <td>Customer country.</td>
    </tr>
    <tr>
        <td>Region</td>
        <td>Geographic region.</td>
    </tr>
    <tr>
        <td>Province</td>
        <td>Province if applicable.</td>
    </tr>
    <tr>
        <td>Phone</td>
        <td>Primary phone number.</td>
    </tr>
    <tr>
        <td>Email</td>
        <td>Primary email address.</td>
    </tr>
    <tr>
        <td>PriceCategory</td>
        <td>Assigned pricing tier.</td>
    </tr>
    <tr>
        <td>PaymentTerm</td>
        <td>Default payment terms.</td>
    </tr>
    <tr>
        <td>SalesDiscount</td>
        <td>Default discount percentage.</td>
    </tr>
    <tr>
        <td>TaxRate</td>
        <td>Default tax rate applied to the customer.</td>
    </tr>
    <tr>
        <td>CreditLimit</td>
        <td>Maximum credit allowed.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Account status.</td>
    </tr>
    <tr>
        <td>IsDropShipOnly</td>
        <td>Drop-ship only flag.</td>
    </tr>
    <tr>
        <td>IsSpecialPricing</td>
        <td>Flag indicating if special pricing rules apply.</td>
    </tr>
    <tr>
        <td>CreatedDate</td>
        <td>Record creation timestamp.</td>
    </tr>
    <tr>
        <td>ModifiedDate</td>
        <td>Last modification timestamp.</td>
    </tr>
  </tbody>
</table>

### b) DimDate
**Purpose:** Time dimension supporting all facts.

Page 7 of 34

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>DateKey</td>
        <td>Surrogate date key.</td>
    </tr>
    <tr>
        <td>FullDate</td>
        <td>Actual calendar date.</td>
    </tr>
    <tr>
        <td>Year</td>
        <td>Year component.</td>
    </tr>
    <tr>
        <td>Quarter</td>
        <td>Quarter number.</td>
    </tr>
    <tr>
        <td>Month</td>
        <td>Month number.</td>
    </tr>
    <tr>
        <td>MonthName</td>
        <td>Month name.</td>
    </tr>
  </tbody>
</table>

### c) DimProduct
**Purpose:** Product master data for inventory and sales analysis.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>ProductKey</td>
        <td>Surrogate product key.</td>
    </tr>
    <tr>
        <td>ItemID</td>
        <td>Unique Business Identifier for the product.</td>
    </tr>
    <tr>
        <td>ItemCode</td>
        <td>Secondary code.</td>
    </tr>
    <tr>
        <td>ItemName</td>
        <td>Product name or description.</td>
    </tr>
    <tr>
        <td>Category</td>
        <td>Product category.</td>
    </tr>
    <tr>
        <td>Collection</td>
        <td>Collection or series.</td>
    </tr>
    <tr>
        <td>Design</td>
        <td>Pattern or design.</td>
    </tr>
    <tr>
        <td>Color</td>
        <td>Primary color.</td>
    </tr>
    <tr>
        <td>Size</td>
        <td>Dimensions.</td>
    </tr>
    <tr>
        <td>Brand</td>
        <td>Brand name.</td>
    </tr>
    <tr>
        <td>Country</td>
        <td>Country of origin.</td>
    </tr>
    <tr>
        <td>Vendor</td>
        <td>Default supplier.</td>
    </tr>
    <tr>
        <td>MaterialType</td>
        <td>Composition material (e.g., Wool, Silk).</td>
    </tr>
    <tr>
        <td>Shape</td>
        <td>Shape of the product (e.g., Rectangular, Round).</td>
    </tr>
    <tr>
        <td>Weight</td>
        <td>Product weight.</td>
    </tr>
  </tbody>
</table>

Page 8 of 34

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>Area</td>
        <td>Surface area.</td>
    </tr>
    <tr>
        <td>Volume</td>
        <td>Volume.</td>
    </tr>
    <tr>
        <td>IsDiscontinued</td>
        <td>Flag indicating if product is no longer for sale.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Lifecycle status.</td>
    </tr>
    <tr>
        <td>CreatedDate</td>
        <td>Creation timestamp.</td>
    </tr>
    <tr>
        <td>ModifiedDate</td>
        <td>Last update timestamp.</td>
    </tr>
  </tbody>
</table>

### d) DimVendors
**Purpose:** Vendor master data for procurement analytics.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>VendorKey</td>
        <td>Surrogate vendor key.</td>
    </tr>
    <tr>
        <td>VendorID</td>
        <td>Business vendor identifier.</td>
    </tr>
    <tr>
        <td>VendorName</td>
        <td>Full company name of the supplier.</td>
    </tr>
    <tr>
        <td>VendorType</td>
        <td>Vendor classification.</td>
    </tr>
    <tr>
        <td>Category</td>
        <td>Business category.</td>
    </tr>
    <tr>
        <td>Class</td>
        <td>Priority or quality class.</td>
    </tr>
    <tr>
        <td>Region</td>
        <td>Geographic region.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Current relationship status (Active, Hold, etc.).</td>
    </tr>
    <tr>
        <td>City</td>
        <td>Vendor city.</td>
    </tr>
    <tr>
        <td>State</td>
        <td>Vendor state.</td>
    </tr>
    <tr>
        <td>Country</td>
        <td>Vendor country.</td>
    </tr>
    <tr>
        <td>PaymentTerm</td>
        <td>Payment terms.</td>
    </tr>
    <tr>
        <td>PaymentPriority</td>
        <td>Settlement priority.</td>
    </tr>
    <tr>
        <td>TaxRate</td>
        <td>Tax percentage applied to vendor invoices.</td>
    </tr>
    <tr>
        <td>CreditLimit</td>
        <td>Vendor credit limit.</td>
    </tr>
  </tbody>
</table>

Page 9 of 34

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>FurnitureVendor</td>
        <td>Furniture supplier flag.</td>
    </tr>
    <tr>
        <td>DesignerRate</td>
        <td>Special percentage rate for designers.</td>
    </tr>
    <tr>
        <td>InTransitDays</td>
        <td>Estimated delivery time from vendor.</td>
    </tr>
    <tr>
        <td>EffectiveDate</td>
        <td>Record effective date.</td>
    </tr>
  </tbody>
</table>

### e) DimWarehouse
**Purpose:** Warehouse and branch locations.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>BranchKey</td>
        <td>Surrogate branch key.</td>
    </tr>
    <tr>
        <td>WarehouseID</td>
        <td>Business location identifier.</td>
    </tr>
    <tr>
        <td>BranchName</td>
        <td>Descriptive name of the branch/warehouse.</td>
    </tr>
    <tr>
        <td>City</td>
        <td>City.</td>
    </tr>
    <tr>
        <td>State</td>
        <td>State.</td>
    </tr>
    <tr>
        <td>Country</td>
        <td>Country.</td>
    </tr>
    <tr>
        <td>ZIP</td>
        <td>Postal code.</td>
    </tr>
    <tr>
        <td>Address</td>
        <td>Street address.</td>
    </tr>
    <tr>
        <td>Phone</td>
        <td>Contact number.</td>
    </tr>
    <tr>
        <td>Email</td>
        <td>Contact email.</td>
    </tr>
    <tr>
        <td>ManagerID</td>
        <td>Manager identifier.</td>
    </tr>
    <tr>
        <td>StoreType</td>
        <td>Location type.</td>
    </tr>
    <tr>
        <td>BusinessDivisionID</td>
        <td>Division mapping.</td>
    </tr>
    <tr>
        <td>BufferQty</td>
        <td>Safety stock quantity.</td>
    </tr>
    <tr>
        <td>TaxID</td>
        <td>Tax identifier.</td>
    </tr>
    <tr>
        <td>TimeZoneHours</td>
        <td>UTC offset.</td>
    </tr>
  </tbody>
</table>

Page 10 of 34

<table>
  <tbody>
    <tr>
        <td>IsActive</td>
        <td>Operational flag.</td>
    </tr>
    <tr>
        <td>WHSStatus</td>
        <td>Warehouse status.</td>
    </tr>
    <tr>
        <td>CreatedDate</td>
        <td>Creation timestamp.</td>
    </tr>
    <tr>
        <td>ModifiedDate</td>
        <td>Last update timestamp.</td>
    </tr>
  </tbody>
</table>

### f) DimInvoiceAddresses
**Purpose:** Shipping destination reference.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>AddressesKey</td>
        <td>Surrogate key.</td>
    </tr>
    <tr>
        <td>State</td>
        <td>Destination state.</td>
    </tr>
    <tr>
        <td>City</td>
        <td>Destination city.</td>
    </tr>
    <tr>
        <td>Country</td>
        <td>Destination country.</td>
    </tr>
  </tbody>
</table>

### g) DimPaymentTerms
**Purpose:** Payment term definitions

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>PaymentTermKey</td>
        <td>key.</td>
    </tr>
    <tr>
        <td>PaymentTermNo</td>
        <td>Business key (term code)</td>
    </tr>
    <tr>
        <td>Description</td>
        <td>Term description</td>
    </tr>
    <tr>
        <td>DueDays</td>
        <td>Number of days until payment is due</td>
    </tr>
    <tr>
        <td>DiscountDays</td>
        <td>Days within which early payment discount applies</td>
    </tr>
    <tr>
        <td>PaymentDiscount</td>
        <td>Discount percentage if paid early</td>
    </tr>
    <tr>
        <td>CreditCardTerms</td>
        <td>Flag for credit card terms</td>
    </tr>
    <tr>
        <td>SQFTPrice</td>
        <td>Cost/price per square foot (for rugs).</td>
    </tr>
    <tr>
        <td>OrgCost</td>
        <td>Original cost per unit</td>
    </tr>
  </tbody>
</table>

Page 11 of 34

h) **DimPriceCategory**

**Purpose:** Price Category definitions

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>PriceCategoryKey</td>
        <td>key.</td>
    </tr>
    <tr>
        <td>CategoryNo</td>
        <td>Business key (category code)</td>
    </tr>
    <tr>
        <td>Description</td>
        <td>Category description</td>
    </tr>
    <tr>
        <td>Blocked</td>
        <td>Flag indicating if category is inactive</td>
    </tr>
  </tbody>
</table>

i) **DimSalesOrderDetail_Log**

**Purpose:** Sales Order Detail Log For BackOrder

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>SalesOrderNo</td>
        <td>Order Number.</td>
    </tr>
    <tr>
        <td>ItemID</td>
        <td>Item ID</td>
    </tr>
    <tr>
        <td>SKU</td>
        <td>Stock ID</td>
    </tr>
    <tr>
        <td>LogSource</td>
        <td>Log</td>
    </tr>
    <tr>
        <td>LogReason</td>
        <td>Log Reason</td>
    </tr>
    <tr>
        <td>BackOrder</td>
        <td>Flag Yes/No</td>
    </tr>
    <tr>
        <td>LogDate</td>
        <td>Log Date (BackOrder created date / Back Order Released date)</td>
    </tr>
  </tbody>
</table>

## 2. Fact Tables

a) **FactSalesInvoice**

**Purpose:** Invoice header metrics.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
</table>

Page **12** of **34**

<table>
  <tbody>
    <tr>
        <td>SalesInvoiceKey</td>
        <td>Surrogate key.</td>
    </tr>
    <tr>
        <td>SalesInvoiceNo</td>
        <td>Sales Invoice number.</td>
    </tr>
    <tr>
        <td>DateKey</td>
        <td>Invoice date.</td>
    </tr>
    <tr>
        <td>OrderDateKey</td>
        <td>Order date.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Customer reference.</td>
    </tr>
    <tr>
        <td>AddressesKey</td>
        <td>Shipping destination.</td>
    </tr>
    <tr>
        <td>BranchKey</td>
        <td>Fulfillment branch.</td>
    </tr>
    <tr>
        <td>PaymentTermKey</td>
        <td>Payment terms.</td>
    </tr>
    <tr>
        <td>SalesType</td>
        <td>Sales classification.</td>
    </tr>
    <tr>
        <td>InvoiceType</td>
        <td>Document type.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Invoice status.</td>
    </tr>
    <tr>
        <td>TotalQuantity</td>
        <td>Total quantity.</td>
    </tr>
    <tr>
        <td>TotalAmount</td>
        <td>Total amount.</td>
    </tr>
    <tr>
        <td>TaxAmount</td>
        <td>Tax total.</td>
    </tr>
    <tr>
        <td>ShippingCharges</td>
        <td>Shipping fees.</td>
    </tr>
    <tr>
        <td>HandlingCharges</td>
        <td>Handling fees.</td>
    </tr>
    <tr>
        <td>ServiceCharges</td>
        <td>Service fees.</td>
    </tr>
    <tr>
        <td>MerchandiseAmount</td>
        <td>Merchandise value.</td>
    </tr>
    <tr>
        <td>ServicesAmount</td>
        <td>Service revenue.</td>
    </tr>
    <tr>
        <td>AppliedAmount</td>
        <td>Applied payments.</td>
    </tr>
    <tr>
        <td>AdjustmentAmount</td>
        <td>Adjustments.</td>
    </tr>
    <tr>
        <td>DiscountAmount</td>
        <td>Discounts.</td>
    </tr>
    <tr>
        <td>TotalWeight</td>
        <td>Total shipment weight.</td>
    </tr>
  </tbody>
</table>

### b) FactSalesDetail
**Purpose:** Invoice line-level sales details.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
</table>

Page 13 of 34

<table>
  <tbody>
    <tr>
        <td>SalesKey</td>
        <td>Surrogate key.</td>
    </tr>
    <tr>
        <td>SalesInvoiceNo</td>
        <td>Sales Invoice number.</td>
    </tr>
    <tr>
        <td>InvoiceLineNumber</td>
        <td>Sale Item Line number.</td>
    </tr>
    <tr>
        <td>DateKey</td>
        <td>Invoice date reference.</td>
    </tr>
    <tr>
        <td>OrderDateKey</td>
        <td>Order date reference.</td>
    </tr>
    <tr>
        <td>ProductKey</td>
        <td>Product reference.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Customer reference.</td>
    </tr>
    <tr>
        <td>BranchKey</td>
        <td>Warehouse reference.</td>
    </tr>
    <tr>
        <td>SalesType</td>
        <td>Sale Item classification.</td>
    </tr>
    <tr>
        <td>ItemType</td>
        <td>Sale Item category.</td>
    </tr>
    <tr>
        <td>Quantity</td>
        <td>Sale Item Quantity sold.</td>
    </tr>
    <tr>
        <td>ShippedQuantity</td>
        <td>Sale item Quantity physically sent to customer.</td>
    </tr>
    <tr>
        <td>ReturnQuantity</td>
        <td>Sales Item Quantity returned after sale.</td>
    </tr>
    <tr>
        <td>UnitPrice</td>
        <td>Sale Item Unit price, Price charged per unit.</td>
    </tr>
    <tr>
        <td>UnitCost</td>
        <td>Sale Item cost per unit (at time of sale).</td>
    </tr>
    <tr>
        <td>DiscountAmount</td>
        <td>Sale Item Discount subtracted from specific line.</td>
    </tr>
    <tr>
        <td>SalesAmount</td>
        <td>Sale Item Net sales amount.</td>
    </tr>
    <tr>
        <td>TaxAmount</td>
        <td>Tax allocated to this line.</td>
    </tr>
    <tr>
        <td>ShippingCharges</td>
        <td>Sale Item Shipping fees allocated to this line.</td>
    </tr>
    <tr>
        <td>ProfitAmount</td>
        <td>Sale Item Net Profit amount.</td>
    </tr>
  </tbody>
</table>

### c) FactPurchaseOrder
**Purpose:** Purchase order header metrics.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
</table>

Page 14 of 34

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>**PurchaseOrderKey**</td>
        <td>Surrogate key.</td>
    </tr>
    <tr>
        <td>**PurchaseOrderNo**</td>
        <td>Purchase Order Number.</td>
    </tr>
    <tr>
        <td>**VendorKey**</td>
        <td>Vendor reference.</td>
    </tr>
    <tr>
        <td>**DateKey**</td>
        <td>Issue date reference.</td>
    </tr>
    <tr>
        <td>**DueDateKey**</td>
        <td>Expected receipt date reference.</td>
    </tr>
    <tr>
        <td>**CancelDateKey**</td>
        <td>Cancellation date reference.</td>
    </tr>
    <tr>
        <td>**CompletionDateKey**</td>
        <td>Completion date reference.</td>
    </tr>
    <tr>
        <td>**WarehouseKey**</td>
        <td>Purchase Receiving warehouse.</td>
    </tr>
    <tr>
        <td>**CustomerKey**</td>
        <td>Customer reference.</td>
    </tr>
    <tr>
        <td>**TotalQty**</td>
        <td>Purchase Order Total Items quantity.</td>
    </tr>
    <tr>
        <td>**TotalAmount**</td>
        <td>Purchase Order Grand Total amount.</td>
    </tr>
    <tr>
        <td>**TotalTax**</td>
        <td>Purchase Order Total tax.</td>
    </tr>
    <tr>
        <td>**InTransitQty**</td>
        <td>Purchase Order Quantity currently shipping from vendor.</td>
    </tr>
    <tr>
        <td>**ReceivedQty**</td>
        <td>Purchase Order Received quantity.</td>
    </tr>
    <tr>
        <td>**PaymentDiscount**</td>
        <td>Purchase Order Discount for early payment terms..</td>
    </tr>
    <tr>
        <td>**SalesDiscount**</td>
        <td>Purchase Order Trade discount provided by vendor.</td>
    </tr>
    <tr>
        <td>**FreightTerm**</td>
        <td>Purchase Order Freight terms.</td>
    </tr>
    <tr>
        <td>**POStatus**</td>
        <td>Purchase Order status (Open, Closed, Partially Shipped, Void, New, Cancel),</td>
    </tr>
    <tr>
        <td>**DropShipment**</td>
        <td>Flag for direct-to-customer shipments (1=Yes, 0=No)</td>
    </tr>
  </tbody>
</table>

Page **15** of **34**

### d) FactPurchaseDetail

**Purpose:** Purchase order line details.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>PurchaseLineKey</th>
        <th>Surrogate key.</th>
    </tr>
    <tr>
        <th>PurchaseOrderNo</th>
        <th>Purchase Order number.</th>
    </tr>
    <tr>
        <th>Line_No</th>
        <th>Purchase Item Line No.</th>
    </tr>
    <tr>
        <th>VendorKey</th>
        <th>Vendor reference.</th>
    </tr>
    <tr>
        <th>ProductKey</th>
        <th>Product reference.</th>
    </tr>
    <tr>
        <th>DateKey</th>
        <th>Issue date reference.</th>
    </tr>
    <tr>
        <th>DueDateKey</th>
        <th>Expected receipt date reference.</th>
    </tr>
    <tr>
        <th>WarehouseKey</th>
        <th>Destination warehouse reference.</th>
    </tr>
    <tr>
        <th>CustomerKey</th>
        <th>Customer reference.</th>
    </tr>
    <tr>
        <th>OrderQty</th>
        <th>Purchase Item Quantity requested from vendor.</th>
    </tr>
    <tr>
        <th>UnitCost</th>
        <th>Purchase Item Cost per unit.</th>
    </tr>
    <tr>
        <th>LineAmount</th>
        <th>Purchase Item Total line cost Amount.</th>
    </tr>
    <tr>
        <th>TaxAmount</th>
        <th>Purchase Item Line tax Amount.</th>
    </tr>
    <tr>
        <th>DiscountPercent</th>
        <th>Purchase Item Discount percent for specific line item.</th>
    </tr>
    <tr>
        <th>InTransitQty</th>
        <th>Purchase Item Quantity currently mid-shipment.</th>
    </tr>
    <tr>
        <th>ReceivedQty</th>
        <th>Purchase Item Received quantity.</th>
    </tr>
    <tr>
        <th>SQFTCost</th>
        <th>Purchase Item Cost per square foot.</th>
    </tr>
  </tbody>
</table>

Page 16 of 34

### e) FactInventorySnapshot

**Purpose:** Inventory position snapshots.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>InventorySnapshotKey</th>
        <th>Surrogate key.</th>
    </tr>
    <tr>
        <th>ProductKey</th>
        <th>Product reference.</th>
    </tr>
    <tr>
        <th>BranchKey</th>
        <th>Warehouse reference.</th>
    </tr>
    <tr>
        <th>QuantityOnHand</th>
        <th>Inventory Available quantity.</th>
    </tr>
    <tr>
        <th>InventoryValue</th>
        <th>Inventory value.</th>
    </tr>
    <tr>
        <th>PickingQuantity</th>
        <th>Inventory Allocated for picking.</th>
    </tr>
    <tr>
        <th>SalesOrderQuantity</th>
        <th>Inventory Reserved for sales orders.</th>
    </tr>
    <tr>
        <th>DamagedQuantity</th>
        <th>Inventory Damaged stock.</th>
    </tr>
    <tr>
        <th>ShowRoomQuantity</th>
        <th>Inventory Display stock.</th>
    </tr>
    <tr>
        <th>MissingBinQuantity</th>
        <th>Inventory Missing stock.</th>
    </tr>
    <tr>
        <th>AverageCost</th>
        <th>Inventory Average cost.</th>
    </tr>
    <tr>
        <th>OriginalCost</th>
        <th>Inventory Original cost.</th>
    </tr>
  </tbody>
</table>

Page **17** of **34**

### a) FactVendorInvoices

**Purpose:** Vendor position Invoices.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>PayableInvoiceNo</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>VendorKey</th>
        <th>Vendor reference.</th>
    </tr>
    <tr>
        <th>InvoiceType</th>
        <th>Code classifying the invoice type</th>
    </tr>
    <tr>
        <th>PaymentTermKey</th>
        <th>PaymentTerm reference..</th>
    </tr>
    <tr>
        <th>Status</th>
        <th>Current invoice status.</th>
    </tr>
    <tr>
        <th>VendorInvoiceRef</th>
        <th>Vendor's reference/invoice number.</th>
    </tr>
    <tr>
        <th>VendorInvoiceDateKey</th>
        <th>Date reference.</th>
    </tr>
    <tr>
        <th>DueDateKey</th>
        <th>Date reference.</th>
    </tr>
    <tr>
        <th>DiscountDateKey</th>
        <th>Date reference..</th>
    </tr>
    <tr>
        <th>CutOffDateKey</th>
        <th>Inventory Missing stock.</th>
    </tr>
    <tr>
        <th>TotalAmount</th>
        <th>Total invoice amount (before payments and adjustments).</th>
    </tr>
    <tr>
        <th>PaidAmount</th>
        <th>Amount already paid to the vendor.</th>
    </tr>
    <tr>
        <th>DiscountAmount</th>
        <th>Early payment discount offered by the vendor.</th>
    </tr>
    <tr>
        <th>DiscountAvailed</th>
        <th>Discount actually taken/applied.</th>
    </tr>
    <tr>
        <th>AdjustmentAmount</th>
        <th>Manual adjustments to the invoice (returns, quality issues, etc.).</th>
    </tr>
    <tr>
        <th>ApprovedAmount</th>
        <th>Amount approved for payment by management.</th>
    </tr>
    <tr>
        <th>ApprovedDiscount</th>
        <th>Discount amount approved.</th>
    </tr>
    <tr>
        <th>ApprovedAdjustment</th>
        <th>Adjustment amount approved.</th>
    </tr>
    <tr>
        <th>PaymentAccount</th>
        <th>account code where payment is recorded.</th>
    </tr>
    <tr>
        <th>OtherChargesAccount</th>
        <th>account for freight, handling, or other charges.</th>
    </tr>
    <tr>
        <th>WarehouseKey</th>
        <th>BranchKey reference</th>
    </tr>
    <tr>
        <th>PeriodID</th>
        <th>period identifier.</th>
    </tr>
  </tbody>
</table>

Page 18 of 34

### b) FactVendorPayments

**Purpose:** Vendor position Payments.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>PaymentNo</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>VendorKey</th>
        <th>Vendor reference.</th>
    </tr>
    <tr>
        <th>DocDateKey</th>
        <th>Date reference.</th>
    </tr>
    <tr>
        <th>PaymentDateKey</th>
        <th>Date reference.</th>
    </tr>
    <tr>
        <th>PaymentAccount</th>
        <th>Bank or cash account debited for the payment.</th>
    </tr>
    <tr>
        <th>DiscountAccount</th>
        <th>Account where discount taken is recorded.</th>
    </tr>
    <tr>
        <th>DocType</th>
        <th>Document type code.</th>
    </tr>
    <tr>
        <th>Amount</th>
        <th>Total payment amount sent to the vendor.</th>
    </tr>
    <tr>
        <th>AppliedAmount</th>
        <th>Amount applied to outstanding invoices.</th>
    </tr>
    <tr>
        <th>AppliedDiscount</th>
        <th>Discount amount deducted from payment.</th>
    </tr>
    <tr>
        <th>Status</th>
        <th>Payment status.</th>
    </tr>
    <tr>
        <th>PaymentType</th>
        <th>Method of payment</th>
    </tr>
    <tr>
        <th>PeriodID</th>
        <th>period identifier.</th>
    </tr>
    <tr>
        <th>VoidDateKey</th>
        <th>Date reference</th>
    </tr>
  </tbody>
</table>

Page **19** of **34**

### c) FactCustomerReturn

**Purpose:** Customer position Returns.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>ReturnHeaderKey</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>CustomerReturnNo</th>
        <th>Unique business identifier for the return.</th>
    </tr>
    <tr>
        <th>SalesInvoiceNo</th>
        <th>sales invoice number.</th>
    </tr>
    <tr>
        <th>CreditMemoNo</th>
        <th>Credit memo issued for this return</th>
    </tr>
    <tr>
        <th>CustomerKey</th>
        <th>Customer Referene.</th>
    </tr>
    <tr>
        <th>DateReceivedKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>CreditDateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>InvoiceDateKey</th>
        <th>Date of the original sales invoice.</th>
    </tr>
    <tr>
        <th>ReceiptType</th>
        <th>Type of receipt</th>
    </tr>
    <tr>
        <th>Status</th>
        <th>Return status</th>
    </tr>
    <tr>
        <th>ReceivingBin</th>
        <th>Warehouse bin where returned items are stored.</th>
    </tr>
    <tr>
        <th>TotalQty</th>
        <th>Total quantity of items returned.</th>
    </tr>
    <tr>
        <th>TotalAmount</th>
        <th>Total value/credit amount for the return.</th>
    </tr>
    <tr>
        <th>ShippingHandlingAmount</th>
        <th>Return shipping and handling charges.</th>
    </tr>
    <tr>
        <th>QtyToWarehouse</th>
        <th>Quantity accepted and sent to warehouse</th>
    </tr>
    <tr>
        <th>TotalBales</th>
        <th>For rugs/large items: number of bales/packages in return.</th>
    </tr>
  </tbody>
</table>

Page 20 of 34

d) **FactCustomerReturnDetail**

**Purpose:** Customer position Returns Detail.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>ReturnKey</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>CustomerReturnNo</th>
        <th>Unique business identifier for the return.</th>
    </tr>
    <tr>
        <th>SalesInvoiceNo</th>
        <th>sales invoice number.</th>
    </tr>
    <tr>
        <th>CustomerKey</th>
        <th>Customer Referene.</th>
    </tr>
    <tr>
        <th>DateReceivedKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>ProductKey</th>
        <th>Product Referene.</th>
    </tr>
    <tr>
        <th>ReturnReason</th>
        <th>Reason for return.</th>
    </tr>
    <tr>
        <th>ReturnQty</th>
        <th>Quantity returned.</th>
    </tr>
    <tr>
        <th>CreditQty</th>
        <th>Quantity credited.</th>
    </tr>
    <tr>
        <th>Cost</th>
        <th>product cost.</th>
    </tr>
    <tr>
        <th>Price</th>
        <th>selling price.</th>
    </tr>
    <tr>
        <th>Discount</th>
        <th>Discount that was applied</th>
    </tr>
    <tr>
        <th>ExtPrice</th>
        <th>Extended price (credit amount for this line)</th>
    </tr>
    <tr>
        <th>TaxAmount</th>
        <th>Tax on the credit</th>
    </tr>
    <tr>
        <th>SQFTPrice</th>
        <th>Cost/price per square foot (for rugs).</th>
    </tr>
    <tr>
        <th>OrgCost</th>
        <th>Original cost per unit</th>
    </tr>
  </tbody>
</table>

Page **21** of **34**

e) FactCreditMemo

**Purpose:** Credit Memo.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>CreditMemoKey</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>CreditMemoNo</th>
        <th>business identifier for the credit memo.</th>
    </tr>
    <tr>
        <th>CustomerKey</th>
        <th>Customer Referene.</th>
    </tr>
    <tr>
        <th>SalesInvoiceNo</th>
        <th>sales invoice number</th>
    </tr>
    <tr>
        <th>CustomerReturnNo</th>
        <th>Related customer return number</th>
    </tr>
    <tr>
        <th>BranchKey</th>
        <th>Warehouse Referene.</th>
    </tr>
    <tr>
        <th>CreditDateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>InvoiceDateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>OrderDateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>ShippedDateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>TotalQty</th>
        <th>Total quantity of items on the credit memo.</th>
    </tr>
    <tr>
        <th>TotalQtyInvoiced</th>
        <th>Total quantity that was originally invoiced.</th>
    </tr>
    <tr>
        <th>TotalMerchandise</th>
        <th>Value of merchandise only (excluding services).</th>
    </tr>
    <tr>
        <th>TotalServices</th>
        <th>Value of services (if any).</th>
    </tr>
    <tr>
        <th>TotalAmount</th>
        <th>Total credit memo amount (before adjustments).</th>
    </tr>
    <tr>
        <th>TaxAmount</th>
        <th>Tax amount on the credit.</th>
    </tr>
    <tr>
        <th>ShippingCharges</th>
        <th>Return shipping charges.</th>
    </tr>
    <tr>
        <th>HandlingCharges</th>
        <th>Handling charges.</th>
    </tr>
    <tr>
        <th>ServiceCharges</th>
        <th>Service charges (if applicable).</th>
    </tr>
  </tbody>
</table>

Page 22 of 34

<table>
  <tbody>
    <tr>
        <td>DiscountAmount</td>
        <td>Discount applied to the credit.</td>
    </tr>
    <tr>
        <td>OpenCredit</td>
        <td>Remaining unapplied credit amount.</td>
    </tr>
    <tr>
        <td>AppliedAmount</td>
        <td>Amount of credit already applied to invoices.</td>
    </tr>
    <tr>
        <td>CreditApplied</td>
        <td>indicating if credit has been applied.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Credit status</td>
    </tr>
    <tr>
        <td>InvoiceType</td>
        <td>Type of document.</td>
    </tr>
    <tr>
        <td>SalesType</td>
        <td>Sales type code</td>
    </tr>
    <tr>
        <td>PriceCategoryKey</td>
        <td>Pricing tier applied.</td>
    </tr>
    <tr>
        <td>PaymentTermKey</td>
        <td>Payment terms for any balances.</td>
    </tr>
  </tbody>
</table>

### f) FactCreditMemoDetail

**Purpose:** Credit Memo Detail.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>SalesKey</th>
        <th>credit detail key.</th>
    </tr>
    <tr>
        <td>CreditMemoNo</td>
        <td>business identifier for the credit memo.</td>
    </tr>
    <tr>
        <td>InvoiceLineNumber</td>
        <td>Line number</td>
    </tr>
    <tr>
        <td>SalesInvoiceNo</td>
        <td>sales invoice number</td>
    </tr>
    <tr>
        <td>BranchKey</td>
        <td>Warehouse Referene.</td>
    </tr>
    <tr>
        <td>InvoiceDateKey</td>
        <td>Date Referene.</td>
    </tr>
  </tbody>
</table>

Page **23** of **34**

<table>
  <tbody>
    <tr>
        <td>OrderDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>ProductKey</td>
        <td>Product Referene.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Customer Key Referene</td>
    </tr>
    <tr>
        <td>SalesType</td>
        <td>Type of sales</td>
    </tr>
    <tr>
        <td>ItemType</td>
        <td>Item category</td>
    </tr>
    <tr>
        <td>Quantity</td>
        <td>Quantity credited</td>
    </tr>
    <tr>
        <td>ShippedQuantity</td>
        <td>Quantity originally shipped</td>
    </tr>
    <tr>
        <td>ReturnQuantity</td>
        <td>Quantity returned (if credit is for a return).</td>
    </tr>
    <tr>
        <td>UnitPrice</td>
        <td>Original unit price.</td>
    </tr>
    <tr>
        <td>UnitCost</td>
        <td>Original unit cost.</td>
    </tr>
    <tr>
        <td>DiscountAmount</td>
        <td>Discount applied on this line.</td>
    </tr>
    <tr>
        <td>SalesAmount</td>
        <td>Extended credit amount (after discount).</td>
    </tr>
    <tr>
        <td>TaxAmount</td>
        <td>Tax on the credit line.</td>
    </tr>
    <tr>
        <td>ShippingCharges</td>
        <td>Shipping charges allocated to this line.</td>
    </tr>
  </tbody>
</table>

### g) FactCustomerPayment

**Purpose:** Customer Payments.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>CashReceiptNo</td>
        <td>Unique identifier for the cash receipt.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Customer making the payment.</td>
    </tr>
    <tr>
        <td>SalesInvoice</td>
        <td>Sales invoice number</td>
    </tr>
    <tr>
        <td>DocDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>PaymentDateKey</td>
        <td>Date Referene.</td>
    </tr>
  </tbody>
</table>

Page **24** of **34**

<table>
  <tbody>
    <tr>
        <td>ApprovedDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>BounceDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>CashAccount</td>
        <td>account receiving payment.</td>
    </tr>
    <tr>
        <td>CreditAccount</td>
        <td>Account credit (revenue/receivable).</td>
    </tr>
    <tr>
        <td>DiscountAccount</td>
        <td>Account Discount</td>
    </tr>
    <tr>
        <td>DocType</td>
        <td>Payment method</td>
    </tr>
    <tr>
        <td>Amount</td>
        <td>Total payment amount received.</td>
    </tr>
    <tr>
        <td>AppliedAmount</td>
        <td>Amount applied to outstanding invoices.</td>
    </tr>
    <tr>
        <td>AppliedDiscount</td>
        <td>Discount given for early payment.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Payment status</td>
    </tr>
    <tr>
        <td>Approved</td>
        <td>Flag Approved</td>
    </tr>
    <tr>
        <td>PeriodID</td>
        <td>period identifier.</td>
    </tr>
  </tbody>
</table>

## h) FactCustomerApplication

**Purpose:** A single customer payment often applies to multiple invoices

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>CRBatchApplicationNo</th>
        <th>Batch application number.</th>
    </tr>
    <tr>
        <td>LineNo</td>
        <td>Line sequence within the batch.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Customer Referene</td>
    </tr>
    <tr>
        <td>SalesInvoiceNo</td>
        <td>Sales Invoice Number</td>
    </tr>
    <tr>
        <td>CashReceiptNo</td>
        <td>Payment being applied.</td>
    </tr>
  </tbody>
</table>

Page 25 of 34

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>CreditMemo</td>
        <td>Credit memo being applied</td>
    </tr>
    <tr>
        <td>DocDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>TransactionDateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>ControlAccount</td>
        <td>Control/suspense account</td>
    </tr>
    <tr>
        <td>DiscountAccount</td>
        <td>Account Discount</td>
    </tr>
    <tr>
        <td>InvoiceBalance</td>
        <td>Outstanding balance on the invoice before application.</td>
    </tr>
    <tr>
        <td>AppliedAmount</td>
        <td>Amount of payment/credit applied to the invoice.</td>
    </tr>
    <tr>
        <td>DiscountAmount</td>
        <td>Discount taken on this application.</td>
    </tr>
    <tr>
        <td>DocType</td>
        <td>Document type</td>
    </tr>
    <tr>
        <td>WriteOff</td>
        <td>indicating if any amount was written off</td>
    </tr>
    <tr>
        <td>PeriodID</td>
        <td>period identifier</td>
    </tr>
  </tbody>
</table>

### i) FactVendorInvoiceDetail

**Purpose:** Each vendor invoice header contains multiple line items (products received). FactVendorInvoiceDetail captures every invoice line: which product, quantity received.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>VendorInvoiceDetailKey</td>
        <td>key.</td>
    </tr>
    <tr>
        <td>PayableInvoiceNo</td>
        <td>Payable Invoice No</td>
    </tr>
    <tr>
        <td>Line_No</td>
        <td>Line sequence number within the invoice.</td>
    </tr>
    <tr>
        <td>VendorKey</td>
        <td>Vendor Referene.</td>
    </tr>
    <tr>
        <td>ProductKey</td>
        <td>Product Referene.</td>
    </tr>
    <tr>
        <td>DateKey</td>
        <td>Date Referene.</td>
    </tr>
    <tr>
        <td>WarehouseKey</td>
        <td>Branch Reference</td>
    </tr>
    <tr>
        <td>BaleNumber</td>
        <td>Bale or package identifier</td>
    </tr>
  </tbody>
</table>

Page **26** of **34**

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>Description</td>
        <td>Item description from invoice.</td>
    </tr>
    <tr>
        <td>ItemType</td>
        <td>Item classification</td>
    </tr>
    <tr>
        <td>VendorStyle</td>
        <td>Vendor's style code for the item.</td>
    </tr>
    <tr>
        <td>OrderQty</td>
        <td>Quantity ordered from vendor.</td>
    </tr>
    <tr>
        <td>ReceivedQty</td>
        <td>Quantity actually received.</td>
    </tr>
    <tr>
        <td>ReturnQty</td>
        <td>Quantity returned to vendor</td>
    </tr>
    <tr>
        <td>Cost</td>
        <td>Unit cost from vendor.</td>
    </tr>
    <tr>
        <td>ExtCost</td>
        <td>Extended cost (Cost × ReceivedQty).</td>
    </tr>
    <tr>
        <td>TaxRate</td>
        <td>Tax rate applied to this line.</td>
    </tr>
    <tr>
        <td>ExtTax</td>
        <td>Extended tax amount (TaxRate × ExtCost).</td>
    </tr>
    <tr>
        <td>Category<br/>Collection</td>
        <td>Product category code.<br/>Collection identifier</td>
    </tr>
    <tr>
        <td>Design</td>
        <td>Design code or ID.</td>
    </tr>
    <tr>
        <td>PONo</td>
        <td>Purchase Order number</td>
    </tr>
    <tr>
        <td>POQty</td>
        <td>Quantity on PO.</td>
    </tr>
    <tr>
        <td>ReceiveBin</td>
        <td>Warehouse bin where item is stored.</td>
    </tr>
    <tr>
        <td>LotNo</td>
        <td>Lot number for batch tracking</td>
    </tr>
  </tbody>
</table>

### j) FactCustomerDebit

**Purpose:** Summary level data for customer credit memos and debit adjustments.

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>CreditMemoKey</td>
        <td>Primary Key (IDENTITY). Surrogate key for the debit record.</td>
    </tr>
    <tr>
        <td>CustomerDebitNo</td>
        <td>Business Key. The actual credit memo number from the ERP.</td>
    </tr>
    <tr>
        <td>CustomerKey</td>
        <td>Foreign Key to DimCustomer.</td>
    </tr>
  </tbody>
</table>

Page **27** of **34**

<table>
  <tbody>
    <tr>
        <td>InvoiceNo</td>
        <td>Reference to the original Sales Invoice (if applicable).</td>
    </tr>
    <tr>
        <td>BranchKey</td>
        <td>Foreign Key to DimBranch. Tracks which location issued the credit.</td>
    </tr>
    <tr>
        <td>CreditDateKey</td>
        <td>Foreign Key to DimDate. The date the credit was issued.</td>
    </tr>
    <tr>
        <td>InvoiceDateKey</td>
        <td>Foreign Key to DimDate. The date of the original invoice.</td>
    </tr>
    <tr>
        <td>OrderDateKey</td>
        <td>Foreign Key to DimDate. The original order date.</td>
    </tr>
    <tr>
        <td>ADDDateKey</td>
        <td>Foreign Key to DimDate. System entry date.</td>
    </tr>
    <tr>
        <td>TotalQty</td>
        <td>Total quantity of items being credited/debited.</td>
    </tr>
    <tr>
        <td>TotalQtyInvoiced</td>
        <td>Total quantity originally invoiced.</td>
    </tr>
    <tr>
        <td>TotalMerchandise</td>
        <td>Value of physical goods being credited.</td>
    </tr>
    <tr>
        <td>TotalServices</td>
        <td>Value of services (e.g., cleaning, repair) being credited.</td>
    </tr>
    <tr>
        <td>TotalAmount</td>
        <td>The final total amount of the debit/credit.</td>
    </tr>
    <tr>
        <td>TaxAmount</td>
        <td>Amount of tax being reversed or adjusted.</td>
    </tr>
    <tr>
        <td>ShippingCharges</td>
        <td>Shipping costs included in the credit.</td>
    </tr>
    <tr>
        <td>HandlingCharges</td>
        <td>Handling fees included in the credit.</td>
    </tr>
    <tr>
        <td>ServiceCharges</td>
        <td>Fees for services associated with this debit.</td>
    </tr>
    <tr>
        <td>SalesDiscount</td>
        <td>Any additional sales discounts applied.</td>
    </tr>
    <tr>
        <td>PaymentDiscountAmount</td>
        <td>Cash/Payment discounts reversed or applied</td>
    </tr>
    <tr>
        <td>OpenCredit</td>
        <td>The remaining balance of the credit yet to be used.</td>
    </tr>
    <tr>
        <td>AppliedAmount<br/>CreditApplied</td>
        <td>The portion of the credit already applied to other invoices.<br/>Flag (0/1) indicating if the credit is fully applied.</td>
    </tr>
    <tr>
        <td>Status</td>
        <td>Current state: "Open", "Applied", "Void", "Pending".</td>
    </tr>
    <tr>
        <td>InvoiceType</td>
        <td>Internal code for the document type.</td>
    </tr>
    <tr>
        <td>SalesType</td>
        <td>Classification of the sale (e.g., 'RET' for Retail, 'WHL' for Wholesale).</td>
    </tr>
  </tbody>
</table>

### k) FactVendorReturn

**Purpose:** Summary level data for customer credit memos and debit adjustments.

Page **28** of **34**

<table>
  <thead>
    <tr>
        <th>Column Name</th>
        <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>**VendorReturnKey**</td>
        <td>key.</td>
    </tr>
    <tr>
        <td>**VendorReturnNo**</td>
        <td>Unique vendor return number</td>
    </tr>
    <tr>
        <td>**VendorKey**</td>
        <td>Foreign Key | Links to `DimVendors`</td>
    </tr>
    <tr>
        <td>**PaymentTermKey**</td>
        <td>Foreign Key | Links to `DimPaymentTerms`</td>
    </tr>
    <tr>
        <td>**InvoiceType**</td>
        <td>Type of return</td>
    </tr>
    <tr>
        <td>**Status**</td>
        <td>return status</td>
    </tr>
    <tr>
        <td>**VendorInvoiceRef**</td>
        <td>Vendor's invoice or reference number</td>
    </tr>
    <tr>
        <td>**PurchaseReceiptNo**</td>
        <td>Associated purchase receipt number</td>
    </tr>
    <tr>
        <td>**VendorReturnDateKey**</td>
        <td>Foreign Key | Links to `DimDate`.</td>
    </tr>
    <tr>
        <td>**EntryDateKey**</td>
        <td>Foreign Key | Links to `DimDate`</td>
    </tr>
    <tr>
        <td>**DueDateKey**</td>
        <td>Foreign Key | Links to `DimDate`</td>
    </tr>
    <tr>
        <td>**DiscountDateKey**</td>
        <td>Foreign Key | Links to `DimDate`</td>
    </tr>
    <tr>
        <td>**CutOffDateKey**</td>
        <td>oreign Key | Links to `DimDate`</td>
    </tr>
    <tr>
        <td>**WarehouseKey**</td>
        <td>Links to `DimWarehouse`</td>
    </tr>
    <tr>
        <td>**TotalAmount**</td>
        <td>Total value of goods being returned</td>
    </tr>
    <tr>
        <td>**PaidAmount**</td>
        <td>Amount already paid or credited by the vendor</td>
    </tr>
    <tr>
        <td>**DiscountAvailed**</td>
        <td>Discount amount actually taken/applied</td>
    </tr>
    <tr>
        <td>**AdjustmentAmount**</td>
        <td>Manual adjustments made to the return amount</td>
    </tr>
    <tr>
        <td>**ApprovedAmount**</td>
        <td>Final amount approved for credit by vendor.</td>
    </tr>
    <tr>
        <td>**ApprovedDiscount**</td>
        <td>Discount amount approved by vendor.</td>
    </tr>
    <tr>
        <td>**ApprovedAdjustment**</td>
        <td>Adjustment amount approved by vendor.</td>
    </tr>
    <tr>
        <td>**PaymentAccount**</td>
        <td>account code where return</td>
    </tr>
  </tbody>
</table>

Page **29** of **34**

<table>
  <tbody>
    <tr>
        <td>OtherChargesAccount</td>
        <td>account code for freight, handling, restocking, or other charges related</td>
    </tr>
    <tr>
        <td>PeriodID</td>
        <td>period identifier</td>
    </tr>
  </tbody>
</table>

### l) FactVendorReturnDetail

**Purpose:** Summary level data for customer credit memos and debit adjustments.

<table>
  <tbody>
    <tr>
        <td>Column Name</td>
        <td>Description</td>
    </tr>
    <tr>
        <th>VendorReturnDetailKey</th>
        <th>key.</th>
    </tr>
    <tr>
        <th>VendorReturnNo</th>
        <th>Return No</th>
    </tr>
    <tr>
        <th>Line_No</th>
        <th>Line sequence number within the invoice.</th>
    </tr>
    <tr>
        <th>VendorKey</th>
        <th>Vendor Referene.</th>
    </tr>
    <tr>
        <th>ProductKey</th>
        <th>Product Referene.</th>
    </tr>
    <tr>
        <th>DateKey</th>
        <th>Date Referene.</th>
    </tr>
    <tr>
        <th>BaleNumber</th>
        <th>Bale or package identifier</th>
    </tr>
    <tr>
        <th>Description</th>
        <th>Item description from invoice.</th>
    </tr>
    <tr>
        <th>ItemType</th>
        <th>Item classification</th>
    </tr>
    <tr>
        <th>VendorStyle</th>
        <th>Vendor's style code for the item.</th>
    </tr>
    <tr>
        <th>OrderQty</th>
        <th>Quantity ordered from vendor.</th>
    </tr>
    <tr>
        <th>ReceivedQty</th>
        <th>Quantity actually received.</th>
    </tr>
    <tr>
        <th>ReturnQty</th>
        <th>Quantity returned to vendor</th>
    </tr>
    <tr>
        <th>Cost</th>
        <th>Unit cost from vendor.</th>
    </tr>
    <tr>
        <th>ExtCost</th>
        <th>Extended cost (Cost × ReceivedQty).</th>
    </tr>
    <tr>
        <th>TaxRate</th>
        <th>Tax rate applied to this line.</th>
    </tr>
    <tr>
        <th>ExtTax</th>
        <th>Extended tax amount .</th>
    </tr>
    <tr>
        <th>SKU</th>
        <th>Stock ID</th>
    </tr>
  </tbody>
</table>

Page 30 of 34

<table>
  <thead>
    <tr>
        <th></th>
        <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>**PONo**</td>
        <td>PO Number</td>
    </tr>
    <tr>
        <td>**ReceiveBin**</td>
        <td>Receive Bin</td>
    </tr>
    <tr>
        <td>**LotNo**</td>
        <td>Lot Number</td>
    </tr>
  </tbody>
</table>

# All Schema Views

## a) VW_SalesByWarehouse

**Purpose:** The **VW_SalesByWarehouse** view shows total sales, quantity sold, profit, and shipping charges for each warehouse,

```sql
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
    SUM(ISNULL(FSD.ShippingCharges,0)) AS TotalShipping
FROM FactSalesDetail FSD
LEFT JOIN DimWarehouse DW ON FSD.BranchKey = DW.BranchKey
LEFT JOIN DimDate DD ON FSD.DateKey = DD.DateKey
GROUP BY DW.WarehouseID, DW.BranchName, DW.City, DW.State, DD.Year,
DD.MonthName;
```

Page **31** of **34**

```sql
GO

SELECT * FROM VW_SalesByWarehouse WHERE Year = '2017' AND WarehouseID =
'L91'
```

### b) VW_SalesMonthly

**Purpose:** The **VW_SalesMonthly** view provides an overall monthly sales overview for the business, showing total invoices, customer count, total quantity sold, sales revenue, tax, discounts, merchandise revenue, services revenue, and average order value,

```sql
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
GO
SELECT * FROM VW_SalesMonthly WHERE MonthName = 'JUNE' AND Year = '2020'
```

Page **32** of **34**

### c) VW_CustomerCreditYearly

```sql
SELECT
    dc.CustomerID,
    d.Year,
    SUM(fc.TotalAmount) AS TotalCredit
FROM FactCreditMemo fc
JOIN DimCustomer dc ON fc.CustomerKey = dc.CustomerKey
JOIN DimDate d ON fc.InvoiceDateKey = d.DateKey
GROUP BY dc.CustomerID, d.Year
ORDER BY d.Year;
```

### d) VW_CustomerPayment

```sql
SELECT
    dc.CustomerID,
    SUM(fcp.Amount) AS PaymentReceived,
    SUM(fcp.AppliedAmount) AS AppliedAmount,
    SUM(fcp.Amount - fcp.AppliedAmount) AS PendingAmount
FROM FactCustomerPayment fcp
JOIN DimCustomer dc ON fcp.CustomerKey = dc.CustomerKey
GROUP BY dc.CustomerID;
```

### e) VW_VendorReturnQtyMonthly

```sql
SELECT
    dv.VendorID,
    d.Year,
    d.MonthName,
```

Page **33** of **34**

```sql
SUM(fvid.ReturnQty) AS ReturnQty,
FROM FactVendorInvoiceDetail fvid
JOIN DimVendors dv ON fvid.VendorKey = dv.VendorKey
JOIN DimDate d ON fvid.DateKey = d.DateKey
GROUP BY dv.VendorID, d.Year, d.MonthName
```

### f) BackOrderHistory

```sql
select * from DimSalesOrderDetail_Log where SalesOrderNo = '4506677'
```

Page **34** of **34**