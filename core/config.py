"""Application settings loaded from environment via Pydantic."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables.

    All settings are loaded from environment. See .env.example for defaults.
    No os.getenv calls exist outside this module — enforced by grep gates.
    """

    # Database
    database_url: str = (
        "postgresql+asyncpg://exotica:exotica_dev_password@localhost:5432/exotica_dev"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Secrets management
    secrets_provider: Literal["env", "aws"] = "env"
    jwt_secret_arn: str = "dev-jwt-secret"
    aws_region: str | None = None

    # Application
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "DEBUG"
    app_name: str = "exotica-service-platform"
    process_type: Literal["web", "worker", "scheduler"] = "web"

    # CORS
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:8000,http://localhost:8001,http://localhost:5173"

    # Idempotency
    idempotency_retention_hours: int = 24

    # ServiceTitan integration (sandbox or production)
    servicetitan_api_key: str = ""
    servicetitan_api_endpoint: str = "https://api.servicetitan.com"
    servicetitan_request_timeout: int = 30

    # QuickBooks integration (sandbox or production)
    quickbooks_realm_id: str = ""
    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_refresh_token: str = ""
    quickbooks_environment: Literal["sandbox", "production"] = "sandbox"
    quickbooks_request_timeout: int = 30

    # HTTP client retry settings
    http_max_retries: int = 3
    http_retry_backoff_factor: float = 0.3

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Cached Settings instance. Subsequent calls return the same object.
    """
    return Settings()
