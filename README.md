# News Snek – Newspaper‑Style RSS & YouTube Summariser  
*A lightweight, Python‑based RSS/YouTube reader that pulls summaries and distributes them via Discord/Telegram (or stdout) using OpenAI‑style LLMs.*

---

## Table of Contents  
1. [What it does](#what-it-does)  
2. [Requirements](#requirements)  
3. [Installation](#installation)  
4. [Configuration](#configuration)  
5. [Running the app](#running-the-app)  
6. [Channels](#channels)  
7. [Development](#development)  
8. [Troubleshooting](#troubleshooting)

---

## What it does

- **Pulls** RSS feeds, regular web pages, and YouTube videos.  
- **Summarises** article text using an LLM chain (OpenRouter, Ollama, etc.).  
- **Aggregates** daily “world‑state” overviews from all processed summaries.  
- **Distributes** summaries to Discord, Telegram, or a local file/console.  
- **Bypasses Blocks**: Supports `cookies.txt` injection for YouTube transcript extraction to avoid "Cloud IP" blocks.

---

## Requirements

| Item | Version | Why |
| --- | --- | --- |
| Docker | **≥ 2.0** | Containerised runtime – no host‑side Python setup needed. |
| One LLM provider | Any supported provider | Provides the summarisation engine (e.g., OpenRouter, Ollama). |
| (Optional) Bot tokens | Telegram/Discord | Required for automated messaging delivery. |

---

## Installation

### Docker Compose (Recommended)

The repo ships with a `docker-compose.yml` that performs a clean build, mounts a persistent volume for your database/settings, and runs in the background.

```bash
git clone https://github.com/your-org/newsnek.git
cd newsnek

# Build and start the container
docker compose up -d
```

### Plain Docker

If you prefer not to use Compose, you can run the image directly:

```bash
docker build -t newsnek:latest .
docker run -d \
    --name newsnek \
    -v /opt/newsnek:/app/data \
    newsnek:latest
```

*Note: The volume `/opt/newsnek` (or your chosen path) is critical. It stores your `settings.json`, `sources.json`, SQLite database, and your `cookies.txt` for YouTube.*

---

## Configuration

All behavior is controlled via **`settings.json`**, which resides in your data volume. 

### Key Sections

1. **`providers`**: Defines the AI models available to the engine (e.g., OpenRouter, Ollama).
2. **`prompts`**: Customises the "personality" of your summaries.
3. **`output.channels`**: Defines the destinations (Telegram, Discord, Console).
4. **`overview`**: Controls the daily consolidated digest (time, target channels, and item count).

### Example `settings.json`

```json
{
  "providers": {
    "openrouter-free": { "type": "openrouter", "model": "openrouter/free" },
    "local-ollama": { "type": "ollama", "host": "http://10.0.10.44:11434", "model": "qwen3.5:4b" }
  },

  "prompts": {
    "article_summary": "Summarise this article in a neutral, concise tone:",
    "overview_summary": "Provide a comprehensive daily overview of the following news summaries."
  },

  "output": {
    "channels": {
      "DailyNews": {
        "type": "telegram",
        "config": {
          "bot_token": "123456:ABC-DEF",
          "chat_id": "@your_channel"
        }
      },
      "TechAlerts": {
        "type": "discord",
        "config": {
          "bot_token": "DISCORD_TOKEN",
          "channel_id": "9876543210"
        }
      }
    }
  },

  "overview": {
    "time": "07:30",
    "channels": [ "DailyNews", "TechAlerts" ],
    "max_items": 50
  },

  "interval": 30,
  "summarizer": {
    "providers": [ "openrouter-free" ],
    "overview_model": "openrouter-free",
    "preferred_language": "en"
  }
}
```

---

## Running the App

The engine is designed to run continuously in the background, but you can also trigger specific actions using `docker exec`.

| Mode | Command | Description |
|------|---------|-------------|
| **One‑off Run** | `docker exec newsnek-new python3 newsnek.py --once` | Processes all feeds once and generates an overview if the time matches. |
| **Trigger Overview** | `docker exec newsnek-new python3 newsnek.py --overview` | Forces an immediate daily overview generation. |
| **Debug Mode** | Add `--debug` to any command | Enables verbose logging to see exactly where an extraction is failing. |

*If you are running it locally (no Docker), simply use `python3 newsnek.py --once`.*

---

## Channels

You can define multiple output channels in `settings.json`. Each group of sources can be routed to different channels.

| Type | Config Fields | Best Use Case |
|------|---------------|-------------|
| `telegram` | `bot_token`, `chat_id` | Fast, mobile‑first alerts to a bot or public channel. |
| `discord` | `bot_token` **or** `webhook_url`, `channel_id` | Rich embeds for community or team feeds. |
| `console` | `output_file` (optional) | Writing to a local `.txt` file—perfect for debugging and local testing. |

**Pro Tip**: To stop a channel from receiving the daily overview, simply remove its name from the `overview.channels` array in `settings.json`.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| **`Provider not found`** | Typo in `settings.json` | Ensure the provider name in `summarizer.providers` matches a key in the `providers` block. |
| **YouTube "Empty Transcript"** | IP Block / No Captions | Drop a `cookies.txt` file into the data volume to authenticate as a real user. |
| **`ModuleNotFoundError`** | Broken package path | Ensure the `src` folder is at the same level as `newsnek.py` inside the container. |
| **JSON Parsing Error** | Syntax mistake | Check for trailing commas or missing quotes in `settings.json` or `sources.json`. |

---

## Development

If you want to contribute or modify the logic:
1. **Environment**: `pip install -r requirements.txt`
2. **Test**: Run `pytest tests/` to ensure no regressions.
3. **Build**: Use `docker build -t newsnek .` to create a new image.
