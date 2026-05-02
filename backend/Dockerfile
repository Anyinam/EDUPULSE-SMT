FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	poppler-utils \
	tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . backend/

# Copy and make entrypoint executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENTRYPOINT ["/app/entrypoint.sh"]