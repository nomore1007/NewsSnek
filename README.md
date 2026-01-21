# News Reader

A sophisticated Python-based RSS feed reader and web scraper that summarizes articles using various AI models. Features multilingual support, multiple output channels (Telegram, Discord), and continuous monitoring capabilities.

## Features

- **Multi-Source Processing**: RSS feeds and direct website scraping
- **AI-Powered Summarization**: Support for Ollama and other AI providers
- **Multilingual Support**: Automatic language detection and translation
- **Multiple Output Channels**: Console, Telegram, Discord (webhooks + bot tokens)
- **Structured Source Groups**: JSON-based source organization with channel routing
- **YouTube Integration**: Video transcript processing
- **Continuous Monitoring**: Run in intervals for real-time news tracking
- **Database Storage**: SQLite with migration support
- **Home Assistant Integration**: Generate daily briefings
- **Clear Error Messages**: Helpful error reporting when Ollama server is unavailable

## Recent Changes

### v2.x - Enhanced Channel Routing & JSON Sources

- **JSON Sources Format**: New structured JSON format for organizing news sources with groups, channel routing, and custom prompts
- **Discord Bot Token Support**: Added support for Discord bot tokens alongside existing webhook authentication
- **Source Group Routing**: Route specific source groups to specific output channels
- **Migration Tools**: Automated migration from legacy `sources.txt` to `sources.json` format
- **Inline Sources**: Support for defining sources directly within `settings.json`

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd news-reader
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure settings**
   The application will automatically create `settings.json` from `settings.example.json` on first run. Edit the created `settings.json` with your configuration.

4. **Add news sources**
    The application supports both JSON and text formats for sources. It will automatically create `sources.json` with the new structured format on first run. Edit the created `sources.json` with your RSS feeds and websites.

    **Migrating from sources.txt to sources.json:**
    ```bash
    python3 migrate_sources.py
    ```

5. **Run the news reader**
   ```bash
   python3 nwsreader.py --file sources.txt --overview
   ```

## Configuration

### Settings Structure

```json
{
  "summarizer": {
    "provider": "ollama",
    "config": {
      "host": "localhost",
      "model": "smollm2:135m",
      "timeout": 120,
      "preferred_language": "en"
    }
  },
  "output": [
    {
      "type": "telegram",
      "config": {
        "bot_token": "your-bot-token",
        "chat_id": "your-chat-id"
      }
    }
  ]
}
```

### Output Channels

- **Console**: Print to terminal or file
- **Telegram**: Send summaries to Telegram chats
- **Discord**: Post embeds to Discord webhooks or via bot tokens

#### Discord Setup

Discord supports two authentication methods:

**Webhook Method** (simpler, recommended for basic usage):
1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook and copy the URL
4. Configure in `settings.json`:
```json
{
  "type": "discord",
  "config": {
    "webhook_url": "https://discord.com/api/webhooks/...",
    "username": "News Reader",
    "avatar_url": "https://example.com/avatar.png"
  }
}
```

**Bot Token Method** (more powerful, allows reading messages):
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token from the "Bot" section
4. Invite the bot to your server with appropriate permissions
5. Get the channel ID (enable Developer Mode in Discord, right-click channel → Copy ID)
6. Configure in `settings.json`:
```json
{
  "type": "discord",
  "config": {
    "bot_token": "your-discord-bot-token",
    "channel_id": "your-channel-id",
    "username": "News Reader"
  }
}
```

### Source Groups and Channel Routing

You can organize your news sources into groups that send to different output channels:

#### Grouped Sources Format

```txt
# News Sources Configuration
# Format: [group-name] or [group-name:channel1,channel2] or [group-name:channel1,channel2:custom prompt]

[telegram-news]
# General news sources for Telegram (default prompt)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss

[discord-tech:discord]
# Technology news for Discord only
https://feeds.feedburner.com/TechCrunch/
https://www.reddit.com/r/technology/.rss

[tech-analysis:telegram:Summarize this technical article focusing on key innovations and implications for developers]
# Tech analysis with custom prompt for Telegram
https://example.com/tech-analysis/rss.xml

[all-channels]
# Sources that go to all configured channels (default prompt)
https://example.com/rss.xml
```

#### Named Output Channels

Update your `settings.json` to use named channels:

```json
{
  "output": {
    "channels": {
      "telegram": {
        "type": "telegram",
        "config": {
          "bot_token": "your-bot-token",
          "chat_id": "your-chat-id"
        }
      },
      "discord": {
        "type": "discord",
        "config": {
          "webhook_url": "https://discord.com/api/webhooks/...",
          "username": "Tech Bot"
        }
      }
    }
  }
}
```

#### Group-Channel Mapping

- `[group-name]` - Sends to all configured channels (default prompt)
- `[group-name:channel1,channel2]` - Sends only to specified channels (default prompt)
- `[group-name:channel1,channel2:custom prompt]` - Sends to specified channels with custom prompt
- `[group-name::custom prompt]` - Sends to all channels with custom prompt

