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
    CHATBOT_TIMEOUT: int = 180  # Timeout in seconds for Skills API calls

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

    # Insights Configuration
    INSIGHTS_CACHE_DIR: str = "static/insights"  # Directory for cached insights
    INSIGHTS_CACHE_TTL: int = 86400  # Cache TTL in seconds (24 hours)
    INSIGHTS_MODEL: str = "claude-sonnet-4-5"  # Model for insights generation

    # Orchestrator Configuration (Autonomous Agents)
    ORCHESTRATOR_ENABLED: bool = True  # Enable/disable autonomous agents
    ORCHESTRATOR_TIMEZONE: str = "Asia/Kolkata"  # Timezone for scheduled jobs

    # External APIs for Demand Forecasting
    OPENWEATHERMAP_API_KEY: str = ""  # Free tier: 1000 calls/day
    ABSTRACTAPI_HOLIDAYS_KEY: str = ""  # Free tier: 1000 calls/month
    RESTAURANT_LOCATION: str = "Bangalore, India"  # Location for weather/events

    # Agent Configuration
    AGENT_MODEL_DEFAULT: str = "claude-sonnet-4-5"  # Default model for agents
    AGENT_MODEL_LIGHT: str = "claude-haiku-4-5"  # Lighter model for simple tasks
    AGENT_MAX_ITERATIONS: int = 10  # Max tool-calling iterations
    AGENT_TIMEOUT: int = 180  # Timeout for agent execution (seconds)

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
