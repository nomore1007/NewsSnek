#!/bin/bash

echo "=== NewsSnek Entrypoint v$(cat /app/VERSION | grep VERSION | cut -d'=' -f2) ==="
echo "Simple test: Creating config files unconditionally..."

echo "Creating settings.json..."
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

echo "Creating sources.txt..."
cat > "/app/sources.txt" << 'EOF'
# Add your RSS feeds and websites here
# RSS feeds (automatically detected)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
EOF

echo "Files created:"
ls -la /app/settings.json /app/sources.txt 2>/dev/null || echo "Files not found"

echo "Entrypoint complete"