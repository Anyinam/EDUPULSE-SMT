import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from flask import current_app, has_app_context
from sqlalchemy import MetaData
from sqlalchemy.engine import make_url


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _alembic_config(database_url: str | None = None) -> Config:
    root = _project_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database_to_head() -> None:
    previous = os.environ.get("ALEMBIC_RUNNING")
    database_url = None
    if has_app_context():
        database_url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    os.environ["ALEMBIC_RUNNING"] = "1"
    try:
        config = _alembic_config(database_url=database_url)
        if has_app_context():
            from backend.api.models import db

            with db.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        else:
            command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_RUNNING", None)
        else:
            os.environ["ALEMBIC_RUNNING"] = previous


def _reset_sqlite_database_file(db) -> bool:
    database_url = make_url(str(db.engine.url))
    if not database_url.drivername.startswith("sqlite"):
        return False

    database_path = database_url.database
    if not database_path or database_path == ":memory:":
        return False

    db.session.remove()
    db.engine.dispose()
    Path(database_path).unlink(missing_ok=True)
    return True


def rebuild_database_from_migrations(db) -> None:
    if not _reset_sqlite_database_file(db):
        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        metadata.drop_all(bind=db.engine)
    upgrade_database_to_head()