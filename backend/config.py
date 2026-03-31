from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Explainable Route Planner"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///data/route_planner.db"
    planner_mode: str = "local"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-haiku-20240307"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
