# syntax=docker/dockerfile:1.6
# ↑ Required for --mount=type=secret (BuildKit)

# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# build-essential + gcc are needed to compile native extensions (chromadb, nh3).
# libpq-dev is needed for asyncpg (PostgreSQL async driver).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first so Docker's layer cache avoids reinstalling when only
# application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download embedding model weights ─────────────────────────────────────
# Bake model weights into the image at build time so the container starts
# without a network round-trip to HuggingFace Hub.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Vectorstore ingestion ─────────────────────────────────────────────────────
# The JWT_SECRET_KEY is read from a BuildKit secret mount so it is never
# stored in any image layer and does not appear in `docker history`.
#
# Build with:
#   DOCKER_BUILDKIT=1 docker build \
#     --secret id=jwt_secret,env=JWT_SECRET_KEY \
#     -t enterprise-agent .
#
# The secret is only available during this RUN step and is not persisted.
RUN --mount=type=secret,id=jwt_secret \
    JWT_SECRET_KEY="$(cat /run/secrets/jwt_secret)" \
    python -m scripts.ingest

# ── Non-root user ─────────────────────────────────────────────────────────────
# Running as root inside a container is unnecessary and increases blast radius
# if the process is compromised.  Create a minimal system account instead.
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

# ── Network ───────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ─────────────────────────────────────────────────────────────
# Orchestrators (Kubernetes, ECS, Compose) use this to detect hung processes.
# Requires a /health endpoint — add one to main.py if not already present.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import httpx, sys; \
         r = httpx.get('http://localhost:8000/health', timeout=4); \
         sys.exit(0 if r.status_code == 200 else 1)"

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
