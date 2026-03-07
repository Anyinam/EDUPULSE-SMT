import os

from dotenv import load_dotenv

load_dotenv()  # This loads the variables from the .env file


class Config:
    # Use the secret from .env, or fall back to a dummy for safety
    SECRET_KEY = os.getenv("SECRET_KEY", "default-unsafe-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "pisa-dev-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
