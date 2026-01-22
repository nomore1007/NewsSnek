#!/bin/sh
set -e

WORK_DIR="/app/data"

echo "=== NewsSnek Entrypoint ==="

mkdir -p "$WORK_DIR"

# Create example files
cat > "$WORK_DIR/settings.example.json" << 'EOF'
{
  "summarizer": {
    "provider": "ollama",
    "config": {
      "host": "http://localhost:11434",
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
    "database": "news_reader.db"
  },
  "output": {
    "groups": {}
  },
  "interval": 60
}
EOF

cat > "$WORK_DIR/sources.example.txt" << 'EOF'
# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
https://feeds.npr.org/1001/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml

# YouTube RSS feeds
https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw
https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA

# Websites for scraping (all channels)
# https://example.com/news
EOF

# Determine sources file
if [ -f "$WORK_DIR/sources.txt" ]; then
    SOURCES_FILE="sources.txt"
elif [ -f "$WORK_DIR/sources.json" ]; then
    SOURCES_FILE="sources.json"
else
    SOURCES_FILE="sources.txt"
fi

echo "Sources file: $SOURCES_FILE"

# Check if settings.json exists
if [ -f "$WORK_DIR/settings.json" ]; then
    echo "Using mounted settings.json from $WORK_DIR"
    ln -sf "$WORK_DIR/settings.json" /app/settings.json
else
    echo "Creating default settings.json"
    cp "$WORK_DIR/settings.example.json" /app/settings.json
fi

# Handle sources file
rm -f /app/sources.txt /app/sources.json

if [ -f "$WORK_DIR/$SOURCES_FILE" ]; then
    echo "Using mounted $SOURCES_FILE from $WORK_DIR"
    ln -sf "$WORK_DIR/$SOURCES_FILE" /app/$SOURCES_FILE
else
    echo "Creating default $SOURCES_FILE"
    cp "$WORK_DIR/sources.example.txt" /app/$SOURCES_FILE
fi

echo "Configuration ready - NewsSnek is starting..."

exec "$@"