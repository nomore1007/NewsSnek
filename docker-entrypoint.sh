#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Create settings.json from example if it doesn't exist
if [ ! -f "/app/settings.json" ]; then
    if [ -f "/app/settings.example.json" ]; then
        cp "/app/settings.example.json" "/app/settings.json"
        echo "Created settings.json from example file"
    else
        echo "Warning: No settings.example.json found, creating minimal settings.json"
        cat > "/app/settings.json" << EOF
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
    fi
fi

# Create sources.txt if it doesn't exist
if [ ! -f "/app/sources.txt" ]; then
    cat > "/app/sources.txt" << EOF
# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
# https://example.com/feed.xml

# Websites for scraping (automatically detected)
# https://example.com/news
EOF
    echo "Created default sources.txt file"
fi

# Execute the main command
exec "$@"