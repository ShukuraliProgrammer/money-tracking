"""Konfiguratsiya faqat muhit o‘zgaruvchilari / .env faylidan o‘qiladi."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    encryption_key: SecretStr
    # Docker compose bu qiymatni o‘zi beradi; lokal ishga tushirishda .env’da yoziladi.
    database_url: str = "postgresql+asyncpg://moneytrack@localhost:5432/moneytrack"
    redis_url: str | None = None

    llm_provider: Literal["anthropic", "openai", "none"] = "none"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_attempts: int = 3
    llm_note_analysis: bool = True

    default_timezone: str = "Asia/Tashkent"
    default_currency: str = "UZS"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
