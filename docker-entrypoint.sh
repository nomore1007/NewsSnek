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
    if [ -f "/app/settings.json" ]; then
        echo "✅ Successfully created settings.json in /app/"
    else
        echo "❌ Failed to create settings.json - file not found after copy"
    fi
else
    echo "❌ ERROR: settings.example.json not found in /app/"
fi

if [ -f "/app/sources.example.txt" ]; then
    cp "/app/sources.example.txt" "/app/sources.txt"
    if [ -f "/app/sources.txt" ]; then
        echo "✅ Successfully created sources.txt in /app/"
    else
        echo "❌ Failed to create sources.txt - file not found after copy"
    fi
else
    echo "❌ ERROR: sources.example.txt not found in /app/"
fi

# Verify files exist
echo "Files in /app:"
ls -la /app/ | grep -E "(settings|sources)" || echo "Config files not found in /app"

echo "Entrypoint: Configuration files ready"

# Execute the main command
exec "$@"