FROM python:3.11-slim

LABEL maintainer="FCAP Engineering <fcap-eng@example.com>"
LABEL description="Financial Crime Analytics Platform — AML Python Service"
LABEL version="1.0.0"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies required for some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached unless requirements change)
COPY python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy AML library source
COPY python/ ./python/

# Create a non-root user for security hardening
RUN addgroup --system fcap && adduser --system --ingroup fcap fcap
USER fcap

# Expose the service port
EXPOSE 8000

# Health-check via the Python HTTP module (no extra dependencies needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# Default entry point — runs the AML pipeline as a module.
# Override CMD in docker-compose or Kubernetes to run alternative entry points.
CMD ["python", "-m", "python.aml.pipeline"]
