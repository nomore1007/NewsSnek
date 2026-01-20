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

# Copy application code (excluding files we don't need in container)
COPY *.py /app/
COPY *.txt /app/
COPY *.json /app/
COPY docker-entrypoint.sh /app/

# Verify entrypoint script is present and executable
RUN echo "=== Verifying docker-entrypoint.sh ===" && \
    ls -la /app/docker-entrypoint.sh && \
    test -x /app/docker-entrypoint.sh && \
    echo "✅ Entrypoint script is executable" || (echo "❌ Making executable" && chmod +x /app/docker-entrypoint.sh)

# Debug: Show key files
RUN echo "=== Key files in /app ===" && ls -la /app/*.py /app/*.sh /app/*.json /app/*.txt 2>/dev/null || echo "Some files missing"

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