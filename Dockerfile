# Password vault app — single stage; config via env (12-factor).
# Build: docker build -t vault-app .
# Run: see docker-compose.yml (persist /data for DB and audit log).
FROM python:3.12-slim

WORKDIR /app

# Dependencies only (no dev/test in image for smaller prod image).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application and web UI (vault package lives under src/).
COPY src/ src/
COPY web/ web/
ENV PYTHONPATH=/app/src

# Defaults; override in compose or run (e.g. VAULT_DB_PATH=/data/vault.db).
ENV VAULT_DB_PATH=/data/vault.db \
    VAULT_AUDIT_LOG_PATH=/data/audit.log \
    VAULT_SESSION_TIMEOUT_MINUTES=15

EXPOSE 8000

# Run uvicorn; bind 0.0.0.0 so the container accepts connections from host.
CMD ["uvicorn", "vault.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
