from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Business Intelligence Copilot"
    environment: str = "development"
    database_url: str = "sqlite:///./app.db"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    vector_store_path: str = "./data/vector_store"
    web_search_api_key: str | None = None
    rate_limit_per_minute: int = 60
    session_ttl_minutes: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
