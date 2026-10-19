"""Typed settings, read from environment variables (prefix CS_) or a .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CS_", env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    data_dir: Path = Path(__file__).resolve().parents[3] / "data"  # repo-root/data in a source checkout

    database_url: str = "postgresql+psycopg://car_support:car_support@localhost:5432/car_support"

    ollama_url: str = "http://localhost:11434"
    # "<provider>:<model>" as understood by LangChain's init_chat_model, e.g. "groq:llama-3.3-70b-versatile".
    chat_model: str = "ollama:gemma3:4b"
    embed_model: str = "qwen3-embedding:0.6b"

    chunk_max_chars: int = 1200  # longer sections are split further; each piece keeps the heading prefix
    chunk_overlap: int = 150


@lru_cache
def get_settings() -> Settings:
    return Settings()
