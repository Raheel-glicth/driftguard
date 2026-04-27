from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DriftGuardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DRIFTGUARD_",
        extra="ignore",
        populate_by_name=True,
    )

    redis_url: str = Field(default="redis://localhost:6379", alias="DRIFTGUARD_REDIS_URL")
    db_path: str = Field(default="./driftguard.db", alias="DRIFTGUARD_DB_PATH")
    llm_judge_model: str = Field(default="gpt-4o-mini", alias="DRIFTGUARD_LLM_JUDGE_MODEL")
    llm_judge_api_key: str | None = Field(default=None, alias="DRIFTGUARD_LLM_JUDGE_API_KEY")
    injection_threshold: float = Field(default=0.7, alias="DRIFTGUARD_INJECTION_THRESHOLD")
    drift_threshold: float = Field(default=0.35, alias="DRIFTGUARD_DRIFT_THRESHOLD")
    trust_threshold: float = Field(default=0.5, alias="DRIFTGUARD_TRUST_THRESHOLD")
    embedding_model: str = Field(default="BAAI/bge-base-en-v1.5", alias="DRIFTGUARD_EMBEDDING_MODEL")
    log_level: str = Field(default="INFO", alias="DRIFTGUARD_LOG_LEVEL")
    chat_model: str = Field(default="gpt-4o-mini", alias="DRIFTGUARD_CHAT_MODEL")
    chat_system_prompt: str = Field(
        default="You are a helpful local AI assistant. Be concise, accurate, and transparent about uncertainty.",
        alias="DRIFTGUARD_CHAT_SYSTEM_PROMPT",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> DriftGuardSettings:
    return DriftGuardSettings()