## Sources Configuration (JSON Format)

The application now supports a structured JSON format for sources configuration, which provides better organization and validation.

### JSON Sources Structure

```json
{
  "groups": {
    "general-news": {
      "description": "General news sources for all channels",
      "channels": [],
      "prompt": null,
      "sources": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.cnn.com/rss/edition.rss"
      ]
    },
    "tech-news": {
      "description": "Technology news for Discord",
      "channels": ["discord"],
      "prompt": "Summarize this technical article focusing on key innovations and implications for developers",
      "sources": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.reddit.com/r/technology/.rss"
      ]
    },
    "all-channels": {
      "description": "Sources that go to all configured channels",
      "channels": [],
      "prompt": null,
      "sources": [
        "https://example.com/rss.xml"
      ]
    }
  }
}
```

### Field Descriptions

- **`description`**: Human-readable description of the group
- **`channels`**: Array of channel names to send summaries to (empty array = all channels)
- **`prompt`**: Custom summarization prompt for this group (null = use default)
- **`sources`**: Array of RSS feed URLs or website URLs

### Inline Sources in Settings

You can also define sources directly in your `settings.json`:

```json
{
  "sources": {
    "groups": {
      "my-news": {
        "description": "My personal news sources",
        "channels": ["telegram"],
        "sources": ["https://example.com/feed.xml"]
      }
    }
  }
}
```

### Migration from Text Format

To migrate from the old `sources.txt` format to the new JSON format:

```bash
python3 migrate_sources.py
```

This will convert your existing text-based groups to the structured JSON format.

#### Custom Prompts

Each group can have its own summarization prompt to tailor the AI's behavior:

- **Tech articles**: Focus on technical details, innovations, and developer implications
- **Business news**: Emphasize financial impact, market analysis, and business strategy
- **General news**: Standard balanced summaries

Prompts override the default `article_summary` prompt from `settings.json`.

#### Backward Compatibility

The old flat format still works - all sources go to all channels:

```txt
# Traditional format (goes to all channels)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
```

## Deployment

### Docker Deployment (Portainer)

1. **Prepare the host directory**
   ```bash
   # Create the data directory on your host
   sudo mkdir -p /opt/newsnek
   sudo chown -R 1000:1000 /opt/newsnek
   ```

   **Important**: The directory must be owned by UID 1000 (the app user in the container) or have 777 permissions for the container to write to it.

2. **Build the Docker image**
   ```bash
   docker build -t news-reader .
   ```

3. **Run with Docker**
   ```bash
   docker run -v /opt/newsnek:/app/data news-reader
   ```

4. **Portainer Stack**
   ```yaml
   services:
     news-reader:
       image: news-reader:latest
       volumes:
         - /opt/newsnek:/app/data
       environment:
         - INTERVAL=60  # Optional: override settings.json interval
       restart: unless-stopped
   ```

   **Note**: This deployment does not include an Ollama server. You must have Ollama running separately and configured in your `settings.json` file.

   **Configuration**: The container will create default configuration files in the mounted volume (`/opt/newsnek` on host) on first run. To customize, edit these files directly on the host:
   - `/opt/newsnek/settings.json` - Main configuration
   - `/opt/newsnek/sources.txt` - News sources

   **Interval Setting**: Configure the run interval in `/opt/newsnek/settings.json`:
   ```json
   {
     "interval": 60
   }
   ```
   Or override with environment variable `INTERVAL=30`.

#### Troubleshooting Docker Deployment

**Issue: Permission denied errors**
```
/app/docker-entrypoint.sh: line 14: /app/data/settings.json: Permission denied
```

**Solution**: Fix the host directory permissions
```bash
# Option 1: Change ownership to UID 1000
sudo chown -R 1000:1000 /opt/newsnek

# Option 2: Make directory writable by all users
sudo chmod 777 /opt/newsnek
```

**Issue: Config files reset to defaults after restart**
```
Config files not found in data directory
```

**Solution**: Ensure the volume is correctly mounted
```bash
# Check if volume is mounted
docker exec news-reader ls -la /app/data

# Edit config files on the host, not in the container
nano /opt/newsnek/settings.json
nano /opt/newsnek/sources.txt
```

**Issue: Container won't start**
- Check logs: `docker logs news-reader`
- Verify Ollama server is accessible from the container
- Ensure the host directory exists and has correct permissions

### Continuous Monitoring

Run with interval for continuous news monitoring:

```bash
# Run every 30 minutes
python3 nwsreader.py --file sources.txt --interval 30

# Run once and generate overview
python3 nwsreader.py --file sources.txt --overview
```

## Requirements

- Python 3.8+
- Ollama server (user-provided, for AI summarization)
- Optional: langdetect, googletrans for translation

## Documentation

See [AGENTS.md](AGENTS.md) for comprehensive documentation including:
- Architecture details
- Extension guides
- Configuration options
- Development guidelines

## License

[Your License Here]