import logging
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Get project root directory (one level up from app/)
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # OpenRouter settings
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_model: str = Field(
        ...,
        description="OpenRouter model to use (e.g., openai/gpt-4o-mini, google/gemini-2.0-flash-001)",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )

    # Security
    api_proxy_secret: str = Field(
        ...,
        description="Secret for authenticating requests from Django backend (REQUIRED, no default)",
    )

    # Application settings
    app_name: str = Field(default="EatFit24 AI Proxy", description="Application name")
    log_level: str = Field(default="INFO", description="Logging level")

    # File upload limits
    max_image_size_bytes: int = Field(
        default=5 * 1024 * 1024,  # 5 MB
        description="Maximum allowed image file size in bytes",
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()

# Debug: log loaded settings (without sensitive data)
logger.info(
    f"Settings loaded: model={settings.openrouter_model}, base_url={settings.openrouter_base_url}"
)
