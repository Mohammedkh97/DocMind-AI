"""
Application configuration using Pydantic BaseSettings.

Loads from environment variables and .env file. All settings are type-safe
and validated at startup, so configuration errors are caught immediately
rather than at runtime during document processing.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration for DocMind AI."""

    # --- Application ---
    app_name: str = "DocMind AI"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # --- API Keys ---
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    openai_api_key: str = Field(default="", description="OpenAI API key (optional fallback)")

    # --- Model Configuration ---
    primary_model: str = Field(
        default="gemini-2.5-flash",
        description="Primary VLM model for extraction"
    )
    fallback_model: str = Field(
        default="gemini-2.0-flash",
        description="Fallback model if primary fails"
    )
    model_temperature: float = Field(
        default=0.0,
        description="Temperature for extraction (0 = deterministic)"
    )
    model_max_retries: int = Field(
        default=2,
        description="Max retries on model API failure"
    )
    model_timeout_seconds: int = Field(
        default=60,
        description="Timeout for model API calls"
    )

    # --- Extraction Settings ---
    pdf_render_dpi: int = Field(
        default=200,
        description="DPI for rendering PDF pages to images"
    )
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum upload file size in MB"
    )
    confidence_high_threshold: float = Field(
        default=0.85,
        description="Threshold for 'high' confidence label"
    )
    confidence_low_threshold: float = Field(
        default=0.60,
        description="Threshold below which fields are flagged"
    )

    # --- OCR Settings ---
    enable_ocr_validation: bool = Field(
        default=True,
        description="Enable PaddleOCR as validation/fallback layer"
    )
    ocr_language: str = Field(
        default="en",
        description="OCR language"
    )

    # --- Image Preprocessing ---
    enable_image_enhancement: bool = Field(
        default=True,
        description="Apply image enhancement (denoise, contrast) before extraction"
    )

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    # --- Database ---
    database_url: str = Field(
        default="sqlite:///./docmind.db",
        description="Database connection string"
    )

    allowed_origins: list[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.

    Using lru_cache ensures settings are loaded once and reused,
    avoiding repeated .env file reads during request handling.
    """
    return Settings()
