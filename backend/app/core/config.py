from __future__ import annotations

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database / cache
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    # JWT (used from Stage 1 onwards; defined here so the env contract is complete)
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_ttl_minutes: int = Field(60, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(30, alias="REFRESH_TOKEN_TTL_DAYS")

    # Envelope encryption KEK (used from Stage 6 onwards)
    encryption_kek: str = Field(..., alias="ENCRYPTION_KEK")

    # CORS — comma-separated list of allowed origins
    cors_origins: str = Field("http://localhost:3300", alias="CORS_ORIGINS")

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
