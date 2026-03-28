"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://undata:undata@localhost:5432/undata"
    undata_base_url: str = "http://localhost:8002"
    log_level: str = "INFO"

    # Keycloak OIDC
    keycloak_url: str = "http://localhost:8080"  # internal (backend→Keycloak)
    keycloak_external_url: str = "http://localhost:8080"  # browser-facing
    keycloak_realm: str = "undata"
    keycloak_client_id: str = "undata-backend"
    keycloak_client_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
