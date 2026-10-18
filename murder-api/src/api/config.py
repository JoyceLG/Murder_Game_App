"""Application settings, read from the environment (12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # When set, the app persists to SQL (e.g. postgresql+asyncpg://...); otherwise in-memory.
    database_url: str | None = None
    # Comma-separated CORS allowlist. Dev default = the Angular dev server. Add the Capacitor
    # WebView origins (capacitor://localhost, https://localhost) when the mobile app ships.
    allowed_origins: str = "http://localhost:4200"
    # Per-client-IP request budgets (per minute); 0 disables a limit.
    rate_limit_per_minute: int = 120  # every REST call + WebSocket handshake
    create_rate_limit_per_minute: int = 10  # game creation
    lookup_miss_limit_per_minute: int = 20  # requests for game codes that do not exist
    # Games older than this are deleted (finished or abandoned); swept every purge interval.
    game_ttl_hours: int = 24
    purge_interval_sec: int = 600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
