"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://undata:undata@localhost:5432/undata"
    undata_base_url: str = "http://localhost:8002"
    secret_key: str = "changeme"
    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "undata"
    keycloak_client_id: str = ""
    keycloak_client_secret: str = ""
    alias_similarity_threshold: float = 0.88
    token_cache_ttl_seconds: int = 300
    log_level: str = "INFO"
    qudt_ttl_path: str = "data/qudt/VOCAB_QUDT-UNITS-ALL.ttl"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
