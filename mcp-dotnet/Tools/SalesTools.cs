using System.ComponentModel;
using ModelContextProtocol.Server;
using SparsMcp.Database;
using SparsMcp.Models;

namespace SparsMcp.Tools;

/// <summary>
/// All 7 MCP sales tools.
/// Each method mirrors its Python counterpart in tools.py/main.py exactly:
/// same tool name, same parameter names, same SQL query, same return shape.
/// </summary>
[McpServerToolType]
public static class SalesTools
{
    // ── Serialisation helper ──────────────────────────────────────────────────
    // Mirrors _serialize_row() in tools.py:
    //   date  → ISO-8601 string  (yyyy-MM-dd)
    //   decimal/numeric → double
    //   everything else passes through unchanged

    private static object? Serialize(object? value) => value switch
    {
        null                      => null,
        DateOnly d                => d.ToString("yyyy-MM-dd"),
        DateTime dt               => dt.ToString("yyyy-MM-dd"),
        decimal dec               => (double)dec,
        _                        => value,
    };

    private static T? Get<T>(Dictionary<string, object?> row, string key)
    {
        if (!row.TryGetValue(key, out var raw)) return default;
        var val = Serialize(raw);
        if (val is null) return default;
        try { return (T)Convert.ChangeType(val, typeof(T)); }
        catch { return default; }
    }

    private static T? GetNullable<T>(Dictionary<string, object?> row, string key) where T : struct
    {
        if (!row.TryGetValue(key, out var raw)) return null;
        var val = Serialize(raw);
        if (val is null) return null;
        try { return (T)Convert.ChangeType(val, typeof(T)); }
        catch { return null; }
    }

    // ── Tool 1 — Total Sales by Day/Week/Month/Year ───────────────────────────

