FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install OS deps — tini for proper signal handling, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps — mirror the backend requirements for the scanner
COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy scanner + backend modules (scanner imports backend via sys.path)
COPY scanner/ /app/scanner/
COPY backend/ /app/backend/

# Run as non-root
RUN useradd -u 1000 -m scanner && chown -R scanner:scanner /app
USER scanner

EXPOSE 8765

# tini reaps zombies and forwards SIGTERM to python — clean shutdown
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "scanner.scanner"]
