#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Configuration files are now created by the application itself
# when it first runs, using the example files as templates.
echo "Entrypoint: Configuration files will be created by the application on first run"
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