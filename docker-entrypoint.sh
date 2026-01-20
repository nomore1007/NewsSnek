#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Ensure config directory exists and has basic files
echo "Entrypoint: Setting up configuration files..."

# Create host directory if it doesn't exist (for volume mount)
mkdir -p /opt/newssnek

# Create config directory if it doesn't exist
mkdir -p /opt/config

# List current files for debugging
echo "Contents of /opt/config:"
ls -la /opt/config/ || echo "Cannot list /opt/config"

echo "Contents of /app (example files):"
ls -la /app/ | grep -E "(settings|sources)" || echo "No example files found in /app"

# Always copy/overwrite example files to ensure they exist
if [ -f "/app/settings.example.json" ]; then
    cp "/app/settings.example.json" "/opt/config/settings.json"
    echo "✅ Created/updated settings.json from example"
else
    echo "❌ ERROR: settings.example.json not found in /app/"
fi

if [ -f "/app/sources.example.txt" ]; then
    cp "/app/sources.example.txt" "/opt/config/sources.txt"
    echo "✅ Created/updated sources.txt from example"
else
    echo "❌ ERROR: sources.example.txt not found in /app/"
fi

# List final files
echo "Final contents of /opt/config:"
ls -la /opt/config/ || echo "Cannot list /opt/config"

echo "Final contents of /opt/newssnek (host mount):"
ls -la /opt/newssnek/ || echo "Cannot list /opt/newssnek"

echo "Entrypoint: Configuration files ready"

# Execute the main command
exec "$@"