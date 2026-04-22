using Microsoft.Data.SqlClient;

namespace SparsMcp.Database;

/// <summary>
/// SQL Server connection for the MCP server.
/// Reads credentials from the backend .env file (loaded in Program.cs via DotNetEnv).
/// Exposes a single ExecuteQueryAsync() helper used by all MCP tools.
/// Mirrors the behaviour of db.py exactly: new connection per query, 30s timeout,
/// TrustServerCertificate=yes, no connection pooling overhead.
/// </summary>
public static class SqlDatabase
{
    private static string BuildConnectionString()
    {
        var server   = Environment.GetEnvironmentVariable("SQL_SERVER")   ?? string.Empty;
        var database = Environment.GetEnvironmentVariable("SQL_DATABASE") ?? string.Empty;
        var user     = Environment.GetEnvironmentVariable("SQL_USER")     ?? string.Empty;
        var password = Environment.GetEnvironmentVariable("SQL_PASSWORD") ?? string.Empty;

        return new SqlConnectionStringBuilder
        {
            DataSource         = server,
            InitialCatalog     = database,
            UserID             = user,
            Password           = password,
            ConnectTimeout     = 30,
            TrustServerCertificate = true,
            Encrypt            = true,
        }.ConnectionString;
    }

    /// <summary>
    /// Execute a parameterised T-SQL query and return rows as a list of dictionaries.
    /// Uses @p0, @p1, … parameter names internally (converted from positional values).
    /// </summary>
    public static async Task<List<Dictionary<string, object?>>> ExecuteQueryAsync(
        string sql, params object?[] parameters)
    {
        var connectionString = BuildConnectionString();

        // Replace ? placeholders (Python style) with @p0, @p1, … (ADO.NET style)
        var idx = 0;
        var adoSql = System.Text.RegularExpressions.Regex.Replace(
            sql, @"\?", _ => $"@p{idx++}");

        await using var conn = new SqlConnection(connectionString);
        await conn.OpenAsync();

        await using var cmd = new SqlCommand(adoSql, conn);
        for (var i = 0; i < parameters.Length; i++)
            cmd.Parameters.AddWithValue($"@p{i}", parameters[i] ?? DBNull.Value);

        await using var reader = await cmd.ExecuteReaderAsync();

        var results = new List<Dictionary<string, object?>>();
        var columns = Enumerable.Range(0, reader.FieldCount)
                                .Select(reader.GetName)
                                .ToList();

        while (await reader.ReadAsync())
        {
            var row = new Dictionary<string, object?>();
            foreach (var col in columns)
            {
                var val = reader[col];
                row[col] = val == DBNull.Value ? null : val;
            }
            results.Add(row);
        }

        return results;
    }
}
