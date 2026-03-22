import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()  # This loads the variables from the .env file


def _build_database_url() -> str:
    test_database_url = (os.getenv("TEST_DATABASE_URL") or "").strip()
    if test_database_url:
        return test_database_url

    database_host = (os.getenv("DATABASE_HOST") or "").strip()
    database_port = (os.getenv("DATABASE_PORT") or "5432").strip()
    postgres_user = (os.getenv("POSTGRES_USER") or "").strip()
    postgres_password = os.getenv("POSTGRES_PASSWORD") or ""
    postgres_db = (os.getenv("POSTGRES_DB") or "").strip()

    if database_host and postgres_user and postgres_db:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=postgres_user,
            password=postgres_password,
            host=database_host,
            port=int(database_port or "5432"),
            database=postgres_db,
        ).render_as_string(hide_password=False)

    return (os.getenv("DATABASE_URL") or "sqlite:///edupulse.db").strip()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    if os.getenv("FLASK_ENV", "development").lower() == "production":
        if not SECRET_KEY or not JWT_SECRET_KEY:
            raise RuntimeError(
                "Startup blocked: SECRET_KEY and JWT_SECRET_KEY must be set in production."
            )