    [McpServerTool(Name = "total_sales_by_period")]
    [Description(
        "Returns total sales (TotalSales) and invoice counts (InvoiceCount) " +
        "aggregated by week and date for a given calendar year and month name. " +
        "Use this to answer daily or weekly sales breakdowns within a specific month.")]
    public static async Task<List<SalesByPeriodRow>> TotalSalesByPeriod(
        [Description("Calendar year, e.g. 2024.")] int year,
        [Description("Full month name, e.g. 'June'.")] string month)
    {
        const string sql = """
            SELECT
                d.Year,
                d.MonthName,
                DATEPART(WEEK, d.FullDate) AS WeekNumber,
                d.FullDate                 AS SalesDate,
                SUM(fsi.TotalAmount)       AS TotalSales,
                COUNT(fsi.SalesInvoiceNo)  AS InvoiceCount
            FROM FactSalesInvoice fsi
            INNER JOIN DimDate d ON fsi.DateKey = d.DateKey
            WHERE d.Year = ? AND d.MonthName = ?
            GROUP BY
                d.Year,
                d.MonthName,
                DATEPART(WEEK, d.FullDate),
                d.FullDate
            HAVING d.Year >= 2000
            ORDER BY d.Year, d.MonthName, WeekNumber, SalesDate;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, year, month);
        return rows.Select(r => new SalesByPeriodRow(
            Year:         GetNullable<int>(r, "Year"),
            MonthName:    Get<string>(r, "MonthName"),
            WeekNumber:   GetNullable<int>(r, "WeekNumber"),
            SalesDate:    Get<string>(r, "SalesDate"),
            TotalSales:   GetNullable<double>(r, "TotalSales"),
            InvoiceCount: GetNullable<int>(r, "InvoiceCount")
        )).ToList();
    }

    // ── Tool 2 — Sales by Product, Collection, and Category ──────────────────

    [McpServerTool(Name = "sales_by_product")]
    [Description(
        "Returns sales revenue (TotalRevenue) and units sold (UnitsSold) " +
        "grouped by product category, collection, and item for a given category code. " +
        "Use this to analyse product-level performance within a category.")]
    public static async Task<List<SalesByProductRow>> SalesByProduct(
        [Description("Product category code, e.g. 'PAKIS'.")] string category)
    {
        const string sql = """
            SELECT
                p.Category,
                p.Collection,
                p.ItemID   AS Product,
                p.ItemName AS ProductName,
                SUM(fsd.SalesAmount) AS TotalRevenue,
                SUM(fsd.Quantity)    AS UnitsSold
            FROM FactSalesDetail fsd
            JOIN DimProduct p ON fsd.ProductKey = p.ProductKey
            WHERE p.Category = ?
            GROUP BY p.Category, p.Collection, p.ItemName, p.ItemID
            ORDER BY TotalRevenue DESC;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, category);
        return rows.Select(r => new SalesByProductRow(
            Category:     Get<string>(r, "Category"),
            Collection:   Get<string>(r, "Collection"),
            Product:      Get<string>(r, "Product"),
            ProductName:  Get<string>(r, "ProductName"),
            TotalRevenue: GetNullable<double>(r, "TotalRevenue"),
            UnitsSold:    GetNullable<double>(r, "UnitsSold")
        )).ToList();
    }

    // ── Tool 3 — Sales by Customer and Customer Tier ─────────────────────────

    [McpServerTool(Name = "sales_by_customer")]
    [Description(
        "Returns total amount spent (TotalSpent), order frequency, and customer tier " +
        "for a specific customer ID. Use this to profile an individual customer's " +
        "purchasing behaviour.")]
    public static async Task<List<SalesByCustomerRow>> SalesByCustomer(
        [Description("Customer identifier string, e.g. '053240'.")] string customer_id)
    {
        const string sql = """
            SELECT
                DPC.Description        AS [Customer Tier],
                c.CustomerName,
                c.CustomerID,
                SUM(fsi.TotalAmount)       AS TotalSpent,
                COUNT(fsi.SalesInvoiceNo)  AS OrderFrequency
            FROM FactSalesInvoice fsi
            JOIN DimCustomer c        ON fsi.CustomerKey = c.CustomerKey
            JOIN DimPriceCategory DPC ON c.Category = DPC.CategoryNo
            WHERE c.CustomerID = ?
            GROUP BY DPC.Description, c.CustomerName, c.CustomerID
            ORDER BY TotalSpent DESC;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, customer_id);
        return rows.Select(r => new SalesByCustomerRow(
            CustomerTier:   Get<string>(r, "Customer Tier"),
            CustomerName:   Get<string>(r, "CustomerName"),
            CustomerID:     Get<string>(r, "CustomerID"),
            TotalSpent:     GetNullable<double>(r, "TotalSpent"),
            OrderFrequency: GetNullable<int>(r, "OrderFrequency")
        )).ToList();
    }

    // ── Tool 4 — Sales by Region and Territory ────────────────────────────────

    [McpServerTool(Name = "sales_by_region")]
    [Description(
        "Aggregates revenue (RegionalRevenue) by country, region, and state " +
        "for a named region. Use this for geographic sales analysis.")]
    public static async Task<List<SalesByRegionRow>> SalesByRegion(
        [Description("Region name, e.g. 'NORTHEAST'.")] string region)
    {
        const string sql = """
            SELECT
                c.Country,
                r.RegionName,
                c.State,
                SUM(fsi.TotalAmount) AS RegionalRevenue
            FROM FactSalesInvoice fsi
            JOIN DimCustomer c ON fsi.CustomerKey = c.CustomerKey
            JOIN DimRegion r   ON c.Region = r.regionNo
            WHERE r.RegionName = ?
            GROUP BY c.Country, r.RegionName, c.State
            ORDER BY RegionalRevenue DESC;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, region);
        return rows.Select(r => new SalesByRegionRow(
            Country:         Get<string>(r, "Country"),
            RegionName:      Get<string>(r, "RegionName"),
            State:           Get<string>(r, "State"),
            RegionalRevenue: GetNullable<double>(r, "RegionalRevenue")
        )).ToList();
    }

    // ── Tool 5 — Revenue vs. Same Period Last Year (YoY) ─────────────────────

    [McpServerTool(Name = "yoy_revenue")]
    [Description(
        "Computes current-year revenue and compares it to the same month of the " +
        "prior year, returning the YoY growth percentage. Use this for year-over-year " +
        "revenue trend analysis.")]
    public static async Task<List<YoYRevenueRow>> YoyRevenue(
        [Description("Target year, e.g. 2025.")] int year,
        [Description("Full month name, e.g. 'November'.")] string month)
    {
        const string sql = """
            WITH RevenueSamePeriod AS (
                SELECT
                    d.MonthName,
                    d.Year AS CurrentYear,
                    SUM(fsi.TotalAmount) AS CurrentYearRevenue,
                    LAG(SUM(fsi.TotalAmount), 1)
                        OVER (PARTITION BY d.MonthName ORDER BY d.Year)
                        AS LastYearRevenue
                FROM FactSalesInvoice fsi
                JOIN DimDate d ON fsi.DateKey = d.DateKey
                GROUP BY d.Year, d.MonthName
            )
            SELECT
                *,
                (CurrentYearRevenue - LastYearRevenue) * 100.0
                    / NULLIF(LastYearRevenue, 0) AS YoY_Growth_Percentage
            FROM RevenueSamePeriod
            WHERE CurrentYear = ? AND MonthName = ?;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, year, month);
        return rows.Select(r => new YoYRevenueRow(
            MonthName:            Get<string>(r, "MonthName"),
            CurrentYear:          GetNullable<int>(r, "CurrentYear"),
            CurrentYearRevenue:   GetNullable<double>(r, "CurrentYearRevenue"),
            LastYearRevenue:      GetNullable<double>(r, "LastYearRevenue"),
            YoY_Growth_Percentage: GetNullable<double>(r, "YoY_Growth_Percentage")
        )).ToList();
    }

    // ── Tool 6 — Average Order Value (AOV) ───────────────────────────────────

    [McpServerTool(Name = "average_order_value")]
    [Description(
        "Computes the average invoice value (AverageOrderValue) for a given year " +
        "and month, excluding cancelled and voided orders. Use this to track AOV trends.")]
    public static async Task<List<AOVRow>> AverageOrderValue(
        [Description("Target year, e.g. 2025.")] int year,
        [Description("Full month name, e.g. 'November'.")] string month)
    {
        const string sql = """
            SELECT
                d.Year,
                d.MonthName,
                AVG(fso.TotalAmount) AS AverageOrderValue
            FROM FactSalesOrders fso
            JOIN DimDate d ON fso.OrderDateKey = d.DateKey
            WHERE fso.Status NOT IN ('Cancel', 'Void')
              AND d.Year      = ?
              AND d.MonthName = ?
            GROUP BY d.Year, d.MonthName, d.Month
            ORDER BY d.Year DESC, d.Month DESC;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, year, month);
        return rows.Select(r => new AOVRow(
            Year:              GetNullable<int>(r, "Year"),
            MonthName:         Get<string>(r, "MonthName"),
            AverageOrderValue: GetNullable<double>(r, "AverageOrderValue")
        )).ToList();
    }

    // ── Tool 7 — New vs. Repeat Customer Revenue ─────────────────────────────

    [McpServerTool(Name = "new_vs_repeat_revenue")]
    [Description(
        "Splits total revenue into NewCustomerRevenue (first-ever purchase) and " +
        "RepeatCustomerRevenue for a given year and month. Use this to understand " +
        "customer acquisition vs retention revenue contribution.")]
    public static async Task<List<NewVsRepeatRow>> NewVsRepeatRevenue(
        [Description("Target year, e.g. 2025.")] int year,
        [Description("Full month name, e.g. 'November'.")] string month)
    {
        const string sql = """
            WITH CustomerFirstPurchase AS (
                SELECT
                    CustomerKey,
                    MIN(DateKey) AS FirstPurchaseDateKey
                FROM FactSalesInvoice
                GROUP BY CustomerKey
            )
            SELECT
                d.Year,
                d.MonthName,
                SUM(CASE WHEN fsi.DateKey = cfp.FirstPurchaseDateKey
                         THEN fsi.TotalAmount ELSE 0 END) AS NewCustomerRevenue,
                SUM(CASE WHEN fsi.DateKey > cfp.FirstPurchaseDateKey
                         THEN fsi.TotalAmount ELSE 0 END) AS RepeatCustomerRevenue
            FROM FactSalesInvoice fsi
            JOIN DimDate d                 ON fsi.DateKey = d.DateKey
            JOIN CustomerFirstPurchase cfp ON fsi.CustomerKey = cfp.CustomerKey
            WHERE d.Year = ? AND d.MonthName = ?
            GROUP BY d.Year, d.MonthName
            ORDER BY d.Year DESC;
            """;

        var rows = await SqlDatabase.ExecuteQueryAsync(sql, year, month);
        return rows.Select(r => new NewVsRepeatRow(
            Year:                  GetNullable<int>(r, "Year"),
            MonthName:             Get<string>(r, "MonthName"),
            NewCustomerRevenue:    GetNullable<double>(r, "NewCustomerRevenue"),
            RepeatCustomerRevenue: GetNullable<double>(r, "RepeatCustomerRevenue")
        )).ToList();
    }
}
