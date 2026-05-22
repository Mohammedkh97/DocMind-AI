"""
FastAPI dependency injection providers.

These are shared dependencies injected into route handlers.
Using dependency injection:
- Makes testing easier (swap real services for mocks)
- Ensures proper resource lifecycle management
- Keeps route handlers thin
"""

from functools import lru_cache

from core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Provide application settings to route handlers."""
    return get_settings()
