import json
import logging

import pytest
from sqlalchemy import create_engine, text

from car_support.config import Settings
from car_support.observability import JsonFormatter, request_id


def test_settings_read_prefixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CS_CHAT_MODEL", "groq:llama-3.3-70b-versatile")
    assert Settings().chat_model == "groq:llama-3.3-70b-versatile"


def test_json_log_carries_request_id_and_fields() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.fields = {"route": "retrieve"}
    token = request_id.set("req-42")
    try:
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id.reset(token)
    assert entry["msg"] == "hello world"
    assert entry["request_id"] == "req-42"
    assert entry["route"] == "retrieve"


@pytest.mark.integration
def test_migrations_create_pgvector_and_tables(database_url: str) -> None:
    with create_engine(database_url).connect() as conn:
        assert conn.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")) == "vector"
        tables = set(conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")))
    assert {"documents", "chunks", "kb_versions"} <= tables
