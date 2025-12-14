FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies + Docker CLI for system_health tool
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Create symlink so robaivenv python symlinks work (skip if already exists from docker.io)
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 || true

# Copy application code
COPY robairagapi/api/ ./api/
COPY robairagapi/config.py robairagapi/main.py ./

# Set environment variables
# venv will be mounted at /venv, prepend to PATH
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH="/app:/robaitools"

# Run API server
CMD python3 main.py
