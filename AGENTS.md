# AGENTS.md - Development Guidelines for News Reader Project

This document provides comprehensive guidelines for agentic coding assistants working on the news reader project. It covers build/lint/test commands, code style conventions, and development best practices.

## Table of Contents
1. [Project Overview](#project-overview)
2. [Build and Development Commands](#build-and-development-commands)
3. [Deployment](#deployment)
4. [Testing Commands](#testing-commands)
5. [Linting and Code Quality](#linting-and-code-quality)
6. [Code Style Guidelines](#code-style-guidelines)
7. [Import Conventions](#import-conventions)
8. [Type Annotations](#type-annotations)
9. [Naming Conventions](#naming-conventions)
10. [Error Handling](#error-handling)
11. [Language Processing](#language-processing-and-translation)
12. [File Organization](#file-organization)
13. [Security Practices](#security-practices)
14. [Performance Considerations](#performance-considerations)

## Project Overview

This is a Python-based RSS feed reader and web scraper that summarizes articles using various AI models. It can process both RSS feeds, direct website URLs, and YouTube channel RSS feeds, and generate consolidated overviews of the current state of the world.

### Architecture

The application follows a modular, extensible architecture designed for easy maintenance and future enhancements:

#### Core Components
- **Summarizer System**: Abstract interface for text summarization with concrete implementations for different AI providers (Ollama, future providers)
- **Content Extraction**: Modular system for extracting content from various sources (RSS, websites, YouTube)
- **Configuration Management**: Centralized settings management with defaults and validation
- **Data Management**: Clean database abstraction layer with SQLite backend

#### Key Classes
- `Summarizer`: Abstract base class for AI summarization providers
- `ContentExtractor`: Handles content extraction from different source types
- `NewsReaderConfig`: Centralized configuration management
- `DataManager`: Database operations and data persistence

#### Benefits
- **Extensible**: Easy to add new AI providers or content sources
- **Maintainable**: Clear separation of concerns and modular design
- **Testable**: Components can be tested independently
- **Configurable**: Settings-driven behavior with sensible defaults

### Files
- `nwsreader.py`: Core application with modular architecture
- `sources.txt`: Unified file containing RSS feeds and website URLs (auto-detected)
- `settings.json`: Configuration file for all settings and options
- `news_reader.db`: SQLite database for persistent storage

## Architecture and Extension Guide

### Adding New Summarizer Providers

To add support for a new AI summarization provider (e.g., OpenAI, Anthropic, local models):

1. **Create a new summarizer class** that inherits from `Summarizer`:
```python
class OpenAISummarizer(Summarizer):
    def __init__(self, config: SummarizerConfig):
        super().__init__(config)
        self.api_key = config.options.get('api_key')
        self.model = config.options.get('model', 'gpt-3.5-turbo')

    def is_available(self) -> bool:
        # Check if API key is set and service is accessible
        return bool(self.api_key)

    def summarize(self, text: str, prompt: str = "Summarize this text:") -> SummarizerResult:
        # Implement OpenAI API call
        try:
            # Your OpenAI API logic here
            return SummarizerResult(success=True, content=summary)
        except Exception as e:
            return SummarizerResult(success=False, error=str(e))
```

2. **Update the SummarizerFactory** to create your new summarizer:
```python
@staticmethod
def create_summarizer(config: SummarizerConfig) -> Summarizer:
    if config.provider_type == 'ollama':
        return OllamaSummarizer(config)
    elif config.provider_type == 'openai':
        return OpenAISummarizer(config)
    else:
        raise ValueError(f"Unsupported summarizer provider: {config.provider_type}")
```

3. **Update settings.json** to include your provider configuration:
```json
{
  "summarizer": {
    "provider": "openai",
    "config": {
      "api_key": "your-openai-api-key",
      "model": "gpt-4"
    }
  }
}
```

### Adding New Content Sources

To add support for new content sources (e.g., Twitter, Reddit, PDF documents):

1. **Extend the ContentExtractor class** with new extraction methods:
```python
class ContentExtractor:
    def extract_from_twitter(self, url: str) -> str:
        # Implement Twitter content extraction
        pass

    def extract_from_pdf(self, url: str) -> str:
        # Implement PDF content extraction
        pass
```

2. **Update detect_source_type()** to recognize new source types:
```python
def detect_source_type(url: str) -> str:
    if 'twitter.com' in url:
        return "twitter"
    elif url.endswith('.pdf'):
        return "pdf"
    # ... existing logic
```

3. **Add processing logic** in the main application loop to handle new source types.

### Language Processing and Translation

The system automatically detects the language of content and translates non-English material to English before summarization:

1. **Language Detection**: Uses automatic language detection to identify content language
2. **Translation**: Translates non-English content to the preferred language before summarization
3. **Fallback**: If translation fails, original content is summarized as-is

**Configuration:**
```json
{
  "summarizer": {
    "config": {
      "preferred_language": "en"
    }
  }
}
```

**Supported Features:**
- Automatic language detection for major languages
- Translation to preferred language before summarization
- Graceful fallback when translation services are unavailable
- Language information preserved in processing metadata

**Dependencies:**
```bash
pip install langdetect googletrans==4.0.0rc1
```

### Customizing Content Extraction

The `ContentExtractor` uses multiple strategies to find main content:

1. **CSS Selectors**: Tries common content selectors (article, .content, etc.)
2. **Fallback Methods**: Uses paragraph extraction if selectors fail
3. **Special Handling**: YouTube transcripts, JSON-LD structured data

To improve extraction for specific sites, add site-specific logic to `_extract_main_content()`.

### Configuration Management

The `NewsReaderConfig` class provides:
- **Settings Loading**: JSON file with defaults
- **Validation**: Ensures required settings are present
- **Provider Configuration**: Abstracts provider-specific settings

### Data Management

The `DataManager` class handles:
- **Database Operations**: CRUD operations for articles, error tracking, overviews
- **Migration Support**: JSON to SQLite conversion
- **Cleanup**: Automatic removal of old data

## Deployment

### Docker Deployment

The application is containerized and ready for deployment via Portainer or Docker Compose.

#### Prerequisites
- Docker and Docker Compose installed
- Ollama server running (user-provided)

#### Quick Start with Docker Compose

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd news-reader
   cp settings.example.json settings.json
   # Edit settings.json and sources.txt
   ```

2. **Start with Docker Compose**
   ```bash
   # Set interval in minutes (optional)
   export INTERVAL=60

   # Start services
   docker-compose up -d
   ```

3. **Monitor logs**
   ```bash
   docker-compose logs -f news-reader
   ```

#### Portainer Deployment

1. **Build the image**
   ```bash
   docker build -t news-reader .
   ```

2. **Deploy via Portainer**
   - Go to Portainer → Stacks
   - Create new stack with the following compose:
   ```yaml
   services:
     news-reader:
       image: news-reader:latest
       volumes:
         - /path/to/data:/app/data
       environment:
         - INTERVAL=60  # Optional: override settings.json interval
       restart: unless-stopped
   ```

   **Configuration**: After deployment, use Portainer's container editor to modify the configuration files inside the container at `/app/settings.json` and `/app/sources.txt`.

#### Environment Variables

- `INTERVAL`: Override run interval in minutes (optional, defaults to settings.json value)

#### Configuration

Configure the run interval in `settings.json`:

```json
{
  "interval": 60
}
```

#### Ollama Configuration

Configure your Ollama server address in `settings.json`:

```json
{
  "summarizer": {
    "config": {
      "host": "your-ollama-server-ip",
      "model": "smollm2:135m"
    }
  }
}
```

Or set the `OLLAMA_HOST` environment variable if not using settings.json.

#### Volume Mounts

- `/app/data`: Persistent storage for database and generated files

#### Configuration

Configuration files are created automatically from example templates on first run:

1. **settings.json**: Created from `settings.example.json`
2. **sources.txt**: Created from `sources.example.txt`

To modify them after deployment:

1. **Through Portainer**: Use the container file editor to modify `/app/settings.json` and `/app/sources.txt`
2. **Through Docker**: Use `docker exec` to edit files inside the running container

**Note**: Working configuration files are created at runtime and persist in the container's data volume.

### Continuous Operation

The application supports continuous monitoring with configurable intervals:

```bash
# Run every 30 minutes
python3 nwsreader.py --file sources.txt --interval 30

# Docker with custom interval
docker run -e INTERVAL=45 news-reader
```

## Build and Development Commands

### Environment Setup
```bash
# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Or install core dependencies manually
pip install requests feedparser beautifulsoup4 youtube-transcript-api langdetect googletrans==4.0.0rc1

# Install development dependencies
pip install pytest black ruff mypy
```

### Running the Application
```bash
# Process mixed sources from unified file (RSS feeds and websites auto-detected)
python3 nwsreader.py --file sources.txt

# Process single URL (type auto-detected)
python3 nwsreader.py --url "https://example.com/feed.xml"
python3 nwsreader.py --url "https://example.com/article"

# Force all URLs to be treated as websites
python3 nwsreader.py --file sources.txt --scrape

# Generate a consolidated state-of-the-world overview
python3 nwsreader.py --overview

# Generate overview with custom model/host
python3 nwsreader.py --overview --model "llama2" --host "localhost"

# Generate overview with custom prompts
python3 nwsreader.py --overview --overview-prompt "Give me a bullet-point summary of today's news"
```

### News Categorization

The system automatically categorizes news articles and organizes overviews by category:

**Available Categories:**
- Politics
- Business & Economy
- Technology
- Science & Health
- Sports
- Entertainment
- Crime & Law
- International
- US News
- Environment
- Education
- Other

**Features:**
- Automatic category detection from article content
- Category-based overview organization
- Stored categories in summary data for future analysis

### Enhanced Content Extraction

The system now extracts full article content and YouTube transcripts for comprehensive summarization:

**RSS Feed Enhancement:**
- Automatically fetches full article content when RSS provides insufficient text
- Extracts content from article pages when summaries are too short (<100 characters)
- Handles JSON-LD structured data for better content extraction

**YouTube Video Support:**
- Extracts video transcripts for summarization (requires `youtube-transcript-api`)
- Processes YouTube RSS feeds with full transcript content
- Falls back to video titles and descriptions if transcripts unavailable

**Content Sources:**
- RSS feed summaries (primary)
- Full article scraping (when RSS content insufficient)
- YouTube video transcripts (for video content)
- JSON-LD structured data extraction

#### YouTube Channel RSS Feeds

YouTube provides RSS feeds for all channels. To find a channel's RSS feed:

1. **Using Channel ID**: `https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID`
   - Find channel ID in YouTube URL or channel settings

2. **Using Username**: `https://www.youtube.com/feeds/videos.xml?user=USERNAME`
   - For channels with custom usernames

Example YouTube RSS feeds included:
- CNN: `https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw`
- BBC News: `https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA`

#### Configuration File (settings.json)

The application uses a `settings.json` file for configuration:

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
  }
}
```

Command-line arguments override settings file defaults.

### Output Channels

The application supports sending summaries and overviews to multiple output channels including console, Telegram, and Discord. Configure output channels in the `output` array in `settings.json`:

```json
{
  "output": [
    {
      "type": "console",
      "config": {
        "output_file": null
      }
    },
    {
      "type": "telegram",
      "config": {
        "bot_token": "your-telegram-bot-token",
        "chat_id": "your-chat-id"
      }
    },
    {
      "type": "discord",
      "config": {
        "webhook_url": "https://discord.com/api/webhooks/...",
        "username": "News Reader",
        "avatar_url": "https://example.com/avatar.png"
      }
    }
  ]
}
```

#### Telegram Setup
1. Create a bot with [@BotFather](https://t.me/botfather) on Telegram
2. Get your bot token
3. Start a chat with your bot or create a group/channel
4. Send a message to get the chat ID, or use [@userinfobot](https://t.me/userinfobot)
5. Add the bot as administrator to channels/groups

#### Discord Setup
1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook
4. Copy the webhook URL
5. Configure username and avatar URL (optional)

### Data Management & Retention

The application automatically manages data retention:

- **Summary Cleanup**: Article summaries older than 10 days are automatically deleted
- **Overview Retention**: Overview files older than 40 days are automatically deleted
- **Timestamp Tracking**: All summaries include timestamps for age-based cleanup
- **Daily Overview Updates**: Overviews for the same date are updated rather than creating duplicates

### Database Storage

The application now uses SQLite database for improved performance and reliability:

- **Migration**: Use `--migrate` to convert from JSON files to SQLite database
- **Tables**: Separate tables for articles, error tracking, and overviews
- **Backup**: Old JSON files are kept as backup during migration
- **Performance**: Faster queries and better data integrity

### Home Assistant Integration

The system is designed for daily news briefings via Home Assistant TTS:

- **Daily Overviews**: Generate and store daily news summaries
- **Export Function**: Use `--export-overview` to create TTS-ready file
- **File Format**: `daily_news_overview.txt` with greeting and content
- **Automation Ready**: Perfect for cron jobs and Home Assistant automation

### File Structure

```
news-reader/
├── sources.txt              # Source URLs
├── settings.json            # Configuration
├── news_reader.db          # SQLite database (new)
├── daily_news_overview.txt # Home Assistant TTS file (generated)
├── summaries.json          # Legacy JSON (kept as backup)
└── error_tracking.json     # Legacy JSON (kept as backup)
```

### Usage Examples

```bash
# Migrate from JSON to database
python3 nwsreader.py --migrate

# Generate daily overview
python3 nwsreader.py --overview

# Export for Home Assistant
python3 nwsreader.py --export-overview

# Daily automation script
python3 nwsreader.py --file sources.txt
python3 nwsreader.py --overview
python3 nwsreader.py --export-overview
```
Source Health Report:
⚠️ example.com: 3 consecutive failures, 8 total errors
   Top error: timeout_retry (5 times)
✅ All sources operating normally.
```

### File Structure

```
news-reader/
├── sources.txt              # Source URLs
├── settings.json            # Configuration
├── news_reader.db          # SQLite database (primary storage)
├── daily_news_overview.txt # Home Assistant TTS file (generated)
├── summaries.json          # Legacy JSON (kept as backup after migration)
└── error_tracking.json     # Legacy JSON (kept as backup after migration)
```

### Custom Prompts and Models

The application supports customizable prompts for both article summarization and overview generation:

```bash
# Use custom prompts
python3 nwsreader.py --article-prompt "Provide a detailed summary:" --overview-prompt "Summarize key global events:"

# Use different models for articles vs overview
python3 nwsreader.py --model "smollm2:135m" --overview-model "llama2"
```

### Development Server (if applicable)
```bash
# No development server for this CLI application
# Use direct script execution for development
```

## Processing Behavior

### Summary Failure Handling
- **Successful Summarization**: Articles are saved to database, categorized, and sent to configured output channels (Telegram, Discord, console)
- **Failed Summarization**: Articles are completely skipped - not saved to database, not sent to output channels, not marked as processed
- **Error Tracking**: Summarization failures are logged for monitoring but don't result in incomplete article processing

### Content Enhancement Strategy
- **RSS Feeds**: Articles with insufficient content (< 100 characters) trigger full article fetching
- **YouTube Videos**: Automatic transcript extraction for videos, with fallback to content scraping
- **Graceful Degradation**: Failed content fetching doesn't break the processing pipeline

### Output Channel Behavior
- Only successfully summarized articles are sent to output channels
- Failed articles are silently skipped to avoid spam
- Channel-specific error handling prevents one failed channel from affecting others

## Testing Commands

### Setup Testing Environment
```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock

# Create basic test structure if not exists
mkdir -p tests
touch tests/__init__.py
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_nwsreader.py

# Run single test function
pytest tests/test_nwsreader.py::test_summarize_text -v

# Run tests with coverage
pytest --cov=nwsreader --cov-report=html

# Run tests in verbose mode
pytest -v

# Run tests with specific marker
pytest -m "integration"
```

### Test Structure Guidelines
- Unit tests in `tests/` directory
- Test files named `test_*.py`
- Test functions named `test_*`
- Use pytest fixtures for common setup
- Mock external dependencies (requests, feedparser)

## Linting and Code Quality

### Ruff (Recommended Linter)
```bash
# Install ruff
pip install ruff

# Lint all files
ruff check .

# Lint specific file
ruff check nwsreader.py

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Alternative Linters
```bash
# Black for formatting
pip install black
black nwsreader.py

# Flake8 for style checking
pip install flake8
flake8 nwsreader.py

# MyPy for type checking
pip install mypy
mypy nwsreader.py
```

## Code Style Guidelines

### General Principles
- Write readable, maintainable code
- Follow PEP 8 style guide
- Use 4 spaces for indentation (never tabs)
- Keep lines under 88 characters (Black default)
- Use docstrings for all public functions
- Add comments for complex logic

### Function Structure
```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """
    Brief description of what function does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this exception is raised
    """
    # Implementation here
    pass
```

### Class Structure
```python
class ClassName:
    """Brief description of the class."""

    def __init__(self, param: Type) -> None:
        """Initialize the class."""
        self.param = param

    def method_name(self, param: Type) -> ReturnType:
        """Brief description of method."""
        pass
```

## Import Conventions

### Standard Library Imports
```python
import json
import os
import sys
from typing import Dict, List, Optional
```

### Third-party Imports
```python
import requests
import feedparser
```

### Local Imports
```python
from . import utils
from .models import FeedSummary
```

### Import Organization
1. Standard library imports (alphabetically sorted)
2. Blank line
3. Third-party imports (alphabetically sorted)
4. Blank line
5. Local imports (alphabetically sorted)

## Type Annotations

### Basic Types
```python
def process_feed(url: str, timeout: int = 30) -> Dict[str, str]:
    pass

def load_data(file_path: str) -> Optional[Dict[str, List[Dict[str, str]]]]:
    pass
```

### Complex Types
```python
from typing import Dict, List, Optional, Union, Any

FeedEntry = Dict[str, Union[str, int]]
FeedData = List[FeedEntry]
SummaryCache = Dict[str, FeedData]

def summarize_feeds(feeds: List[str]) -> SummaryCache:
    pass
```

### Generic Types
```python
from typing import TypeVar, Generic

T = TypeVar('T')

class Result(Generic[T]):
    def __init__(self, value: T, error: Optional[str] = None) -> None:
        self.value = value
        self.error = error
```

## Naming Conventions

### Variables and Functions
- Use `snake_case` for variables and functions
- Use descriptive names: `feed_url` not `url`, `summary_cache` not `cache`
- Boolean variables: `is_summarized`, `has_content`

### Constants
- Use `UPPER_SNAKE_CASE` for constants
- Define at module level

```python
DEFAULT_TIMEOUT = 120
OLLAMA_DEFAULT_MODEL = "smollm2:135m"
```

### Classes
- Use `PascalCase` for class names
- Use descriptive names: `RSSFeedProcessor` not `Processor`

### Methods
- Instance methods: `process_feed()`, `get_summary()`
- Class methods: `from_file()`, `create_default()`
- Static methods: `validate_url()`, `clean_text()`

## Error Handling

### Exception Patterns
```python
def safe_file_operation(file_path: str) -> Optional[Dict]:
    """Safely load JSON file with proper error handling."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")
        return None
```

### Custom Exceptions
```python
class RSSProcessingError(Exception):
    """Raised when RSS feed processing fails."""
    pass

class SummarizationError(Exception):
    """Raised when text summarization fails."""
    pass
```

### Error Messages
- Be descriptive but not verbose
- Include relevant context (file paths, URLs, etc.)
- Use logging levels appropriately

## File Organization

### Directory Structure
```
news-reader/
├── nwsreader.py          # Main application
├── feeds.txt            # RSS feed URLs
├── summaries.json       # Cached summaries
├── tests/               # Test files
│   ├── __init__.py
│   └── test_nwsreader.py
├── requirements.txt     # Python dependencies
├── pyproject.toml      # Project configuration
└── AGENTS.md           # This file
```

### File Naming
- Use `snake_case` for Python files
- Test files: `test_*.py`
- Configuration: `pyproject.toml`, `requirements.txt`

## Security Practices

### Input Validation
```python
def validate_url(url: str) -> bool:
    """Validate URL format and safety."""
    if not url or not url.startswith(('http://', 'https://')):
        return False
    # Additional validation logic
    return True
```

### Secrets Management
- Never hardcode API keys or passwords
- Use environment variables for sensitive data
- Store Ollama host in configuration, not code

### Data Sanitization
- Sanitize RSS feed content before processing
- Escape special characters in JSON output
- Validate file paths to prevent directory traversal

## Performance Considerations

### Memory Management
- Process feeds incrementally, not all at once
- Clear large data structures when no longer needed
- Use streaming for large JSON files

### Network Efficiency
- Implement retry logic with exponential backoff
- Cache summaries to avoid redundant API calls
- Use connection pooling for multiple requests

### Code Optimization
- Avoid unnecessary string concatenations
- Use list comprehensions over loops where appropriate
- Profile code with `cProfile` for bottlenecks

## Development Workflow

### Before Committing
1. Run tests: `pytest`
2. Run linter: `ruff check --fix .`
3. Format code: `ruff format .`
4. Type check: `mypy .`
5. Manual testing with sample feeds

### Code Review Checklist
- [ ] Tests pass and coverage >80%
- [ ] Code follows style guidelines
- [ ] Type annotations are complete
- [ ] Error handling is appropriate
- [ ] Documentation is updated
- [ ] Security considerations addressed

### Git Commit Messages
```
feat: add support for multiple RSS formats
fix: handle network timeouts gracefully
docs: update API documentation
style: format code with black
refactor: extract feed processing logic
test: add unit tests for summarization
```

This comprehensive guide ensures consistent, maintainable code across the project. Follow these guidelines when making changes or adding new features.