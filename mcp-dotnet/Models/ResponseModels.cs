namespace SparsMcp.Models;

// All fields are nullable to gracefully handle NULL values from SQL Server,
// mirroring the Optional fields in the Python Pydantic models.

/// <summary>Tool 1 — total_sales_by_period</summary>
public record SalesByPeriodRow(
    int?    Year,
    string? MonthName,
    int?    WeekNumber,
    string? SalesDate,
    double? TotalSales,
    int?    InvoiceCount
);

/// <summary>Tool 2 — sales_by_product</summary>
public record SalesByProductRow(
    string? Category,
    string? Collection,
    string? Product,
    string? ProductName,
    double? TotalRevenue,
    double? UnitsSold
);

/// <summary>Tool 3 — sales_by_customer</summary>
public record SalesByCustomerRow(
    string? CustomerTier,
    string? CustomerName,
    string? CustomerID,
    double? TotalSpent,
    int?    OrderFrequency
);

/// <summary>Tool 4 — sales_by_region</summary>
public record SalesByRegionRow(
    string? Country,
    string? RegionName,
    string? State,
    double? RegionalRevenue
);

/// <summary>Tool 5 — yoy_revenue</summary>
public record YoYRevenueRow(
    string? MonthName,
    int?    CurrentYear,
    double? CurrentYearRevenue,
    double? LastYearRevenue,
    double? YoY_Growth_Percentage
);

/// <summary>Tool 6 — average_order_value</summary>
public record AOVRow(
    int?    Year,
    string? MonthName,
    double? AverageOrderValue
);

/// <summary>Tool 7 — new_vs_repeat_revenue</summary>
public record NewVsRepeatRow(
    int?    Year,
    string? MonthName,
    double? NewCustomerRevenue,
    double? RepeatCustomerRevenue
);
