"""Central application settings (Pydantic Settings, env-driven)."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./jobfit.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_ENABLED: bool = False
    FILE_STORAGE_PATH: str = "/tmp/jobfit_storage"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024
    LOG_LEVEL: str = "INFO"
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    WEIGHT_MANDATORY: float = 0.40
    WEIGHT_PREFERRED: float = 0.15
    WEIGHT_EXPERIENCE: float = 0.20
    WEIGHT_SKILL: float = 0.15
    WEIGHT_TRANSFERABILITY: float = 0.05
    WEIGHT_CONFIDENCE: float = 0.05
    SEMANTIC_THRESHOLD: float = 0.62
    TRANSFERABLE_THRESHOLD: float = 0.55

    # RL decision layer (additive; existing matcher stays authoritative).
    RL_ENABLED: bool = True
    RL_MODEL_PATH: str = "backend/app/nlp/rl/models/rl_policy.json"
    RL_MIN_OVERRIDE_CONF: float = 0.55

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
