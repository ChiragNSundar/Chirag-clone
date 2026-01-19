# ============================================================
# Chirag Clone v2.6 - Production Dockerfile
# Multi-stage build with security hardening and performance optimizations
# ============================================================

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Cache npm dependencies
COPY frontend-react/package*.json ./
RUN npm ci --silent

# Build frontend
COPY frontend-react/ ./
RUN npm run build

# Stage 2: Build Python wheels
FROM python:3.11-slim AS python-builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Build wheels for faster installation
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# Stage 3: Production
FROM python:3.11-slim

LABEL maintainer="Chirag"
LABEL description="Chirag Clone - Personal AI Digital Twin v2.7"
LABEL version="2.7.0"

# ============== Security Hardening ==============
# Create non-root user with specific UID/GID
RUN groupadd -r -g 1001 chirag && useradd -r -u 1001 -g chirag chirag

# Set secure permissions
RUN chmod 755 /usr

WORKDIR /app

# ============== Runtime Dependencies ==============
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    ffmpeg \
    libmupdf-dev \
    curl \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy and install Python wheels
COPY --from=python-builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# ============== Application Code ==============
# Copy backend
COPY --chown=chirag:chirag backend/ ./backend/

# Copy frontend build (matching main.py path expectation: parent/frontend-react/dist)
COPY --from=frontend-builder --chown=chirag:chirag /app/frontend/dist ./frontend-react/dist/

# ============== Data Directories ==============
RUN mkdir -p \
    /app/backend/data/chroma_db \
    /app/backend/data/uploads \
    /app/backend/data/audio_cache \
    /app/backend/data/knowledge \
    /app/backend/data/rewind \
    /app/backend/logs \
    /app/backend/migrations/versions \
    && chown -R chirag:chirag /app

# ============== Environment Variables ==============
ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Performance tuning
ENV MALLOC_ARENA_MAX=2
ENV PYTHONHASHSEED=random

# Default connections (override in docker-compose)
ENV REDIS_URL=redis://localhost:6379/0
ENV CHROMA_HOST=localhost
ENV CHROMA_PORT=8000
ENV LOG_LEVEL=INFO

# Security
ENV SECURE_HEADERS=true

# ============== Switch to Non-Root ==============
USER chirag

# Expose port
EXPOSE 8000

# ============== Health Check ==============
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# ============== Entrypoint ==============
WORKDIR /app/backend

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run uvicorn with production settings
CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "2", \
    "--ws", "websockets", \
    "--loop", "uvloop", \
    "--http", "httptools", \
    "--proxy-headers", \
    "--forwarded-allow-ips", "*"]

