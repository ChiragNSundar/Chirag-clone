# Chirag Clone - Production Dockerfile
# Multi-stage build for smaller final image

# Stage 1: Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt


# Stage 2: Production stage
FROM python:3.11-slim

# Labels
LABEL maintainer="Chirag"
LABEL description="Chirag Clone - Personal AI Digital Twin"
LABEL version="1.0"

# Security: Create non-root user
RUN groupadd -r chirag && useradd -r -g chirag chirag

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create data directories
RUN mkdir -p /app/backend/data/chroma_db \
    && mkdir -p /app/backend/data/uploads \
    && chown -R chirag:chirag /app

# Switch to non-root user
USER chirag

# Environment variables
ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Run with gunicorn
WORKDIR /app/backend
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
