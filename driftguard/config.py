from __future__ import annotations

from functools import lru_cache
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _running_on_vercel() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _default_db_path() -> str:
    # Vercel functions can only write to the ephemeral /tmp directory.
    return "/tmp/driftguard.db" if _running_on_vercel() else "./driftguard.db"


def _default_sync_processing() -> bool:
    # Serverless runtimes should not rely on background workers surviving after the response.
    return _running_on_vercel()


class DriftGuardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DRIFTGUARD_",
        extra="ignore",
        populate_by_name=True,
    )

    redis_url: str = Field(default="redis://localhost:6379", alias="DRIFTGUARD_REDIS_URL")
    db_path: str = Field(default_factory=_default_db_path, alias="DRIFTGUARD_DB_PATH")
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
    sync_processing: bool = Field(default_factory=_default_sync_processing, alias="DRIFTGUARD_SYNC_PROCESSING")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> DriftGuardSettings:
    return DriftGuardSettings()
