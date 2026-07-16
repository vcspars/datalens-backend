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
    # tried (via a bounded LangGraph ReAct loop) before falling back to the
    # LangChain SQL agent. Leave MCP_SERVER_URL empty to fully skip this path.
    MCP_ENABLED: bool = True
    MCP_SERVER_URL: str = ""            # e.g. https://your-mcp-host.example.com/mcp
    MCP_API_KEY: str = ""               # optional — sent as "Authorization: Bearer <key>"
    MCP_MAX_TOOL_CALLS: int = 6         # max MCP tool calls allowed per user turn
    MCP_AGENT_TIMEOUT_SECONDS: float = 60.0   # overall wall-clock budget for the MCP ReAct loop
    MCP_TOOLS_REFRESH_MINUTES: float = 30.0   # auto-refresh cached tool catalog after this long

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

