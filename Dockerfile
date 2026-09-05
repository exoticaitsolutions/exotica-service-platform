# Multi-stage Dockerfile for the Exotica Platform
# Single image supports multiple process types (web, worker, scheduler) via ENV PROCESS_TYPE

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /tmp

# Install uv
RUN pip install uv

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Create and populate venv with uv
RUN uv venv /opt/venv --python python3.11 && \
    uv pip install --python /opt/venv/bin/python -e .

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy venv from builder
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

# Set up environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default to web process (can be overridden with docker run -e PROCESS_TYPE=worker)
ENV PROCESS_TYPE=web

# Start command (will be overridden per process type)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
