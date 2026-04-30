from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    cors_origins: list[str] = []
    environment: str = "development"
    log_level: str = "INFO"
    trust_proxy_header: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _check_production_cors(self) -> "Settings":
        if self.environment.lower() == "production":
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must be set explicitly in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not contain wildcard '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
