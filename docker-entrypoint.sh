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

# Copy example files to the HOST directory (which is mounted to /opt/config)
# This ensures files are created on the host and visible to the container
echo "Creating configuration files..."

if [ -f "/app/settings.example.json" ]; then
    cp "/app/settings.example.json" "/opt/newssnek/settings.json"
    if [ -f "/opt/newssnek/settings.json" ]; then
        echo "✅ Successfully created settings.json on host (/opt/newssnek/)"
    else
        echo "❌ Failed to create settings.json - file not found after copy"
    fi
else
    echo "❌ ERROR: settings.example.json not found in /app/"
fi

if [ -f "/app/sources.example.txt" ]; then
    cp "/app/sources.example.txt" "/opt/newssnek/sources.txt"
    if [ -f "/opt/newssnek/sources.txt" ]; then
        echo "✅ Successfully created sources.txt on host (/opt/newssnek/)"
    else
        echo "❌ Failed to create sources.txt - file not found after copy"
    fi
else
    echo "❌ ERROR: sources.example.txt not found in /app/"
fi

# Verify files exist in both locations
echo "Files in /opt/newssnek (host):"
ls -la /opt/newssnek/ || echo "Cannot list /opt/newssnek"

echo "Files in /opt/config (container mount):"
ls -la /opt/config/ || echo "Cannot list /opt/config"

echo "Entrypoint: Configuration files ready"

# Execute the main command
exec "$@"