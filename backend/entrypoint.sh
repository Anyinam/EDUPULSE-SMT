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
APP_ROLE=${APP_ROLE:-web}
RUN_DB_MIGRATIONS=${RUN_DB_MIGRATIONS:-false}
SEED_DEMO_DATA=${SEED_DEMO_DATA:-false}
GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}

export DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME APP_ROLE RUN_DB_MIGRATIONS SEED_DEMO_DATA GUNICORN_WORKERS

# Wait for PostgreSQL using Python (more reliable in containers)
python << 'WAIT_SCRIPT'
import os
import sys
import psycopg2
import time
from urllib.parse import urlparse

database_url = (os.getenv('DATABASE_URL') or '').strip()

host = os.getenv('DB_HOST') or os.getenv('DATABASE_HOST', 'db')
port = int(os.getenv('DB_PORT') or os.getenv('DATABASE_PORT', '5432'))
user = os.getenv('POSTGRES_USER', 'edupulse_user')
password = os.getenv('POSTGRES_PASSWORD', 'try123')

if database_url:
    parsed = urlparse(database_url)
    if parsed.hostname:
        host = parsed.hostname
    if parsed.port:
        port = parsed.port
    if parsed.username:
        user = parsed.username
    if parsed.password is not None:
        password = parsed.password

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
            print(f"  Last error: {e}")
            sys.exit(1)
        print(f"  PostgreSQL is unavailable (attempt {retry_count}/{max_retries}) - {e} - sleeping...")
        time.sleep(2)
WAIT_SCRIPT

if [ "$RUN_DB_MIGRATIONS" = "true" ]; then
    echo "🗂️  Running Alembic migrations..."
    alembic upgrade head
else
    echo "⏭️  Skipping automatic migrations (RUN_DB_MIGRATIONS=false)"
fi

if [ "$APP_ROLE" = "migrate" ]; then
    echo "✅ Migration task completed"
    exit 0
fi

if [ "$SEED_DEMO_DATA" = "true" ]; then
    echo "🌱 Seeding full demo data..."
    python backend/seed.py || echo "  ⚠️  Full seed script not available or already seeded"
elif [ "$SEED_DEMO_DATA" = "auto" ]; then
    echo "🌱 Auto-seeding the full local demo environment if the database is empty..."
    DEMO_SEED_STATE=$(python <<'EOF'
from backend.api.api import app
from backend.api.models import School

with app.app_context():
    print("empty" if School.query.count() == 0 else "populated")
EOF
)

    if [ "$DEMO_SEED_STATE" = "empty" ]; then
        if ! python backend/seed.py; then
            echo "  ⚠️  Full demo seed failed; falling back to minimal bootstrap"
            python backend/bootstrap_demo.py || echo "  ⚠️  Demo bootstrap script failed"
        fi
    else
        echo "⏭️  Demo seed skipped: database already has school data"
    fi
else
    echo "⏭️  Demo seeding disabled"
fi

echo "🎉 Backend initialization complete!"

if [ "$APP_ROLE" = "scheduler" ]; then
    export ENABLE_SCHEDULER=true
    echo "🕒 Starting dedicated scheduler process..."
    exec python <<'EOF'
import signal
import time

from backend.api.api import app

def _shutdown(_signum, _frame):
        raise SystemExit(0)

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

with app.app_context():
        while True:
                time.sleep(60)
EOF
fi

export ENABLE_SCHEDULER=${ENABLE_SCHEDULER:-false}
echo "🌐 Starting Flask application on 0.0.0.0:5000..."

# Start Flask app with gunicorn
# Inside Docker, bind to 0.0.0.0 to allow inter-container communication
# Host access is controlled by docker-compose port mapping
exec gunicorn --bind 0.0.0.0:5000 --workers "$GUNICORN_WORKERS" --timeout 120 "backend.api.api:app"
