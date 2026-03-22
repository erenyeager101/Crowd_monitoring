# syntax=docker/dockerfile:1
FROM python:3.11-slim

LABEL maintainer="Crowd Monitoring Team"
LABEL description="Modular Crowd Management & Monitoring Platform"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY crowd_engine/ ./crowd_engine/
COPY api_server.py ./
COPY cameras.json ./
COPY MobileNetSSD_deploy.prototxt ./

# Model file (large — mount via volume in production)
# COPY MobileNetSSD_deploy.caffemodel ./

# Non-root user for security
RUN useradd -m -u 1000 crowdapp && chown -R crowdapp:crowdapp /app
USER crowdapp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/livez')"

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
