#!/bin/bash
# Test script to verify entrypoint functionality

echo "=== Testing Entrypoint Configuration ==="
echo "This script simulates the entrypoint logic"

# Create test data directory
mkdir -p /tmp/test-data

# Simulate entrypoint logic
echo "Checking for config files..."

if [ -f "/tmp/test-data/settings.json" ]; then
    echo "Found user settings.json"
elif [ ! -f "/tmp/test-settings.json" ]; then
    echo "Creating default settings.json..."
    cat > "/tmp/test-settings.json" << 'EOF'
{
  "test": "config"
}
EOF
    echo "Created test settings.json"
fi

if [ -f "/tmp/test-data/sources.txt" ]; then
    echo "Found user sources.txt"
elif [ ! -f "/tmp/test-sources.txt" ]; then
    echo "Creating default sources.txt..."
    echo "# Test sources" > "/tmp/test-sources.txt"
    echo "Created test sources.txt"
fi

echo "Files created:"
ls -la /tmp/test-*

echo "=== Test Complete ==="