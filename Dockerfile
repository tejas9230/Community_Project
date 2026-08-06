# ── Render Production Dockerfile ──────────────────
FROM python:3.10-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p static/uploads

EXPOSE 10000

ENV PORT=10000
ENV PYTHONUNBUFFERED=1

CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:app
