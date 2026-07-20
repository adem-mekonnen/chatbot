# syntax=docker/dockerfile:1.6

# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Install system dependencies needed for compiling certain Python packages
# libpq-dev is for PostgreSQL, others for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
# We use --no-cache-dir to keep the image size small
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-downloading model weights (REMOVED) ──────────────────────────────────
# We REMOVED the SentenceTransformer download here because we are now using 
# Cloud APIs. This saves ~450MB of disk and prevents RAM spikes during build.

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Non-root user ─────────────────────────────────────────────────────────────
# Professional security: run as a limited user
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app \
    && chmod +x start.sh

USER appuser

# ── Network ───────────────────────────────────────────────────────────────────
# Render uses the $PORT env var, but we expose 8000 for the internal backend
EXPOSE 8000
EXPOSE 10000

# ── Entrypoint ────────────────────────────────────────────────────────────────
# We use the start.sh script to handle database seeding and starting both
# the FastAPI backend and the Streamlit frontend.
CMD ["sh", "start.sh"]