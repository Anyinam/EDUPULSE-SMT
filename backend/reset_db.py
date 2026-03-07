import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.api import app
from backend.api.models import db


def reset_database():
    with app.app_context():
        print("🗑️  Dropping all tables...")
        db.drop_all()
        print("✨ Creating all tables (Empty Schema)...")
        db.create_all()
        print("✅ Database reset complete.")


if __name__ == "__main__":
    reset_database()
