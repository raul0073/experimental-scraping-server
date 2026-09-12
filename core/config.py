from __future__ import annotations
from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- Server / App ----
    APP_NAME: str = Field(default="Experimental API", description="App display name")
    PORT: int = Field(default=8080, description="Server port")
    TZ: str = Field(default="Asia/Jerusalem", description="IANA time zone")
    HOST_URL: AnyHttpUrl = Field(
        default="http://127.0.0.1:8080",
        description="Public base URL of this service"
    )

    # ---- Mongo (legacy, unused — kept optional so old envs don't break) ----
    MONGODB_URI: str | None = None
    DB_NAME: str | None = None

    # ---- Auth / Admin ----
    ADMIN_KEY: SecretStr | None = None

    # ---- External / APIs ----
    OPENAI_KEY: SecretStr | None = None

    # Optional email & OAuth (keep optional if you don’t use them yet)
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int | None = None
    EMAIL_USER: str | None = None
    EMAIL_PASSWORD: SecretStr | None = None
    GOOGLE_CLIENT_ID: str | None = None

    # Winner base (client of your scraper; override via env when deployed)
    WINNER_BASE_URL: AnyHttpUrl = Field(
        default="http://127.0.0.1:8080/api/v3",
        description="Base URL for Winner proxy API"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,  # your envs are uppercase; keep it strict
        extra="ignore",       # ignore unexpected envs instead of failing
    )


settings = Settings()
