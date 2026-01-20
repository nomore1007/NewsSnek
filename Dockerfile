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

# Create default config files from examples (before user switch)
RUN if [ -f "/app/settings.example.json" ]; then \
        cp "/app/settings.example.json" "/app/settings.json" && \
        echo "Created settings.json during build"; \
    fi
RUN if [ -f "/app/sources.example.txt" ]; then \
        cp "/app/sources.example.txt" "/app/sources.txt" && \
        echo "Created sources.txt during build"; \
    fi

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