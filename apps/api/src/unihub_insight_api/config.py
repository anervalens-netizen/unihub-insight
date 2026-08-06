from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIHUB_INSIGHT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "UniHub Insight API"
    version: str = "1.0.0-rc.2"
    environment: Literal["development", "test", "production"] = "development"
    data_mode: Literal["demo", "postgres"] = "demo"
    auth_mode: Literal["demo", "proxy"] = "demo"
    database_url: str | None = None
    metadata_database_url: str | None = None
    allowed_origins: str = "http://localhost:3100"
    trusted_proxy_secret: str | None = None
    analytics_groups: str = "unihub-manager,unihub-analytics,unihub-admin,authentik Admins"
    management_groups: str = "unihub-manager,unihub-admin,authentik Admins"
    hr_groups: str = "unihub-hr,unihub-admin,authentik Admins"
    pnl_groups: str = "unihub-pnl,unihub-admin,authentik Admins"
    admin_groups: str = "unihub-admin,authentik Admins"
    db_pool_min_size: int = Field(default=1, ge=1, le=10)
    db_pool_max_size: int = Field(default=6, ge=2, le=20)
    metadata_pool_max_size: int = Field(default=3, ge=1, le=10)
    statement_timeout_ms: int = Field(default=2500, ge=250, le=5000)
    batch_deadline_ms: int = Field(default=8000, ge=1000, le=10000)

    @model_validator(mode="after")
    def validate_runtime(self) -> Settings:
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("db_pool_min_size cannot exceed db_pool_max_size")
        if self.data_mode == "postgres" and not self.database_url:
            raise ValueError("database_url is required in postgres mode")
        if self.auth_mode == "proxy" and not self.trusted_proxy_secret:
            raise ValueError("trusted_proxy_secret is required in proxy auth mode")
        if self.environment == "production":
            if self.data_mode == "demo":
                raise ValueError("production cannot run with demo data")
            if self.auth_mode == "demo":
                raise ValueError("production cannot run with demo authentication")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @staticmethod
    def parse_groups(value: str) -> frozenset[str]:
        return frozenset(item.strip() for item in value.split(",") if item.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
