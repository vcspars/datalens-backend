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

    # JWT settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production-use-env-variable"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours (was 30 min)
    
    # CORS settings
    # For development, you can use ["*"] to allow all origins
    # For production, specify exact origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000", 
        "http://localhost:8080",
        "http://localhost:8081",
        "http://122.129.80.228:8080",
        "http://122.129.80.228:4173"
    ]
     
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

