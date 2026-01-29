"""Configuration settings for the application"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "datalens_db"
    
    # JWT settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production-use-env-variable"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS settings
    # For development, you can use ["*"] to allow all origins
    # For production, specify exact origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000", 
        "http://localhost:8080",
        "http://localhost:8081"
    ]

    OPENAI_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

