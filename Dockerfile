# Chirag Clone v2.3.1 - Production Dockerfile
# Multi-stage build for FastAPI backend and React frontend
# Includes Voice, Vision, Brain Station, Real-Time WebSocket, and Performance Optimizations

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend-react/package*.json ./
RUN npm ci --silent
COPY frontend-react/ ./
RUN npm run build

# Stage 2: Build Python wheels
FROM python:3.11-slim AS python-builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# Stage 3: Production
FROM python:3.11-slim
LABEL maintainer="Chirag"
LABEL description="Chirag Clone - Personal AI Digital Twin v2.3.1"
LABEL version="2.3.1"

# Security: Create non-root user
RUN groupadd -r chirag && useradd -r -g chirag chirag

WORKDIR /app

# Install runtime dependencies (audio, PDF, network tools, and process monitoring)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    ffmpeg \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage and install
COPY --from=python-builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY backend/ ./backend/

# Copy frontend build from frontend-builder
COPY --from=frontend-builder /app/frontend/dist ./frontend/

# Create data directories with proper structure
RUN mkdir -p /app/backend/data/chroma_db \
    && mkdir -p /app/backend/data/uploads \
    && mkdir -p /app/backend/data/audio_cache \
    && mkdir -p /app/backend/data/knowledge \
    && mkdir -p /app/backend/logs \
    && chown -R chirag:chirag /app

# Switch to non-root user
USER chirag

# Environment variables for production
ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Performance tuning
ENV MALLOC_ARENA_MAX=2
ENV PYTHONHASHSEED=random

# Expose FastAPI port (HTTP + WebSocket)
EXPOSE 8000

# Enhanced health check using curl (more reliable in containers)
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run with uvicorn (optimized for production)
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "websockets", "--loop", "uvloop", "--http", "httptools"]
