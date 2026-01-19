#!/bin/bash

# Entrypoint script for NewsSnek container
# Ensures configuration files exist before starting the application

# Configuration files are now created by the application itself
# when it first runs, using the example files as templates.
echo "Entrypoint: Configuration files will be created by the application on first run"

# Execute the main command
exec "$@"