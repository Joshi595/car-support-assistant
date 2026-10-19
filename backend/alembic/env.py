"""Alembic migration environment: runs migrations online against the configured database."""

from logging.config import fileConfig

from alembic import context

import car_support.db.models  # noqa: F401  (registers the tables on Base.metadata)
from car_support.db.session import Base, get_engine

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
