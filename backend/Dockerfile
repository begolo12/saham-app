FROM python:3.11-slim

WORKDIR /app

# Install build deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Ensure signals.db dir is writable
RUN chmod -R 777 /app

EXPOSE 8774

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8774"]
