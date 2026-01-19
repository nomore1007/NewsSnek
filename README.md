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

## Deployment

### Docker Deployment (Portainer)

1. **Build the Docker image**
   ```bash
   docker build -t news-reader .
   ```

2. **Run with Docker**
   ```bash
   docker run -v $(pwd)/data:/app/data news-reader
   ```

3. **Portainer Stack**
   ```yaml
   services:
     news-reader:
       image: news-reader:latest
       volumes:
         - ./data:/app/data
       environment:
         - INTERVAL=60  # Optional: override settings.json interval
       restart: unless-stopped
   ```

   **Note**: This deployment does not include an Ollama server. You must have Ollama running separately and configured in your `settings.json` file.

   **Configuration**: After deployment, use Portainer's container file manager to edit `/app/settings.json` and `/app/sources.txt` inside the running container. The container will create default versions of these files on first run.

   **Interval Setting**: Configure the run interval in `/app/settings.json`:
   ```json
   {
     "interval": 60
   }
   ```
   Or override with environment variable `INTERVAL=30`.

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