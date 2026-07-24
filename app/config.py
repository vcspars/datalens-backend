"""Configuration settings for the application"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "datalens_db"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # SQL Server (for LangChain chat with database)
    SQL_SERVER: str = ""
    SQL_DATABASE: str = ""
    SQL_USER: str = ""
    SQL_PASSWORD: str = ""
    SQL_DRIVER: str = "ODBC Driver 17 for SQL Server"

    # Chat with Database: True = Vanna AI, False = LangChain
    USE_VANNA_AI: bool = False

    # Gemini: True = use Gemini 2.5 Pro for chat SQL agent, False = use GPT
    USE_GEMINI: bool = False
    GEMINI_API_KEY: str = ""

    # --- MCP (Model Context Protocol) — hosted tool server integration ---
    # Set MCP_SERVER_URL in .env to enable. Tools are cached at startup and
    # included as individual tools in the unified orchestrator agent's tool
    # list. Leave MCP_SERVER_URL empty to run the SQL subagent only.
    MCP_ENABLED: bool = True
    MCP_SERVER_URL: str = ""            # e.g. https://your-mcp-host.example.com/mcp
    MCP_API_KEY: str = ""               # optional — sent as "Authorization: Bearer <key>"
    MCP_TOOLS_REFRESH_MINUTES: float = 30.0   # auto-refresh cached tool catalog after this long

    # --- Unified orchestrator agent (outer ReAct loop) ---
    # Governs the single top-level agent that decides whether to call MCP
    # tools, the SQL subagent, or both. Timeout MUST exceed
    # SQL_AGENT_TIMEOUT_SECONDS because a single query_sql_database tool call
    # can itself run for the full SQL agent budget.
    ORCHESTRATOR_MAX_TOOL_CALLS: int = 6      # max outer tool calls (each MCP call + the SQL subagent call count toward this)
    ORCHESTRATOR_TIMEOUT_SECONDS: float = 300.0  # wall-clock budget for the whole orchestrator turn

    # --- SQL ReAct subagent (inner bounded loop, called via query_sql_database tool) ---
    # These bound the SQL-only agent that runs inside the query_sql_database
    # wrapper tool. Values are unchanged from before the unified-agent redesign.
    SQL_AGENT_MAX_TOOL_CALLS: int = 16        # max SQL tool calls per query_sql_database invocation
    SQL_AGENT_TIMEOUT_SECONDS: float = 280.0  # wall-clock budget per query_sql_database invocation

    # Swagger /docs password gate
    DOCS_PASSWORD: str = "sdf@#FDF23fd"

    # JWT settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production-use-env-variable"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours (was 30 min)
    
    # CORS settings
    # For development, you can use ["*"] to allow all origins
    # For production, specify exact origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:4173",   # Vite dev server (this project)
        "http://127.0.0.1:4173",
        "http://localhost:5173",   # Vite default port
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
    ]
     
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

