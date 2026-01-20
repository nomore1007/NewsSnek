#!/bin/bash

# Entrypoint script for NewsSnek container
# Config files are created during Docker build, this script handles user overrides

echo "=== NewsSnek Entrypoint v$(cat /app/VERSION 2>/dev/null | grep VERSION | cut -d'=' -f2 || echo 'unknown') ==="
echo "Setting up configuration files..."

# First, ensure config files exist in /app (always writable by app user)
if [ ! -f "/app/settings.json" ]; then
    cat > "/app/settings.json" << 'EOF'
{
  "summarizer": {
    "provider": "ollama",
    "config": {
      "host": "localhost",
      "model": "smollm2:135m",
      "timeout": 120,
      "preferred_language": "en"
    }
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
  "output": [
    {
      "type": "console",
      "config": {
        "output_file": null
      }
    },
    {
      "type": "telegram",
      "config": {
        "bot_token": "your-telegram-bot-token",
        "chat_id": "your-chat-id"
      }
    },
    {
      "type": "discord",
      "config": {
        "webhook_url": "https://discord.com/api/webhooks/...",
        "username": "News Reader",
        "avatar_url": "https://example.com/avatar.png"
      }
    }
  ],
  "interval": 60
}
EOF
    echo "✅ Created default settings.json"
fi

if [ ! -f "/app/sources.txt" ]; then
    cat > "/app/sources.txt" << 'EOF'
# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
https://feeds.npr.org/1001/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml

# YouTube RSS feeds
https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw
https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA

# Websites for scraping (automatically detected)
# https://example.com/news
EOF
    echo "✅ Created default sources.txt"
fi

# Try to create persistent copies in data directory if writable
echo "Attempting to create persistent config files..."
mkdir -p /app/data 2>/dev/null || echo "⚠️  Cannot create data directory"

if [ -w "/app/data" ] 2>/dev/null; then
    cp "/app/settings.json" "/app/data/settings.json" 2>/dev/null && echo "✅ Created persistent settings.json" || echo "⚠️  Could not create persistent settings.json"
    cp "/app/sources.txt" "/app/data/sources.txt" 2>/dev/null && echo "✅ Created persistent sources.txt" || echo "⚠️  Could not create persistent sources.txt"
else
    echo "⚠️  Data directory not writable - config files will not persist between container restarts"
fi

# Verify files exist and show version info
echo "=== Configuration Complete ==="
echo "Runtime config files in /app:"
ls -la /app/ | grep -E "(settings|sources)" || echo "Config files not found in app directory"

echo "Checking persistence status..."
if [ -d "/app/data" ] && [ -w "/app/data" ]; then
    echo "Persistent config files in /app/data:"
    ls -la /app/data/ | grep -E "(settings|sources)" || echo "No persistent config files found"
    echo "✅ Config files will persist between container restarts"
else
    echo "⚠️  Config files will NOT persist - check volume mount permissions"
fi

echo "🎯 NewsSnek is ready to run!"
exec "$@"