"""Database migration environment configuration."""

from __future__ import with_statement

from logging.config import fileConfig

from alembic import context
from flask import current_app
from sqlalchemy import create_engine, text


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_target_metadata():
    try:
        return current_app.extensions["migrate"].db.metadata
    except RuntimeError:
        return None


def get_engine():
    try:
        return current_app.extensions["migrate"].db.engine
    except RuntimeError:
        return create_engine(config.get_main_option("sqlalchemy.url"))


def get_engine_url():
    engine = get_engine()
    if engine is None:
        return config.get_main_option("sqlalchemy.url")
    return str(engine.url).replace("%", "%%")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=get_engine_url(),
        target_metadata=get_target_metadata(),
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = get_engine()

    with connectable.connect() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL)"
        ))
        connection.execute(text(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
        ))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=get_target_metadata(),
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
