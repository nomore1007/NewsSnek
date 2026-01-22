#!/bin/bash

# Entrypoint script for NewsSnek container
# Handles configuration file management and volume mount permissions

set -e

WORK_DIR="/app/data"

echo "=== NewsSnek Entrypoint ==="

# Ensure data directory exists and has correct permissions
mkdir -p "$WORK_DIR"

# Fix data directory permissions if needed (only show if there's an issue)
if [ -d "$WORK_DIR" ] && ! touch $WORK_DIR/.test_write 2>/dev/null; then
    echo "⚠️  Fixing $WORK_DIR permissions..."
    chown -R 1000:1000 $WORK_DIR
    chmod -R 755 $WORK_DIR
    rm -f $WORK_DIR/.test_write
fi

# Default settings.json content
DEFAULT_SETTINGS='{"summarizer":{"provider":"ollama","config":{"host":"http://localhost:11434","model":"smollm2:135m","timeout":120,"preferred_language":"en"}},"processing":{"max_overview_summaries":50,"scrape_timeout":30,"user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},"prompts":{"article_summary":"Summarize this article briefly:","overview_summary":"Based on the following news summaries, provide a comprehensive overview..."},"files":{"sources":"sources.txt","database":"news_reader.db"},"output":{"groups":{}},"interval":60}'

DEFAULT_SOURCES="# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
https://feeds.npr.org/1001/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml

# YouTube RSS feeds
https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw
https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA

# Websites for scraping (all channels)
# https://example.com/news"

# Default sources.txt content
DEFAULT_SOURCES=$(cat << 'EOF'
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
)

# Create example files in working directory
echo "$DEFAULT_SETTINGS" > "$WORK_DIR/settings.example.json"
echo "$DEFAULT_SOURCES" > "$WORK_DIR/sources.example.txt"

# Note: User must mount or create settings.json and sources.txt in $WORK_DIR

if [ ! -f "$WORK_DIR/sources.txt" ]; then
    echo "📝 Creating default sources.txt..."
    cp /app/sources.example.txt $WORK_DIR/sources.txt
    chown 1000:1000 $WORK_DIR/sources.txt
fi

# Use files directly from mounted data directory
if [ -f "$WORK_DIR/settings.json" ]; then
    echo "📁 Using mounted settings.json from $WORK_DIR"
    ln -sf $WORK_DIR/settings.json /app/settings.json
    
    # Debug: Show what the settings file contains for sources
    echo "🔍 Settings content for sources section:"
    grep -A 5 '"files"' $WORK_DIR/settings.json || echo "No files section found"
else
    echo "📝 Creating default settings.json..."
    echo "$DEFAULT_SETTINGS" > /app/settings.json
fi

# Read sources file setting from mounted settings and ensure only that file is used
SOURCES_FILE=$(grep -o '"sources":\s*"[^"]*"' $WORK_DIR/settings.json 2>/dev/null | cut -d'"' -f4)
if [ -z "$SOURCES_FILE" ]; then
    SOURCES_FILE="sources.txt"
fi

echo "🔧 Sources file specified in settings: $SOURCES_FILE"

# Remove ANY existing sources files to avoid conflicts
rm -f /app/sources.txt /app/sources.json

# Use ONLY the sources file specified in settings from mounted directory
if [ -f "$WORK_DIR/$SOURCES_FILE" ]; then
    echo "📁 Using mounted $SOURCES_FILE from $WORK_DIR"
    ln -sf "$WORK_DIR/$SOURCES_FILE" "/app/$SOURCES_FILE"
else
    echo "⚠️  $SOURCES_FILE not found in $WORK_DIR, creating default in /app..."
    if [ "$SOURCES_FILE" = "sources.json" ]; then
        echo "$DEFAULT_SETTINGS" | grep -A 50 '"sources"' | grep -B 50 '"interval"' > "/app/$SOURCES_FILE"
    else
        # Create default sources.txt
        cp /app/sources.example.txt "/app/$SOURCES_FILE"
    fi

echo "✅ Using ONLY sources file: /app/$SOURCES_FILE (from $WORK_DIR)"

echo "✅ Configuration ready - NewsSnek is starting..."

# Execute the main command
"$@"

# End of script