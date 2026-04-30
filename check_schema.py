"""
Schema verification script.
Connects to TestStarSchema DB and compares actual table/column structure
against the schema defined in db_knowledge_executive.py
"""
import pyodbc

# ---- DB credentials from .env ----
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=122.129.80.229;"
    "DATABASE=TestStarSchema;"
    "UID=DEVUser;"
    "PWD=DEVUser"
)

# ---- Expected schema from db_knowledge_executive.py ----
EXPECTED = {
    "DimCustomer":               ["CustomerKey","CustomerID","CustomerCode","CustomerName","CustomerType","Category","Class","City","State","Country","RegionKey","Province","Phone","Email","PriceCategoryKey","PaymentTermKey","SalesDiscount","TaxRate","CreditLimit","CurrentBalance","Status","IsDropShipOnly","IsSpecialPricing","CreatedDate","ModifiedDate"],
    "DimDate":                   ["DateKey","FullDate","Year","Quarter","Month","MonthName"],
    "DimProduct":                ["ProductKey","ItemID","ItemCode","ItemName","Category","Collection","Design","DesignDescription","Color","ColorDescription","Size","SizeDescription","Brand","Country","Vendor","MaterialType","Shape","Weight","Area","Volume","IsDiscontinued","Status","SetItem","CreatedDate","ModifiedDate","Construction","ImagePath","MinOrderQty","CollectionType"],
    "DimVendors":                ["VendorKey","VendorID","VendorName","VendorType","Category","Class","Region","Status","City","State","Country","PaymentTerm","PaymentPriority","TaxRate","CreditLimit","FurnitureVendor","DesignerRate","InTransitDays"],
    "DimWarehouse":              ["WarehouseKey","WarehouseID","WarehouseName","City","State","Country","ZIP","Address","Phone","Email","ManagerID","StoreType","BusinessDivisionID","BufferQty","TaxID","TimeZoneHours","IsActive","WHSStatus","CreatedDate","ModifiedDate"],
    "DimInvoiceAddresses":       ["AddressesKey","SalesInvoiceNo","State","Zip","City","Country","ShipToAddress","SalesOrderNo","BillToAddress","BillTocity","BillToState","BillToZip"],
    "DimPaymentTerms":           ["PaymentTermKey","PaymentTermNo","Description","DueDays","DiscountDays","PaymentDiscount","CreditCardTerms"],
    "DimPriceCategory":          ["PriceCategoryKey","CategoryNo","Description","Blocked"],
    "DimSalesOrderDetail_Log":   ["SalesOrderNo","ItemID","SKU","LogSource","LogReason","BackOrder","LogDate"],
    "DimBillOfLading":           ["BillOfLadingKey","BillOfLadingNo","CustomerKey","WarehouseKey","Address1","Address2","City","State","Zip","VehicleNo","Carrier","Route","ShipVia","ScacCode","PickUpDateKey","DeliveryDateKey","TotalAmount","Freight","TotalCharges","FreightPrepaid","CODCharges","CODAmount","CODChargesPrepaid","CarrierProNo","Status","ADDDateKey"],
    "DimBillOfLadingDetail":     ["BillOfLadingDetailKey","BillOfLadingNo","PackingSlipNo","BaleNo","Weight","Charges","DeclareValue","TotalCUFT","Rate","RateRef","HandlingUnit","SideMark","Description"],
    "DimRugOAK":                 ["RugKey","SKU","ItemID","ProductKey","RugID","StockNo","VendorKey","LocationID","Category","Collection","Design","Color","Size","SizeDescription","DesignType","PurchasePrice","LastSalePrice","UnitPrice","SQFTPrice","STDCost","Cost","OrgPurchasePrice","LastCredit","LastCreditDate","RTVDebitMemo","RTVDate","SerialNo"],
    "DimItemPrice":              ["ItemPriceKey","ItemID","ProductKey","Pricecategory","UnitPrice","SQFTPrice"],
    "DimRegion":                 ["RegionKey","RegionNo","RegionName"],
    "DimGLAccounts":             ["GLAccountKey","AccountID","Description","Category","TypeID"],
    "DimConsignmentAddresses":   ["AddressesKey","ConsignmentNo","City","State","Zip","Country"],
    "DimSalesRep":               ["SalesRepKey","SalesRepID","SalesRepName","SalesRepType","Category","Class","Region","Status","City","State","Country","PaymentTerm","PaymentPriority","TaxRate","CreditLimit","DesignerRate"],
    "COAMaping":                 ["SegmentID","Value","AccountID","Main","AccDescr","TypeID","Category","BalanceSheet_MainGroups","BalanceSheet_SubGroups","BalanceSheet_Details","PLStatementMainGroups","PLStatementSubGroups","PLStatementDetails"],
    # Fact tables
    "FactSalesInvoice":          ["SalesInvoiceKey","SalesInvoiceNo","SalesOrderNo","PackingSlipNo","DateKey","OrderDateKey","CustomerKey","AddressesKey","WarehouseKey","PaymentTermKey","PriceCategoryKey","SalesType","InvoiceType","Status","TotalQuantity","TotalAmount","TaxAmount","ShippingCharges","HandlingCharges","ServiceCharges","MerchandiseAmount","ServicesAmount","AppliedAmount","DiscountAmount","TotalWeight"],
    "FactSalesDetail":           ["SalesKey","SalesInvoiceNo","InvoiceLineNumber","DateKey","OrderDateKey","ProductKey","CustomerKey","WarehouseKey","ItemType","Quantity","UnitPrice","UnitCost","DiscountAmount","SalesAmount","TaxAmount","ShippingCharges","ProfitAmount"],
    "FactPurchaseOrder":         ["PurchaseOrderKey","PurchaseOrderNo","VendorKey","DateKey","OrderDateKey","DueDateKey","CancelDateKey","ETADateKey","WarehouseKey","CustomerKey","TotalQty","TotalAmount","TotalTax","InTransitQty","ReceivedQty","Status","DropShipment"],
    "FactPurchaseDetail":        ["PurchaseLineKey","PurchaseOrderNo","Line_No","VendorKey","ProductKey","DateKey","DueDateKey","WarehouseKey","CustomerKey","OrderQty","UnitCost","LineAmount","TaxAmount","DiscountPercent","InTransitQty","ReceivedQty","Area","Length","ReceivedLength","SQFTCost"],
    "FactInventorySnapshot":     ["InventorySnapshotKey","ProductKey","WarehouseKey","QuantityOnHand","InventoryValue","PickingQuantity","SalesOrderQuantity","DamagedQuantity","ShowRoomQuantity","MissingBinQuantity","AverageCost"],
    "FactVendorInvoice":         ["VendorInvoiceKey","PayableInvoiceNo","VendorKey","InvoiceType","PaymentTermKey","Status","VendorInvoiceRef","VendorInvoiceDateKey","DueDateKey","EntryDateKey","TotalAmount","PaidAmount","WarehouseKey","PeriodID"],
    "FactVendorPayments":        ["PaymentKey","PaymentNo","VendorKey","DocDateKey","PaymentDateKey","PaymentAccount","DiscountAccount","DocType","Amount","AppliedAmount","AppliedDiscount","Status","PaymentType","PeriodID","VoidDateKey"],
    "FactCustomerReturn":        ["ReturnHeaderKey","CustomerReturnNo","SalesInvoiceNo","CreditMemoNo","CustomerKey","DateReceivedKey","CreditDateKey","InvoiceDateKey","ReceiptType","ReturnStatus","TotalQty","TotalAmount","ShippingHandlingAmount","QtyToWarehouse","TotalBales"],
    "FactCustomerReturnDetail":  ["ReturnKey","CustomerReturnNo","CustomerKey","DateReceivedKey","ProductKey","ReturnReason","ReturnQty","CreditQty","Cost","Price","Discount","ExtPrice","TaxAmount","SQFTPrice"],
    "FactCreditMemo":            ["CreditMemoKey","CreditMemoNo","CustomerKey","DateKey","SalesOrderNO","InvoiceNo","CustomerReturnNo","ConsignmentInvoiceNo","WarehouseKey","CreditDateKey","InvoiceDateKey","OrderDateKey","ShippedDateKey","TotalQty","TotalQtyInvoiced","TotalMerchandise","TotalServices","TotalAmount","TaxAmount","ShippingCharges","HandlingCharges","ServiceCharges","SalesDiscount","PaymentDiscountAmount","AppliedAmount","Status","PriceCategoryKey","PaymentTermKey"],
    "FactCreditMemoDetail":      ["SalesKey","SalesInvoiceNo","InvoiceLineNumber","WarehouseKey","DateKey","OrderDateKey","ProductKey","CustomerKey","SalesType","ItemType","Quantity","UnitPrice","UnitCost","DiscountAmount","SalesAmount","TaxAmount","ShippingCharges","ProfitAmount"],
    "FactCustomerPayment":       ["CashReceiptKey","CashReceiptNo","CustomerKey","SalesInvoiceKey","DocDateKey","PaymentDateKey","ApprovedDateKey","BounceDateKey","CashAccount","CreditAccount","DiscountAccount","DocType","Amount","AppliedAmount","AppliedDiscount","Status","PeriodID"],
    "FactCustomerApplication":   ["CRBatchApplicationNo","LineNo","CustomerKey","SalesInvoice","CashReceipt","CreditMemo","DocDateKey","TransactionDateKey","ControlAccount","DiscountAccount","InvoiceBalance","AppliedAmount","DiscountAmount","DocType","WriteOff","PeriodID"],
    "FactCustomerDebit":         ["CreditMemoKey","CustomerDebitNo","CustomerKey","InvoiceNo","WarehouseKey","CreditDateKey","InvoiceDateKey","OrderDateKey","ADDDateKey","TotalServices","TotalAmount","TaxAmount","ShippingCharges","HandlingCharges","ServiceCharges","SalesDiscount","PaymentDiscountAmount","OpenCredit","AppliedAmount","CreditApplied","Status","InvoiceType","SalesType"],
    "FactVendorReturn":          ["VendorReturnKey","VendorReturnNo","VendorKey","PaymentTermKey","InvoiceType","Status","VendorInvoiceRef","VendorReturnDateKey","WarehouseKey","TotalAmount","PaidAmount","DiscountAvailed","DiscountAmount","PeriodID"],
    "FactVendorReturnDetail":    ["VendorInvoiceDetailKey","VendorReturnNo","Line_No","VendorKey","ProductKey","DateKey","BaleNumber","Description","ItemType","VendorStyle","ReturnQty","Cost","Discount","ExtCost","TaxRate","ExtTax","SKU","PONo","POLineNo","POQty","ReceiveBin","LotNo"],
    "FactSalesOrders":           ["SalesOrderKey","SalesOrderNo","CustomerKey","WarehouseKey","PriceCategoryKey","PaymentTermKey","OrderDateKey","ShippingDateKey","CancelDateKey","SalesType","Status","SpecialOrder","TotalQty","TotalQtyShipped","TotalMerchandise","TotalServices","TotalAmount","TaxAmount","ServiceCharges","ShippingCharges","SalesDiscount","OpenCredit","PeriodID","PaymentDiscount"],
    "FactSalesOrderDetail":      ["SalesOrderDetailKey","SalesOrderNo","Line_No","CustomerKey","ProductKey","WarehouseKey","PriceCategoryKey","OrderDateKey","RequiredDateKey","ShippingDateKey","ItemType","SKU","OrderQty","ToShipQty","ShippedQty","Cost","Price","Discount","ExtPrice","TaxRate","TaxAmount","SQFTPrice","ReturnQty"],
    "FactPackingSlips":          ["PackingSlipKey","PackingSlipNo","CustomerKey","SalesOrderNo","WarehouseKey","DateCreatedKey","DatePrintedKey","SalesInvoiceNo","SaleType","Status","TotalQty","TotalBales","TotalWeight","TotalSQFT","TotalCuft","ShippingCharges","HandlingCharges","PeriodID"],
    "FactPackingSlipDetail":     ["PackingSlipDetailKey","PackingSlipNo","Line_No","ProductKey","WarehouseKey","PriceCategoryKey","ShippedDateKey","ItemType","Quantity","Cost","Price","Discount","ExtPrice","TaxRate","TaxAmount","SQFTPrice","TrackingNo"],
    "FactVendorPackingSlips":    ["VPackingSlipKey","VPackingSlipNo","VendorKey","PurchaseOrderNo","DateShippedKey","ArrivalDateKey","VPackingSlipDateKey","TotalQuantity","TotalAmount","Received","WarehouseKey","Status","PeriodID"],
    "FactVendorPackingSlipDetail":["VPackingSlipDetailKey","VPackingSlipNo","Line_No","ProductKey","VendorKey","PurchaseOrderNo","ItemType","SKU","OrderQty","ShippedQty","Cost","ExtCost","Discount","TaxRate","ExtTax","SQFTPrice"],
    "FactSalesCommission":       ["CommissionKey","CommissionNo","SalesInvoiceNo","SalesOrderNo","SalesRepKey","CustomerIDKey","PoolID","InvoiceType","Status","PoolCommission","PoolShare","CommissionRate","TotalAmount","AmountForCommission","PaidAmount","CDS","MCE","InvoiceDateKey","DateKey","CommissionDateKey"],
    "FactCommissionInvoice":     ["CommissionInvoiceKey","CommissionInvoiceNo","SalesRepKey","PaymentTermKey","Status","CommissionInvoiceRef","CommissionInvoiceDateKey","InvoiceDateKey","DueDateKey","TotalAmount","PaidAmount","WarehouseKey","PeriodID"],
    "FactCommissionRates":       ["CommissionRateKey","SalesRepKey","CustomerKey","HomeCollection","PricecategoryKey","Commission","CDS","SalesRepCompany","MasterAgent","CollectionType"],
    "FactConsignments":          ["ConsignmentKey","ConsignmentNo","DateKey","CustomerKey","AddressesKey","Pricecategorykey","PaymentTermKey","SalesType","InvoiceType","Status","TotalQuantity","TotalAmount","TaxAmount","ShippingCharges","HandlingCharges","ServiceCharges","MerchandiseAmount","ServicesAmount","AppliedAmount","DiscountAmount","TotalWeight"],
    "FactConsignmentDetail":     ["SalesKey","ConsignmentNo","LineNumber","DateKey","OrderDateKey","ProductKey","CustomerKey","WarehouseKey","ItemType","Quantity","UnitPrice","UnitCost","DiscountAmount","SalesAmount","TaxAmount","ShippingCharges","ProfitAmount"],
    "FactAccountMonthlySummary": ["AccountMonthlyKey","GLAccountKey","DateKey","AccountID","Description","PeriodStartDate","OpeningBalance","PTD_Debit","PTD_Credit","PTD_Net","YTD_Debit","YTD_Credit","YTD_Net","ClosingBalance"],
}


