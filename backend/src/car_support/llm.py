"""Access to models. Embeddings come from Ollama's /api/embed (free, local)."""

from collections.abc import Sequence

import httpx

from car_support.config import get_settings


def embed_texts(texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
    """Embed texts with the configured Ollama embedding model, in batches."""
    settings = get_settings()
    vectors: list[list[float]] = []
    with httpx.Client(base_url=settings.ollama_url, timeout=120) as client:
        for start in range(0, len(texts), batch_size):
            resp = client.post(
                "/api/embed",
                json={"model": settings.embed_model, "input": list(texts[start : start + batch_size])},
            )
            resp.raise_for_status()
            vectors.extend(resp.json()["embeddings"])
    return vectors
