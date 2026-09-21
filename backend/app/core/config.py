from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NSS BloodConnect"
    app_env: str = "development"
    database_url: str = "sqlite:///./nss_bloodconnect.db"
    jwt_secret: str = "development-only-default-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    geocoding_provider: str = "nominatim"
    geocoding_user_agent: str = "NSSBloodConnect/1.0 (development)"
    geocoding_timeout_seconds: float = 5.0
    ai_enabled: bool = False
    ai_provider: str = ""
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 20.0
    nvidia_nim_api_key: str = ""
    nvidia_nim_base_url: str = ""
    nvidia_nim_model: str = "deepseek-v4"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_config(self):
        env = (self.app_env or "").lower()

        if env == "production":
            if not self.database_url or self.database_url.lower().startswith("sqlite"):
                raise ValueError("Production DATABASE_URL must be set to a PostgreSQL connection string. SQLite is not allowed in production.")
            if len(self.jwt_secret) < 32 or self.jwt_secret in {"change-me-in-production", "super-secret-key", "development-only-default-change-me"}:
                raise ValueError("Production JWT_SECRET must be set to a strong external secret of at least 32 characters.")
            if not self.cors_origins or self.cors_origins.strip() == "*":
                raise ValueError("Production CORS_ORIGINS must be explicit values, not a wildcard.")

        return self


settings = Settings()