def main():
    print("Connecting to TestStarSchema on VCSSQL02...")
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    # ── 1. Get all actual tables + column counts ──────────────────────────────
    cursor.execute(
        "SELECT TABLE_NAME, COUNT(*) AS ColumnCount "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = 'dbo' "
        "GROUP BY TABLE_NAME ORDER BY TABLE_NAME"
    )
    db_tables = {r[0]: r[1] for r in cursor.fetchall()}

    # ── 2. Get actual columns per table (case-insensitive compare) ────────────
    cursor.execute(
        "SELECT TABLE_NAME, COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = 'dbo' "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION"
    )
    db_cols: dict[str, list[str]] = {}
    for tbl, col in cursor.fetchall():
        db_cols.setdefault(tbl, []).append(col)

    conn.close()

    expected_tables = set(EXPECTED.keys())
    actual_tables   = set(db_tables.keys())

    missing_from_db   = sorted(expected_tables - actual_tables)
    extra_in_db       = sorted(actual_tables   - expected_tables)
    common_tables     = sorted(expected_tables & actual_tables)

    # ── 3. Print summary ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(f"  SCHEMA: {len(expected_tables)} tables defined   |   DB: {len(actual_tables)} tables found")
    print("=" * 70)

    # --- Tables missing from DB ---
    if missing_from_db:
        print(f"\n[MISSING FROM DB] {len(missing_from_db)} table(s) defined in schema but NOT in DB:")
        for t in missing_from_db:
            print(f"  - {t}")
    else:
        print("\n[OK] All schema-defined tables exist in the DB.")

    # --- Extra tables in DB ---
    if extra_in_db:
        print(f"\n[EXTRA IN DB] {len(extra_in_db)} table(s) in DB but NOT defined in schema:")
        for t in extra_in_db:
            print(f"  + {t}  ({db_tables[t]} cols)")
    else:
        print("[OK] No unexpected extra tables in DB.")

    # ── 4. Per-table column comparison ───────────────────────────────────────
    print()
    print(f"{'TABLE':<40} {'SCHEMA':>8} {'DB':>6}  STATUS / DIFF")
    print("-" * 90)

    all_match = True
    for tbl in common_tables:
        exp_cols  = [c.lower() for c in EXPECTED[tbl]]
        act_cols  = [c.lower() for c in db_cols.get(tbl, [])]
        exp_set   = set(exp_cols)
        act_set   = set(act_cols)
        schema_n  = len(EXPECTED[tbl])
        db_n      = db_tables[tbl]

        missing_cols = sorted(exp_set - act_set)
        extra_cols   = sorted(act_set - exp_set)

        if not missing_cols and not extra_cols:
            status = "OK"
        else:
            status = "MISMATCH"
            all_match = False

        print(f"{tbl:<40} {schema_n:>8} {db_n:>6}  {status}", end="")
        if missing_cols:
            print(f"\n    SCHEMA cols missing from DB : {', '.join(missing_cols)}", end="")
        if extra_cols:
            print(f"\n    Extra cols in DB (not in schema): {', '.join(extra_cols)}", end="")
        print()

    print("-" * 90)
    if all_match and not missing_from_db:
        print("\n RESULT: All tables and columns match perfectly.")
    else:
        print("\n RESULT: Discrepancies found — review above.")


if __name__ == "__main__":
    main()
