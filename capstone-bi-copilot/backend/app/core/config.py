from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "AI Business Intelligence Copilot"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./business_agent.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    development_auth_email: str = ""
    frontend_url: str = "http://localhost:5173"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"
    oauth_token_encryption_key: str = ""
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    voice_stt_model: str = ""
    voice_tts_model: str = "gemini-2.5-flash-preview-tts"
    voice_tts_voice: str = "Kore"
    rag_top_k: int = 5
    upload_root: str = "./data/uploads"
    cors_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = 120
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    def ensure_paths(self) -> None:
        Path(self.upload_root).mkdir(parents=True, exist_ok=True)

@lru_cache
def get_settings() -> Settings:
    s=Settings(); s.ensure_paths(); return s
