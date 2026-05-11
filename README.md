# NewsSnek (News Reader & Summarizer)

A lightweight Python application that pulls RSS feeds and webpages, extracts the main content, summarizes it with an LLM, and outputs the summary to console or chat platforms. Designed for quick deployment with Docker.

## Features
- **JSON‑based source groups** with customizable prompts
- **Multi‑channel output** (console, Discord, Telegram, etc.)
- **Container‑friendly**: runs inside a minimal Python image, persisting data to a mounted volume
- **Hot‑reload** of configuration via `settings.json` or `sources.json`
- **Extensible**: add new providers or output channels via plug‑in interface

## Project Layout
```
├── Dockerfile
├── docker-entrypoint.sh   # Sets up data dir and symlinks settings/files
├── newsnek.py
├── migrate_sources.py
├── settings.json          # Runtime config (create from settings.example.json)
├── sources.json           # JSON source definition (create from sources.example.json)
├── requirements.txt
└── …
```

## Prerequisites
- Docker 18.09+ or Podman
- An Ollama server running (or any other provider you wish to configure)

## Docker Setup
```bash
# 1. Pull or build the image
# Build locally
docker build -t news-snek .

# 2. Create a data directory on the host and give ownership to UID 1000
sudo mkdir -p /opt/news-snek
sudo chown -R 1000:1000 /opt/news-snek

# 3. Run the container
# Mount the data directory so settings, sources, and DB persist between restarts
# The first run will create default `settings.json` and `sources.json`
# Edit these files on the host to customize your feeds and channels

docker run \
  --name news-snek \
  -v /opt/news-snek:/app/data \
  -p 8080:8080 \
  news-snek
```

### Docker Compose
You can also use the included `docker-compose.yml`:
```yaml
version: "3"
services:
  news-snek:
    build: .
    volumes:
      - /opt/news-snek:/app/data
    restart: unless-stopped
```

## Configuration
See the web‑style docs in the repository or run:
```bash
python3 newsnek.py --help
```

### Settings (`settings.json`)
- `ollama`, `openrouter`, etc. providers
- `files.s` for source and DB paths
- `output.channels` mapping
- `interval` in seconds

### Sources (`sources.json`)
Define groups with `description`, `channels`, `prompt`, and a list of URLs.

## Usage
```bash
# One‑shot summary of current feeds
python3 newsnek.py --once

# Continuous monitoring
python3 newsnek.py
```

## Testing
```bash
# Run unit tests (if any)
pytest
```

## Contributing
Pull requests are welcome. Please run documentation checks and tests before submitting.

## License
MIT
