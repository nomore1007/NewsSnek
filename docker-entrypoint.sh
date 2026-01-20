#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Ensure config directory exists and has basic files
echo "Entrypoint: Setting up configuration files..."

# Create host directory if it doesn't exist (for volume mount)
mkdir -p /opt/newssnek

# List current files for debugging
echo "Contents of /opt/newssnek (host mount):"
ls -la /opt/newssnek/ || echo "Cannot list /opt/newssnek"

echo "Contents of /app (example files):"
ls -la /app/ | grep -E "(settings|sources)" || echo "No example files found in /app"

# Copy example files to the normal container location (which is mounted to host)
# This ensures files are created in /app and visible on host through volume mount
echo "Creating configuration files..."

if [ -f "/app/settings.example.json" ]; then
    cp "/app/settings.example.json" "/app/settings.json"
    echo "✅ Created settings.json from example file"
elif [ -f "/app/settings.json" ]; then
    echo "✅ settings.json already exists"
else
    # Create default settings.json
    cat > "/app/settings.json" << 'EOF'
{
  "ollama": {
    "host": "localhost",
    "model": "smollm2:135m",
    "overview_model": "llama2",
    "timeout": 120
  },
  "processing": {
    "max_overview_summaries": 50,
    "scrape_timeout": 30,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  },
  "prompts": {
    "article_summary": "Summarize this article briefly:",
    "overview_summary": "Based on the following news summaries, provide a comprehensive overview..."
  },
  "files": {
    "sources": "sources.txt",
    "summaries": "summaries.json",
    "database": "news_reader.db"
  },
  "summarizer": {
    "provider": "ollama",
    "config": {
      "host": "localhost",
      "model": "smollm2:135m",
      "timeout": 120,
      "preferred_language": "en"
    }
  },
  "output": [
    {
      "type": "console",
      "config": {
        "output_file": null
      }
    }
  ],
  "interval": 60
}
EOF
    echo "✅ Created default settings.json"
fi

if [ -f "/app/sources.example.txt" ]; then
    cp "/app/sources.example.txt" "/app/sources.txt"
    echo "✅ Created sources.txt from example file"
elif [ -f "/app/sources.txt" ]; then
    echo "✅ sources.txt already exists"
else
    # Create default sources.txt
    cat > "/app/sources.txt" << 'EOF'
# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss

# Websites for scraping (automatically detected)
# https://example.com/news
EOF
    echo "✅ Created default sources.txt"
fi

# Verify files exist
echo "Files in /app:"
ls -la /app/ | grep -E "(settings|sources)" || echo "Config files not found in /app"

echo "Entrypoint: Configuration files ready"

# Execute the main command
exec "$@"