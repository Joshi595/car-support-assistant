"""Typed settings, read from environment variables (prefix CS_) or a .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CS_", env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    data_dir: Path = Path(__file__).resolve().parents[3] / "data"  # repo-root/data in a source checkout

    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and adds ~2 s per new connection.
    database_url: str = "postgresql+psycopg://car_support:car_support@127.0.0.1:5432/car_support"

    ollama_url: str = "http://127.0.0.1:11434"
    # "<provider>:<model>" as understood by LangChain's init_chat_model, e.g. "groq:openai/gpt-oss-120b".
    chat_model: str = "ollama:gemma3:4b"
    # Comma-separated chain tried in order when the chat model fails, e.g. after a free tier's daily cap:
    # "groq:openai/gpt-oss-20b,ollama:gemma3:4b". Empty = no fallback.
    fallback_chat_model: str = ""
    groq_api_key: SecretStr | None = None  # free key from console.groq.com, used for "groq:..." models
    # Optional injection classifier on top of the built-in rules, e.g.
    # "groq:meta-llama/llama-prompt-guard-2-86m". It sends every customer message to Groq, so it is off by
    # default (the local setup stays private).
    prompt_guard_model: str = ""
    prompt_guard_threshold: float = 0.5

    embed_model: str = "qwen3-embedding:4b"  # "qwen3-embedding:0.6b" for low-memory machines
    # Embed questions on the CPU (~0.5 s) so the chat model stays loaded on a small GPU; swapping the two
    # models on a 6 GB card cost 5-10 s per question. Set false with enough GPU memory for both.
    query_embedding_on_cpu: bool = True
    # Instruction prepended to search queries (Qwen3-Embedding convention); empty string = no instruction.
    embed_query_instruction: str = (
        "Given a customer question about a car maker's products and services, "
        "retrieve passages that answer it"
    )

    chunk_max_chars: int = 1200  # longer sections are split further; each piece keeps the heading prefix
    chunk_overlap: int = 150

    top_k: int = 4  # passages given to the chat model
    # Dense search wins with qwen3-embedding:4b (ADR 0003); hybrid stays available.
    retrieval_mode: Literal["dense", "hybrid", "keyword"] = "dense"
    candidates: int = 30  # per-ranker pool before fusion (hybrid mode)
    keyword_weight: float = 0.1  # weight of full-text ranks in hybrid fusion (dense = 1.0)
    answer_cache: bool = True  # exact-match cache of knowledge-base answers (see pipeline/cache.py)
    relevance_threshold: float = 0.40  # top cosine similarity below this = clearly off-topic (ADR 0003)

    # Observability. Traces go to a self-hosted Phoenix, e.g. "http://127.0.0.1:6006/v1/traces"; empty = off.
    tracing_endpoint: str = ""

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]  # the frontend
    chat_rate_limit: str = "20/minute"  # per client IP
    agent_jwt_secret: SecretStr | None = None  # shared with the frontend's Auth.js; unset = agent routes off

    # Live tools. Open Charge Map needs a free key (openchargemap.org); without one the tool says so.
    open_charge_map_key: str = ""
    http_user_agent: str = "car-support-assistant/0.1 (+https://github.com/Joshi595/car-support-assistant)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
