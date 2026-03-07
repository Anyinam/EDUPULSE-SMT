import os

from dotenv import load_dotenv

load_dotenv()  # This loads the variables from the .env file


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    if os.getenv("FLASK_ENV", "development").lower() == "production":
        if not SECRET_KEY or not JWT_SECRET_KEY:
            raise RuntimeError(
                "Startup blocked: SECRET_KEY and JWT_SECRET_KEY must be set in production."
            )
