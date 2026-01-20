# News Reader

A sophisticated Python-based RSS feed reader and web scraper that summarizes articles using various AI models. Features multilingual support, multiple output channels (Telegram, Discord), and continuous monitoring capabilities.

## Features

- **Multi-Source Processing**: RSS feeds and direct website scraping
- **AI-Powered Summarization**: Support for Ollama and other AI providers
- **Multilingual Support**: Automatic language detection and translation
- **Multiple Output Channels**: Console, Telegram, Discord
- **YouTube Integration**: Video transcript processing
- **Continuous Monitoring**: Run in intervals for real-time news tracking
- **Database Storage**: SQLite with migration support
- **Home Assistant Integration**: Generate daily briefings

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
   The application will automatically create `sources.txt` from `sources.example.txt` on first run. Edit the created `sources.txt` with your RSS feeds and websites.

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
- **Discord**: Post embeds to Discord webhooks

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