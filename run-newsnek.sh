#!/bin/sh
cd /app/src
while true; do
  echo "=== Starting NewsSnek $(date) ==="
  # Use settings.json and sources.json from mounted /app/data via symlinks
  python3 newsnek.py
  echo "=== Completed at $(date) ==="
  echo "Sleeping 60 minutes..."
  sleep 3600
done
