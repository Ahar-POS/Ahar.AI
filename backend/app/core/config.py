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
    DATA_PATH: str = "new_test_data"  # Path to data directory (NEW schema)
    REPORTS_DIR: str = "static/reports"  # Directory for generated reports

    # Skills API Beta Headers
    SKILLS_BETA_HEADERS: list = [
        "code-execution-2025-08-25",
        "skills-2025-10-02",
        "files-api-2025-04-14"
    ]

    # Insights Configuration
    INSIGHTS_CACHE_DIR: str = "static/insights"  # Directory for cached insights
    INSIGHTS_CACHE_TTL: int = 604800  # Cache TTL in seconds (1 week)
    INSIGHTS_MODEL: str = "claude-sonnet-4-5-20250929"  # Model for insights generation

    # Static Directory
    STATIC_DIR: str = "static"  # Base static files directory

    # Orchestrator Configuration (Autonomous Agents)
    ORCHESTRATOR_ENABLED: bool = True  # Enable/disable autonomous agents
    ORCHESTRATOR_TIMEZONE: str = "Asia/Kolkata"  # Timezone for scheduled jobs

    # Revenue Anomaly Detection (legacy keys kept for backward compat)
    REVENUE_ANOMALY_THRESHOLD: float = 0.60
    REVENUE_ANOMALY_MIN_HISTORY_DAYS: int = 7

    # Operations Pulse Service
    PULSE_REVENUE_THRESHOLD: float = 0.60           # Alert if current-hour < 60% of historical avg
    PULSE_CHANNEL_THRESHOLD: float = 0.50           # Alert if channel revenue < 50% of baseline
    PULSE_KITCHEN_LATENCY_MULTIPLIER: float = 1.5   # Alert if avg kitchen time > 1.5× baseline
    PULSE_CANCELLATION_SPIKE_PP: float = 0.15       # Alert if cancellation rate > baseline + 15pp
    PULSE_AOV_THRESHOLD: float = 0.75               # Alert if AoV < 75% of baseline
    PULSE_DEAD_PERIOD_MINUTES: int = 30             # Minutes with no orders = dead period
    PULSE_TABLE_STALE_MINUTES: int = 20             # Minutes OCCUPIED table with no active order
    PULSE_MIN_HISTORY_DAYS: int = 7                 # Min history days to fire any alert

    # Smart Approval Thresholds (Phase 5)
    AUTO_APPROVE_LIMIT_INR: int = 5000       # Auto-approve if total order cost < this (rupees)
    AUTO_APPROVE_NEW_SUPPLIER: bool = False  # If True, auto-approve even for unknown suppliers

    # External APIs for Demand Forecasting
    OPENWEATHERMAP_API_KEY: str = ""  # Free tier: 1000 calls/day (forecast only)
    VISUALCROSSING_API_KEY: str = ""  # Free tier: 1000 calls/day (includes historical data!)
    NEWSAPI_KEY: str = ""  # Free tier: 100 calls/day
    ABSTRACTAPI_HOLIDAYS_KEY: str = ""  # Free tier: 1000 calls/month
    RESTAURANT_LOCATION: str = "Bangalore, India"  # Location for weather/events

    # Agent Configuration
    AGENT_MODEL_DEFAULT: str = "claude-sonnet-4-5"  # Default model for agents
    AGENT_MODEL_LIGHT: str = "claude-haiku-4-5"  # Lighter model for simple tasks
    AGENT_MAX_ITERATIONS: int = 10  # Max tool-calling iterations
    AGENT_TIMEOUT: int = 180  # Timeout for agent execution (seconds)
    AGENT_PRICE_ANOMALY_MULTIPLIER: float = 2.0      # escalate if current price > N× historical avg
    AGENT_TOTAL_AUTO_APPROVE_LIMIT_INR: int = 3000   # per-run auto-approve budget cap in INR

    # OCR and Document Processing Configuration
    UPLOAD_DIR: str = "uploads/documents"  # Directory for uploaded documents
    MAX_UPLOAD_SIZE_MB: int = 10  # Maximum upload file size in MB
    OCR_TIMEOUT_SEC: int = 30  # Timeout for OCR processing
    PRICE_VARIANCE_THRESHOLD_PCT: float = 0.05  # 5% price variance threshold for warnings

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
