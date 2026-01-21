#Version Control
ARG CACHE_BUST=3

# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# No additional system dependencies needed

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

# Config files will be created by entrypoint script in the data directory for persistence

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user and ensure proper permissions
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app && \
    chmod -R 755 /app

# Use entrypoint script (handles volume mount permissions)
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command - can be overridden by Portainer
CMD ["python3", "nwsreader.py", "--file", "sources.txt", "--overview", "--interval", "60"]
