FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared libraries
COPY robaimodeltools/ ./robaimodeltools/
COPY robaidata/ ./robaidata/

# Copy requirements and install dependencies
COPY robairagapi/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r robaimodeltools/requirements.txt

# Copy application code
COPY robairagapi/api/ ./api/
COPY robairagapi/config.py robairagapi/main.py ./

# Create non-root user for security
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app

# Switch to non-root user
USER apiuser

# Run API server
CMD ["python3", "main.py"]
