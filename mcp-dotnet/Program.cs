using System.ComponentModel;
using DotNetEnv;
using SparsMcp.Tools;

// Load credentials from backend/.env (one level up from this project folder)
var envPath = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".env");
if (File.Exists(envPath))
    Env.Load(envPath);

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Logging.AddConsole(opts =>
{
    opts.FormatterName = "simple";
});
builder.Logging.AddSimpleConsole(opts =>
{
    opts.SingleLine = true;
    opts.TimestampFormat = "yyyy-MM-dd HH:mm:ss  ";
});

builder.Services
    .AddMcpServer()
    .WithHttpTransport()
    .WithToolsFromAssembly();

var app = builder.Build();

app.MapMcp("/sse");

app.Logger.LogInformation("Starting SPARS Sales MCP server on http://localhost:8001/sse");

app.Run("http://0.0.0.0:8001");
