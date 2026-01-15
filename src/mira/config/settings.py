"""
Settings configuration for MIRA using Pydantic Settings.

Environment variables are used for configuration, with optional .env file support.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="MIRA", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Datadog settings
    datadog_api_key: str | None = Field(
        default=None,
        description="Datadog API key",
    )
    datadog_app_key: str | None = Field(
        default=None,
        description="Datadog Application key",
    )
    datadog_site: str = Field(
        default="datadoghq.com",
        description="Datadog site (e.g., datadoghq.com, datadoghq.eu)",
    )

    # Azure DevOps settings
    azure_devops_pat: str | None = Field(
        default=None,
        description="Azure DevOps Personal Access Token",
    )
    azure_devops_organization_url: str | None = Field(
        default=None,
        description="Azure DevOps organization URL",
    )
    azure_devops_organization: str | None = Field(
        default=None,
        description="Azure DevOps organization name",
    )

    # Google ADK / LLM settings
    google_api_key: str | None = Field(
        default=None,
        description="Google API key for Gemini models",
    )
    llm_model: str = Field(
        default="gemini-2.0-flash",
        description="LLM model to use for agents",
    )

    # Service Registry settings
    service_registry_path: str = Field(
        default="config/service_registry.json",
        description="Path to service registry JSON file",
    )

    # Webhook settings
    webhook_secret: str | None = Field(
        default=None,
        description="Secret for validating webhook signatures",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
