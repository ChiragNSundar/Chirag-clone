# Chirag Clone v2.3 - Production Dockerfile
# Multi-stage build for FastAPI backend and React frontend
# Includes Voice (ElevenLabs/Whisper), Vision, Brain Station, and Real-Time WebSocket features

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend-react/package*.json ./
RUN npm ci
COPY frontend-react/ ./
RUN npm run build

# Stage 2: Build Python wheels
FROM python:3.11-slim AS python-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# Stage 3: Production
FROM python:3.11-slim
LABEL maintainer="Chirag"
LABEL description="Chirag Clone - Personal AI Digital Twin v2.3"
LABEL version="2.3"

# Security: Create non-root user
RUN groupadd -r chirag && useradd -r -g chirag chirag

WORKDIR /app

# Install runtime dependencies (audio, PDF, and network tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    ffmpeg \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage and install
COPY --from=python-builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY backend/ ./backend/

# Copy frontend build from frontend-builder
COPY --from=frontend-builder /app/frontend/dist ./frontend/

# Create data directories
RUN mkdir -p /app/backend/data/chroma_db \
    && mkdir -p /app/backend/data/uploads \
    && mkdir -p /app/backend/data/audio_cache \
    && mkdir -p /app/backend/data/knowledge \
    && chown -R chirag:chirag /app

# Switch to non-root user
USER chirag

# Environment variables
ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose FastAPI port (HTTP + WebSocket)
EXPOSE 8000

# Health check for FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run with uvicorn (WebSocket support enabled by default)
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "websockets"]
