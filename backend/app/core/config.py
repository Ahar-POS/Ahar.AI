"""
Application configuration using Pydantic Settings.

Loads environment variables and provides typed configuration access.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Ahar.AI Restaurant POS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_PREFIX: str = "/api/v1"
    API_PORT: int = 8000

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "ahar_pos"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Session Configuration
    SESSION_EXPIRE_HOURS: int = 24
    SESSION_REMEMBER_ME_DAYS: int = 30
    SESSION_COOKIE_NAME: str = "session_token"
    SESSION_COOKIE_SECURE: bool = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"

    # AI Configuration (placeholder for future use)
    AI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""

    # Claude API for admin chatbot with Skills API
    CLAUDE_API_KEY: str = ""
    CHATBOT_MODEL: str = "claude-haiku-4-5"  # Cost-optimized model

    # Skills API Configuration
    SKILLS_PATH: str = "skills"  # Path to skills directory
    DATA_PATH: str = "lexis_test_data"  # Path to data directory
    REPORTS_DIR: str = "static/reports"  # Directory for generated reports

    # Skills API Beta Headers
    SKILLS_BETA_HEADERS: list = [
        "code-execution-2025-08-25",
        "skills-2025-10-02",
        "files-api-2025-04-14"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings singleton.
    """
    return Settings()
