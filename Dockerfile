FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlink so robaivenv python symlinks work
RUN ln -s /usr/local/bin/python3 /usr/bin/python3

# Copy application code
COPY robairagapi/api/ ./api/
COPY robairagapi/config.py robairagapi/main.py ./

# Create non-root user for security
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app

# Switch to non-root user
USER apiuser

# Set environment variables
# venv will be mounted at /venv, prepend to PATH
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH="/app:/robaitools"

# Run API server
CMD python3 main.py
