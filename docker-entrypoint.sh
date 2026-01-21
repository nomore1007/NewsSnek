#!/bin/bash

# Entrypoint script for NewsSnek container
# Handles configuration file management and volume mount permissions

set -e

echo "=== NewsSnek Entrypoint v$(cat /app/VERSION 2>/dev/null | grep VERSION | cut -d'=' -f2 || echo 'unknown') ==="

# Ensure data directory exists and has correct permissions
mkdir -p /app/data

# Fix data directory permissions if needed (only show if there's an issue)
if [ -d "/app/data" ] && ! touch /app/data/.test_write 2>/dev/null; then
    echo "⚠️  Fixing /app/data permissions..."
    chown -R 1000:1000 /app/data
    chmod -R 755 /app/data
    rm -f /app/data/.test_write
fi

# Default settings.json content
DEFAULT_SETTINGS='{
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
     "sources": "sources.json",
     "database": "news_reader.db"
   },
   "sources": {
     "groups": {
       "general-news": {
         "description": "General news sources for all channels",
         "channels": [],
         "prompt": null,
         "sources": [
           "https://feeds.bbci.co.uk/news/rss.xml",
           "https://rss.cnn.com/rss/edition.rss"
         ]
       },
       "tech-news": {
         "description": "Technology news for Discord",
         "channels": ["discord"],
         "prompt": null,
         "sources": [
           "https://feeds.feedburner.com/TechCrunch/",
           "https://www.reddit.com/r/technology/.rss"
         ]
       }
     }
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
    },
    {
      "type": "discord",
      "config": {
        "bot_token": "your-discord-bot-token",
        "channel_id": "your-channel-id",
        "username": "News Reader"
      }
    }
  ],
  "interval": 60
}'

# Default sources.txt content
DEFAULT_SOURCES='# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
https://feeds.npr.org/1001/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml

# YouTube RSS feeds
https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw
https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA

# Websites for scraping (automatically detected)
# https://example.com/news'

# Create or use existing configuration files
if [ ! -f "/app/data/settings.json" ]; then
    echo "📝 Creating default settings.json..."
    echo "$DEFAULT_SETTINGS" > /app/data/settings.json
    chown 1000:1000 /app/data/settings.json
fi

if [ ! -f "/app/data/sources.txt" ]; then
    echo "📝 Creating default sources.txt..."
    echo "$DEFAULT_SOURCES" > /app/data/sources.txt
    chown 1000:1000 /app/data/sources.txt
fi

# Copy to runtime location
cp /app/data/settings.json /app/settings.json
cp /app/data/sources.txt /app/sources.txt
chown 1000:1000 /app/settings.json /app/sources.txt

echo "✅ Configuration ready - NewsSnek is starting..."

# Execute command (already running with appropriate permissions)
exec "$@"