# =============================================================================
# Async Research Assistant — Multi-stage Dockerfile
# Multi-stage build: smaller final image, no build tools at runtime.
# =============================================================================

# ---- Build stage ----
FROM python:3.12-slim AS builder
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim
LABEL org.opencontainers.image.description="AIENG Final Project — Async Research Assistant"
LABEL org.opencontainers.image.source="https://github.com/abdurahmanligulnisa/research-assistant.git"

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user before copying files
RUN useradd --create-home --shell /bin/bash appuser

COPY --chown=appuser:appuser . .

USER appuser

# Default: run the offline demo (no API keys required)
# Override: docker run --env-file .env researcher python -m researcher ask "..."
CMD ["python", "demo_ai.py", "--offline"]
