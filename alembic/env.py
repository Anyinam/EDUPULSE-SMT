import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Load Flask app config
os.environ.setdefault("FLASK_APP", "backend.api.api")
os.environ.setdefault("FLASK_ENV", "development")

# Import the Flask app and database
try:
    from backend.api.api import app
    from backend.api.models import db

    target_metadata = db.metadata
except ImportError:
    # Fallback if Flask app can't be imported
    target_metadata = None

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def _resolve_database_url() -> str:
    app_database_url = None
    try:
        app_database_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    except Exception:
        app_database_url = None

    if app_database_url:
        return app_database_url

    from backend.config import _build_database_url

    return _build_database_url()


config.set_main_option("sqlalchemy.url", _resolve_database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    existing_connection = config.attributes.get("connection")
    if existing_connection is not None:
        connection = existing_connection
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
