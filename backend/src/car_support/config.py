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

    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and adds ~2 s per new connection.
    database_url: str = "postgresql+psycopg://car_support:car_support@127.0.0.1:5432/car_support"

    ollama_url: str = "http://127.0.0.1:11434"
    # "<provider>:<model>" as understood by LangChain's init_chat_model, e.g. "groq:llama-3.3-70b-versatile".
    chat_model: str = "ollama:gemma3:4b"
    embed_model: str = "qwen3-embedding:4b"  # "qwen3-embedding:0.6b" for low-memory machines
    # Instruction prepended to search queries (Qwen3-Embedding convention); empty string = no instruction.
    embed_query_instruction: str = (
        "Given a customer question about a car maker's products and services, "
        "retrieve passages that answer it"
    )

    chunk_max_chars: int = 1200  # longer sections are split further; each piece keeps the heading prefix
    chunk_overlap: int = 150

    top_k: int = 4  # passages given to the chat model
    retrieval_mode: Literal["dense", "hybrid", "keyword"] = (
        "dense"  # dense wins with qwen3-embedding:4b (ADR 0003)
    )
    candidates: int = 30  # per-ranker pool before fusion (hybrid mode)
    keyword_weight: float = 0.1  # weight of full-text ranks in hybrid fusion (dense = 1.0)
    relevance_threshold: float = 0.40  # top cosine similarity below this = clearly off-topic (ADR 0003)


@lru_cache
def get_settings() -> Settings:
    return Settings()
