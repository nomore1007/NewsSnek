# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Create data directory for persistent storage
RUN mkdir -p /app/data

# Note: Config files are created by entrypoint script to work with volume mounts

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Use entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command - can be overridden by Portainer
CMD ["python3", "nwsreader.py", "--file", "sources.txt", "--overview", "--interval", "60"]