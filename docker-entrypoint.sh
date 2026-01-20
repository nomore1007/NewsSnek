#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Ensure config directory exists and has basic files
echo "Entrypoint: Setting up configuration files..."

# Create config directory if it doesn't exist
mkdir -p /opt/config

# List current files for debugging
echo "Contents of /opt/config:"
ls -la /opt/config/

echo "Contents of /app:"
ls -la /app/ | grep -E "(settings|sources)"

# Copy example files if they don't exist in the mounted volume
if [ ! -f "/opt/config/settings.json" ]; then
    if [ -f "/app/settings.example.json" ]; then
        cp "/app/settings.example.json" "/opt/config/settings.json"
        echo "Created settings.json from example"
    else
        echo "ERROR: settings.example.json not found in /app/"
    fi
fi

if [ ! -f "/opt/config/sources.txt" ]; then
    if [ -f "/app/sources.example.txt" ]; then
        cp "/app/sources.example.txt" "/opt/config/sources.txt"
        echo "Created sources.txt from example"
    else
        echo "ERROR: sources.example.txt not found in /app/"
    fi
fi

# List final files
echo "Final contents of /opt/config:"
ls -la /opt/config/

echo "Entrypoint: Configuration files ready"

# Execute the main command
exec "$@"