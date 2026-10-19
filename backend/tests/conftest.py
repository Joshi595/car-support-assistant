import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from car_support.config import get_settings
from car_support.db.session import get_engine

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A throwaway Postgres + pgvector with all migrations applied; CS_DATABASE_URL points at it."""
    if shutil.which("docker") is None:
        pytest.skip("Docker not installed")
    from testcontainers.community.postgres import PostgresContainer

    with (
        PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg,
        pytest.MonkeyPatch.context() as mp,
    ):
        url = pg.get_connection_url()
        mp.setenv("CS_DATABASE_URL", url)
        get_settings.cache_clear()
        get_engine.cache_clear()
        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
        yield url
    get_settings.cache_clear()
    get_engine.cache_clear()
