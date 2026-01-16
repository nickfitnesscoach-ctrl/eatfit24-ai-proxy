import logging
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Project root (one level up from app/)
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Env contract is STRICT:
    every variable uses explicit validation_alias to avoid silent misconfiguration
    in Docker / CI / VPS environments.
    """

    # ============================
    # OpenRouter configuration
    # ============================
    openrouter_api_key: str = Field(
        ...,
        validation_alias="OPENROUTER_API_KEY",
        description="OpenRouter API key",
    )

    openrouter_model: str = Field(
        ...,
        validation_alias="OPENROUTER_MODEL",
        description="OpenRouter model to use for main recognition (e.g. openai/gpt-4o-mini)",
    )

    openrouter_gate_model: str = Field(
        default="",
        validation_alias="OPENROUTER_GATE_MODEL",
        description="Optional separate model for gate check. If empty, uses openrouter_model",
    )

    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
        description="OpenRouter API base URL",
    )

    # ============================
    # Security
    # ============================
    api_proxy_secret: str = Field(
        ...,
        validation_alias="API_PROXY_SECRET",
        description="Secret key for authenticating requests from backend",
    )

    # ============================
    # App / runtime settings
    # ============================
    app_name: str = Field(
        default="EatFit24 AI Proxy",
        validation_alias="APP_NAME",
        description="Application name",
    )

    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Logging level",
    )

    max_image_size_bytes: int = Field(
        default=5 * 1024 * 1024,  # 5 MB
        validation_alias="MAX_IMAGE_SIZE_BYTES",
        description="Maximum allowed image size in bytes",
    )

    # ============================
    # Food Gate (Anti-Hallucination)
    # ============================
    food_gate_threshold: float = Field(
        default=0.60,
        validation_alias="FOOD_GATE_THRESHOLD",
        description="Minimum confidence to pass food gate (reject if below)",
    )

    recognition_threshold: float = Field(
        default=0.65,
        validation_alias="RECOGNITION_THRESHOLD",
        description="Recognition confidence threshold (future use)",
    )

    error_http200_compat: bool = Field(
        default=False,
        validation_alias="AI_PROXY_ERROR_HTTP200_COMPAT",
        description="If true, return HTTP 200 for errors (legacy backend compat)",
    )

    # ============================
    # Pydantic settings config
    # ============================
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env")
        if (PROJECT_ROOT / ".env").exists()
        else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ============================
# Global settings instance
# ============================
settings = Settings()

# ============================
# Safe startup log (NO secrets)
# ============================
try:
    env_path = PROJECT_ROOT / ".env"
    logger.info(
        "Settings loaded: model=%s base_url=%s max_image_size=%s env_file=%s",
        settings.openrouter_model,
        settings.openrouter_base_url,
        settings.max_image_size_bytes,
        str(env_path) if env_path.exists() else "ENV_ONLY",
    )
except Exception:
    # Config must NEVER crash import
    pass
