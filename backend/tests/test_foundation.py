import json
import logging
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from car_support.config import Settings, get_settings
from car_support.db.session import get_engine
from car_support.observability import JsonFormatter, request_id

BACKEND = Path(__file__).resolve().parent.parent


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
@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_migrations_run_on_real_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        url = pg.get_connection_url()
        monkeypatch.setenv("CS_DATABASE_URL", url)
        get_settings.cache_clear()
        get_engine.cache_clear()

        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

        with create_engine(url).connect() as conn:
            assert conn.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")) == "vector"
