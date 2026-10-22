import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from backend.infrastructure.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

MIGRATION_LOCK_KEY = 734622


def database_url():
    url = config.attributes.get('db_url')
    if not url:
        url = context.get_x_argument(as_dictionary=True).get('db_url')
    if not url:
        url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL, -x db_url=... or config.attributes["db_url"] is required')
    return url


def configure(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=False,
        include_schemas=False,
        render_as_batch=False,
        **kwargs,
    )


def run_migrations_offline():
    configure(
        url=database_url(),
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text("SET lock_timeout = '30s'"))
        locked = connection.scalar(text(f'SELECT pg_try_advisory_lock({MIGRATION_LOCK_KEY})'))
        if not locked:
            raise RuntimeError('Another FGAS migration is already running')
        connection.commit()
        try:
            configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text(f'SELECT pg_advisory_unlock({MIGRATION_LOCK_KEY})'))
            connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
