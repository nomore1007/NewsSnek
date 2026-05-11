# NewsSnek

A lightweight, Docker-ready news aggregator and summarizer. It pulls RSS feeds and YouTube content, uses AI (Ollama or OpenRouter) to summarize them, and delivers the results to your preferred channels (Discord, Telegram, or Console).

## 🚀 Quick Start (Docker)

The easiest way to get running is using Docker.

### 1. Prepare your data directory
The application persists all settings, sources, and the SQLite database in a single directory on your host.
```bash
sudo mkdir -p /opt/newsnek
sudo chown -R $USER:$USER /opt/newsnek
```

### 2. Run with Docker
Build and run the container in one command:
```bash
docker build -t news-snek .
docker run -d \
  --name news-snek \
  -v /opt/newsnek:/app/data \
  news-snek
```

### 3. Configure
The first run will create default templates in `/opt/newsnek`. Edit these to set up your feeds and AI providers:
* `/opt/newsnek/settings.json` — AI credentials and output channels.
* `/opt/newsnek/sources.json` — Your news feeds and groups.

---

## 🛠 Project Structure

```
.
├── Dockerfile
├── README.md
├── requirements.txt
├── run-newsnek.sh       # Container entrypoint wrapper
├── src/                 # Main application logic
│   ├── app.py           # Entry point
│   ├── config.py        # Configuration management
│   ├── database.py      # SQLite integration
│   ├── extractor.py     # Content scraping
│   ├── output_channels.py
│   └── summarizers.py
└── .gitignore           # Protects credentials and local data
```

## ⚙️ Configuration Details

### AI Providers
Supported providers include:
* **OpenRouter**: Requires an `api_key` in `settings.json`.
* **Ollama**: Requires an `api_url` (e.g., `http://host.docker.internal:11434`).

### Data Persistence
All runtime data is stored in `/app/data` inside the container, which maps to `/opt/newsnek` on your host:
* `news_reader.db` — SQLite database.
* `settings.json` — Runtime configuration.
* `sources.json` — Feed definitions.

## 🧪 Local Development

If you want to run the application directly on your host (without Docker):

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the application**:
   ```bash
   python3 newsnek.py --debug
   ```
   *Note: Ensure your `settings.json` and `sources.json` are in the current directory or specify paths via command line arguments.*

## 🛡 Security & Best Practices
* **Never commit `settings.json` or `sources.json`** to version control. They contain API keys and personal channel IDs.
* Use the provided `settings.example.json` and `sources.example.json` as templates.
* Always use the `.gitignore` provided to prevent accidental exposure of sensitive data.

## 📜 License
MIT
