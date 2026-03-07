#!/bin/bash
set -e

echo "🚀 Starting EduPulse Backend..."
echo "⏳ Waiting for PostgreSQL to be ready..."

# Set defaults
DB_HOST=${DATABASE_HOST:-db}
DB_PORT=${DATABASE_PORT:-5432}
DB_USER=${POSTGRES_USER:-edupulse_user}
DB_PASSWORD=${POSTGRES_PASSWORD:-try123}
DB_NAME=${POSTGRES_DB:-edupulse_db}

# Wait for PostgreSQL using Python (more reliable in containers)
python << 'WAIT_SCRIPT'
import os
import sys
import psycopg2
import time

host = os.getenv('DB_HOST', 'db')
port = int(os.getenv('DB_PORT', '5432'))
user = os.getenv('POSTGRES_USER', 'edupulse_user')
password = os.getenv('POSTGRES_PASSWORD', 'try123')

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'  # Connect to system database
        )
        conn.close()
        print("✅ PostgreSQL is ready!")
        break
    except psycopg2.OperationalError as e:
        retry_count += 1
        if retry_count >= max_retries:
            print(f"❌ Failed to connect to PostgreSQL after {max_retries} attempts")
            sys.exit(1)
        print(f"  PostgreSQL is unavailable (attempt {retry_count}/{max_retries}) - sleeping...")
        time.sleep(2)
WAIT_SCRIPT

# Run Flask database initialization
echo "🔧 Initializing database schema..."
python << 'EOF'
import os
os.environ['FLASK_APP'] = 'backend.api.api'
os.environ['FLASK_ENV'] = os.getenv('FLASK_ENV', 'production')

from backend.api.api import app
from backend.api.models import db

with app.app_context():
    print("  Creating tables from models...")
    try:
        db.create_all()
        print("  ✅ Database schema created!")
    except Exception as e:
        print(f"  ⚠️  Error creating tables: {e}")
        print("  (This may be OK if tables already exist)")
EOF

# Run seed data if demo mode
if [ "${DEMO_MODE:-true}" = "true" ]; then
  echo "🌱 Seeding demo data..."
  python backend/seed.py || echo "  ⚠️  Seed script not available or already seeded"
fi

echo "🎉 Backend initialization complete!"
echo "🌐 Starting Flask application on 0.0.0.0:5000..."

# Start Flask app with gunicorn
# Inside Docker, bind to 0.0.0.0 to allow inter-container communication
# Host access is controlled by docker-compose port mapping
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 "backend.api.api:app"
