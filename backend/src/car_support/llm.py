"""Access to models. Embeddings come from Ollama's /api/embed; chat models from any LangChain provider."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from car_support.config import get_settings
from car_support.db.models import EMBED_DIM


def _provider_model(spec: str) -> BaseChatModel:
    """One chat model from a "<provider>:<model>" spec, deterministic (temperature 0)."""
    settings = get_settings()
    provider = spec.split(":", 1)[0]
    kwargs: dict[str, Any] = {"temperature": 0}
    if provider == "ollama":
        # reasoning=False skips the <think> phase of hybrid models: lookups need no long reasoning.
        kwargs |= {"base_url": settings.ollama_url, "reasoning": False, "client_kwargs": {"timeout": 120}}
    else:
        kwargs |= {"timeout": 60, "max_retries": 2}
        if provider == "groq" and settings.groq_api_key:
            kwargs["api_key"] = settings.groq_api_key.get_secret_value()
        if "gpt-oss" in spec:  # reasoning model: support lookups need little reasoning, keep it fast
            kwargs["reasoning_effort"] = "low"
    model: BaseChatModel = init_chat_model(spec, **kwargs)
    return model


def _fallback_specs() -> list[str]:
    return [s.strip() for s in get_settings().fallback_chat_model.split(",") if s.strip()]


def _resilient(primary: Runnable[Any, Any], fallbacks: list[Runnable[Any, Any]]) -> Runnable[Any, Any]:
    """Retry once (a local Ollama runner that crashed is restarted on the next request), then try each
    fallback in order (free cloud tiers cap tokens per model per day, so a chain multiplies capacity)."""
    model = primary.with_retry(stop_after_attempt=2)
    return (
        model.with_fallbacks([f.with_retry(stop_after_attempt=2) for f in fallbacks]) if fallbacks else model
    )


@lru_cache
def chat_model() -> Runnable[Any, Any]:
    """The configured chat model, falling back along CS_FALLBACK_CHAT_MODEL if it errors."""
    primary = _provider_model(get_settings().chat_model)
    return _resilient(primary, [_provider_model(spec) for spec in _fallback_specs()])


@lru_cache
def structured_model[T](schema: type[T]) -> Runnable[Any, T]:
    """The configured chat model constrained to return `schema` (JSON-schema enforced where supported)."""
    primary = _provider_model(get_settings().chat_model).with_structured_output(schema, method="json_schema")
    fallbacks = [_provider_model(spec).with_structured_output(schema) for spec in _fallback_specs()]
    return _resilient(primary, fallbacks)


def embed_texts(texts: Sequence[str], batch_size: int = 32, on_cpu: bool = False) -> list[list[float]]:
    """Embed texts with the configured Ollama embedding model, in batches."""
    settings = get_settings()
    vectors: list[list[float]] = []
    with httpx.Client(base_url=settings.ollama_url, timeout=120) as client:
        for start in range(0, len(texts), batch_size):
            resp = client.post(
                "/api/embed",
                json={
                    "model": settings.embed_model,
                    "input": list(texts[start : start + batch_size]),
                    # Qwen3-Embedding is Matryoshka-trained: every model size can emit EMBED_DIM-long vectors.
                    "dimensions": EMBED_DIM,
                    "options": {"num_gpu": 0} if on_cpu else {},
                },
            )
            resp.raise_for_status()
            vectors.extend(resp.json()["embeddings"])
    return vectors


def embed_queries(queries: Sequence[str]) -> list[list[float]]:
    """Embed search queries. Qwen3-Embedding is trained with a task instruction on the query side only."""
    settings = get_settings()
    instruction = settings.embed_query_instruction
    texts = [f"Instruct: {instruction}\nQuery: {q}" if instruction else q for q in queries]
    return embed_texts(texts, on_cpu=settings.query_embedding_on_cpu)
