"""Logs, metrics and traces.

- Logs: JSON lines with a per-request ID carried in a context variable.
- Metrics: Prometheus counters and histograms, served at /metrics (Grafana dashboard in infra/grafana).
- Traces: OpenTelemetry spans of every graph step, sent to a self-hosted Arize Phoenix (opt-in).
"""

import json
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from prometheus_client import Counter, Histogram

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
log = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id.get(),
            **getattr(record, "fields", {}),  # log.info("...", extra={"fields": {...}})
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)


# ── Metrics ────────────────────────────────────────────────────────────────────

_SECONDS = (0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60)

ANSWERS = Counter("cs_answers_total", "Chat replies by outcome and market", ["outcome", "market"])
ANSWER_SECONDS = Histogram("cs_answer_seconds", "Time to the final answer", ["outcome"], buckets=_SECONDS)
STEP_SECONDS = Histogram("cs_step_seconds", "Time per pipeline step", ["step"], buckets=_SECONDS)
CACHE = Counter("cs_answer_cache_total", "Answer cache lookups", ["result"])  # hit | miss
FEEDBACK = Counter("cs_feedback_total", "Customer ratings", ["rating"])  # helpful | unhelpful
HANDOFFS = Counter("cs_handoffs_total", "Conversations handed to a person", ["reason"])
TOOL_ERRORS = Counter("cs_tool_errors_total", "Live tool calls that failed", ["tool"])
MODEL_ERRORS = Counter(
    "cs_model_errors_total", "Model calls that failed after retries and fallbacks", ["step"]
)
BLOCKED = Counter("cs_blocked_total", "Messages refused as prompt-injection attempts")


def timed[**P, R](step: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record a pipeline step's duration in cs_step_seconds."""

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                STEP_SECONDS.labels(step).observe(time.perf_counter() - started)

        return wrapper

    return decorate


# ── Traces ─────────────────────────────────────────────────────────────────────


def setup_tracing(endpoint: str, project: str = "car-support") -> Any:
    """Send LangChain/LangGraph spans to Phoenix (or any OTLP/HTTP collector). Returns the tracer provider."""
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    provider = register(endpoint=endpoint, project_name=project, batch=True, verbose=False)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    log.info("tracing enabled", extra={"fields": {"endpoint": endpoint, "project": project}})
    return provider
