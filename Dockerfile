# HermesClaw: A security-first open-source local AI agent framework

FROM python:3.12-slim AS base

# Security: run as non-root
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Create workspace and log directories with correct ownership
RUN mkdir -p /app/workspace /app/data /app/logs && \
    chown -R appuser:appuser /app

USER appuser

# Offline-first defaults
ENV NETWORK_ENABLED=false \
    DRY_RUN=true \
    AUTO_APPROVE=false \
    WORKSPACE_ROOT=/app/workspace \
    API_HOST=127.0.0.1 \
    API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["python", "-m", "hermes_openclaw", "--serve"]
