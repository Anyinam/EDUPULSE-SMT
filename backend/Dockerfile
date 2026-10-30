FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	poppler-utils \
	tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY backend /app/backend

# Files attached to onboarding emails (see IMPORT_TEMPLATE_ATTACHMENTS in backend/routes.py)
COPY DATA_IMPORT_TEMPLATE.csv /app/DATA_IMPORT_TEMPLATE.csv
COPY compliance/CONSENT_AND_NOTICE_TEMPLATES.md /app/compliance/CONSENT_AND_NOTICE_TEMPLATES.md

# Copy and make entrypoint executable
COPY backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENTRYPOINT ["/app/entrypoint.sh"]