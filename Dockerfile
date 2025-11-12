# Multi-stage Dockerfile for production deployment
# Python 3.11.9 for maximum stability with scikit-learn and data science packages

# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.11.9-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements files
COPY requirements/ /tmp/requirements/

# Install Python dependencies
# Use base-linux.txt for production Linux environment
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements/base-linux.txt && \
    pip install -r /tmp/requirements/observability.txt && \
    pip install -r /tmp/requirements/encryption.txt && \
    pip install -r /tmp/requirements/ai_requirements.txt && \
    # Additional production dependencies
    pip install gunicorn==21.2.0 daphne==4.0.0

# ============================================
# Stage 2: Runtime - Minimal production image
# ============================================
FROM python:3.11.9-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.production

# Install runtime system dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgdal30 \
    libgeos-c1v5 \
    libproj25 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Create application directory structure
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R appuser:appuser /app

# Set work directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser . /app/

# Copy entrypoint scripts
COPY --chown=appuser:appuser docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=appuser:appuser docker/wait-for-postgres.sh /usr/local/bin/wait-for-postgres.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/wait-for-postgres.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "intelliwiz_config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--log-level", "info"]
