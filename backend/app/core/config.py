import ipaddress
import re
import secrets
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NSS BloodConnect"
    app_env: str = "development"
    database_url: str = Field(default="sqlite:///./nss_bloodconnect.db", repr=False)
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trusted_hosts: str = "*"
    rate_limit_redis_url: str = Field(default="", repr=False)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = Field(default="", repr=False)
    smtp_password: str = Field(default="", repr=False)
    smtp_from_email: str = ""
    smtp_starttls: bool = True
    password_reset_token_expire_minutes: int = 30
    auth_cookie_enabled: bool = False
    auth_cookie_name: str = "nss_bloodconnect_session"
    csrf_cookie_name: str = "nss_bloodconnect_csrf"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    geocoding_provider: str = "nominatim"
    geocoding_user_agent: str = "NSSBloodConnect/1.0 (development)"
    geocoding_timeout_seconds: float = 5.0
    ai_enabled: bool = False
    ai_provider: str = ""
    ai_api_key: str = Field(default="", repr=False)
    ai_base_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 20.0
    nvidia_nim_api_key: str = Field(default="", repr=False)
    nvidia_nim_base_url: str = ""
    nvidia_nim_model: str = "deepseek-v4"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_config(self):
        env = (self.app_env or "").strip().lower()
        if env not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production.")
        if self.auth_cookie_samesite.lower() not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be Lax, Strict, or None.")
        if not self.jwt_secret.strip():
            raise ValueError("JWT_SECRET must not be empty.")

        if env in {"production", "staging"}:
            if not self.database_url or self.database_url.lower().startswith("sqlite"):
                raise ValueError("Production DATABASE_URL must be set to a PostgreSQL connection string. SQLite is not allowed in production.")
            normalized_secret = self.jwt_secret.strip()
            placeholder_prefixes = (
                "replace-",
                "change-me",
                "your-",
                "example-",
                "placeholder",
            )
            if "jwt_secret" not in self.model_fields_set:
                raise ValueError("Production JWT_SECRET must be supplied externally.")
            if (
                len(normalized_secret) < 32
                or len(set(normalized_secret)) < 12
                or normalized_secret.lower().startswith(placeholder_prefixes)
                or normalized_secret in {
                    "change-me-in-production",
                    "super-secret-key",
                    "development-only-default-change-me",
                }
            ):
                raise ValueError("Production JWT_SECRET must be set to a strong external secret of at least 32 characters.")
            configured_origins = [
                origin.strip()
                for origin in self.cors_origins.split(",")
                if origin.strip()
            ]
            if not configured_origins or "*" in configured_origins:
                raise ValueError("Production CORS_ORIGINS must be explicit values, not a wildcard.")
            for origin in configured_origins:
                parsed_origin = urlsplit(origin)
                if (
                    parsed_origin.scheme != "https"
                    or not parsed_origin.hostname
                    or parsed_origin.username is not None
                    or parsed_origin.password is not None
                    or parsed_origin.path
                    or parsed_origin.query
                    or parsed_origin.fragment
                ):
                    raise ValueError("Production CORS_ORIGINS must contain valid HTTPS origins only.")
            if self.frontend_url not in configured_origins:
                raise ValueError("Production FRONTEND_URL must be included in CORS_ORIGINS.")
            configured_hosts = [
                host.strip()
                for host in self.trusted_hosts.split(",")
                if host.strip()
            ]
            if not configured_hosts or "*" in configured_hosts:
                raise ValueError("Production TRUSTED_HOSTS must contain explicit hostnames, not a wildcard.")
            for host in configured_hosts:
                try:
                    parsed_host = urlsplit(f"//{host}")
                    port = parsed_host.port
                except ValueError as exc:
                    raise ValueError("Production TRUSTED_HOSTS must contain valid hostnames without ports.") from exc
                if (
                    not parsed_host.hostname
                    or parsed_host.username is not None
                    or parsed_host.password is not None
                    or parsed_host.path
                    or parsed_host.query
                    or parsed_host.fragment
                    or port is not None
                    or parsed_host.netloc.lower() != host.lower()
                ):
                    raise ValueError("Production TRUSTED_HOSTS must contain hostnames only, without schemes or ports.")
                try:
                    ipaddress.ip_address(parsed_host.hostname)
                except ValueError:
                    try:
                        ascii_hostname = parsed_host.hostname.encode("idna").decode("ascii")
                    except UnicodeError as exc:
                        raise ValueError("Production TRUSTED_HOSTS contains an invalid hostname.") from exc
                    labels = ascii_hostname.rstrip(".").split(".")
                    if any(
                        not label
                        or len(label) > 63
                        or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                        for label in labels
                    ):
                        raise ValueError("Production TRUSTED_HOSTS contains an invalid hostname.")
            if not self.rate_limit_redis_url:
                raise ValueError("Production RATE_LIMIT_REDIS_URL must be configured.")
            if not self.rate_limit_redis_url.lower().startswith("rediss://"):
                raise ValueError("Production RATE_LIMIT_REDIS_URL must use TLS.")
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("Production SMTP_HOST and SMTP_FROM_EMAIL must be configured.")
            if not self.smtp_starttls:
                raise ValueError("Production SMTP_STARTTLS must be enabled.")
            if bool(self.smtp_username) != bool(self.smtp_password):
                raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must either both be set or both be empty.")
            if self.auth_cookie_enabled and not self.auth_cookie_secure:
                raise ValueError("Production auth cookies require AUTH_COOKIE_SECURE=true.")
            if self.auth_cookie_samesite.lower() == "none" and not self.auth_cookie_secure:
                raise ValueError("SameSite=None auth cookies require AUTH_COOKIE_SECURE=true.")

        return self


settings = Settings()
