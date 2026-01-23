"""
News Reader Application

A Python-based RSS feed reader and web scraper that summarizes articles using various AI models.
Processes RSS feeds and direct website URLs, extracts content, and generates consolidated
news overviews organized by categories.

Features:
- RSS feed processing with automatic content enhancement
- Website scraping with article extraction
- YouTube transcript processing for video content
- Modular summarization system supporting multiple AI providers
- Category-based news organization
- Database storage with SQLite
- Error tracking and source health monitoring
- Home Assistant integration for daily briefings

Architecture:
- Summarizer Interface: Abstract base for different AI providers
- Content Extractors: Modular content extraction from various sources
- Configuration Manager: Centralized settings management
- Data Manager: Clean database abstraction layer

Author: News Reader Team
"""

import requests
import feedparser
import json
import argparse
import sys
import os
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
from typing import Dict, List, Tuple, Optional, Protocol, Any
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPTS_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPTS_AVAILABLE = False

try:
    from langdetect import detect, LangDetectError
    LANGUAGE_DETECTION_AVAILABLE = True
except ImportError:
    LANGUAGE_DETECTION_AVAILABLE = False

try:
    from googletrans import Translator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False


# ============================================================================
# SUMMARIZER SYSTEM
# ============================================================================

class SummarizerConfig:
    """Configuration for a summarizer provider."""

    def __init__(self, provider_type: str, **kwargs):
        """
        Initialize summarizer configuration.

        Args:
            provider_type: Type of summarizer ('ollama', etc.)
            **kwargs: Provider-specific configuration options
        """
        self.provider_type = provider_type
        self.options = kwargs


class SummarizerResult:
    """Result of a summarization operation."""

    def __init__(self, success: bool, content: str = "", error: str = "", original_language: str = "", translated: bool = False):
        """
        Initialize summarizer result.

        Args:
            success: Whether summarization was successful
            content: Summarized content (if successful)
            error: Error message (if failed)
            original_language: Detected language of original content
            translated: Whether content was translated before summarization
        """
        self.success = success
        self.content = content
        self.error = error
        self.original_language = original_language
        self.translated = translated


class Summarizer(ABC):
    """Abstract base class for text summarization providers."""

    def __init__(self, config: SummarizerConfig):
        """
        Initialize the summarizer.

        Args:
            config: Configuration for this summarizer
        """
        self.config = config

    @abstractmethod
    def summarize(self, text: str, prompt: str = "Summarize this text:") -> SummarizerResult:
        """
        Summarize the given text.

        Args:
            text: Text to summarize
            prompt: Summarization prompt/instruction

        Returns:
            SummarizerResult with the summary or error
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this summarizer is available and properly configured.

        Returns:
            True if the summarizer can be used
        """
        pass

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the given text.

        Args:
            text: Text to analyze

        Returns:
            ISO language code (e.g., 'en', 'es', 'fr') or 'unknown' if detection fails
        """
        if not LANGUAGE_DETECTION_AVAILABLE:
            return 'unknown'

        try:
            # Clean text for better detection
            clean_text = text.strip()
            if len(clean_text) < 10:  # Too short for reliable detection
                return 'unknown'

            detected = detect(clean_text)
            return detected
        except (LangDetectError, Exception):
            return 'unknown'

    def translate_text(self, text: str, target_language: str = 'en') -> str:
        """
        Translate text to the target language.

        Args:
            text: Text to translate
            target_language: Target language ISO code

        Returns:
            Translated text or original text if translation fails
        """
        if not TRANSLATION_AVAILABLE:
            return text

        try:
            translator = Translator()
            result = translator.translate(text, dest=target_language)
            return result.text
        except Exception:
            # Return original text if translation fails
            return text


class OllamaSummarizer(Summarizer):
    """Ollama-based text summarizer."""

    def __init__(self, config: SummarizerConfig):
        """
        Initialize Ollama summarizer.

        Args:
            config: Must contain 'host', 'model', and 'timeout' options
        """
        super().__init__(config)
        host_url = config.options.get('host', 'http://localhost:11434')
        parsed = urlparse(host_url)
        self.host = parsed.hostname
        self.port = parsed.port or 11434
        self.scheme = parsed.scheme
        self.model = config.options.get('model', 'smollm2:135m')
        self.timeout = config.options.get('timeout', 120)
        self.preferred_language = config.options.get('preferred_language', 'en')

    def is_available(self) -> bool:
        """Check if Ollama service is accessible."""
        try:
            # Simple health check by trying to reach the API
            response = requests.get(f"{self.scheme}://{self.host}:{self.port}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def summarize(self, text: str, prompt: str = "Summarize this text:") -> SummarizerResult:
        """
        Summarize text using Ollama API with language processing.

        Args:
            text: Text to summarize
            prompt: Summarization instruction

        Returns:
            SummarizerResult with summary or error
        """
        try:
            # Detect language of the input text
            detected_language = self.detect_language(text)
            translated = False
            processed_text = text

            # Translate to preferred language if different
            if detected_language != 'unknown' and detected_language != self.preferred_language:
                print(f"🌐 Detected language: {detected_language}, translating to {self.preferred_language}...")
                processed_text = self.translate_text(text, self.preferred_language)
                translated = True
                if processed_text != text:
                    print("✅ Translation completed")
                else:
                    print("⚠️ Translation failed, using original text")

            payload = {
                "model": self.model,
                "prompt": f"{prompt}\n\n{processed_text}",
                "stream": True
            }

            with requests.post(
                f"{self.scheme}://{self.host}:{self.port}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout
            ) as response:
                response.raise_for_status()

                summary = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "response" in data:
                        summary += data["response"]
                    if data.get("done"):
                        break

                return SummarizerResult(
                    success=True,
                    content=summary.strip(),
                    original_language=detected_language,
                    translated=translated
                )

        except requests.exceptions.ConnectionError as e:
            error_msg = f"❌ Cannot connect to Ollama server at {self.host}:{self.port}. Please ensure Ollama is running."
            print(error_msg)
            return SummarizerResult(success=False, error=error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = f"⏰ Timeout connecting to Ollama server at {self.host}:{self.port} (timeout: {self.timeout}s)"
            print(error_msg)
            return SummarizerResult(success=False, error=error_msg)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                error_msg = f"❌ Model '{self.model}' not found on Ollama server. Please ensure the model is installed."
                print(error_msg)
                print(f"💡 Available models can be listed with: ollama list")
                print(f"💡 Install the model with: ollama pull {self.model}")
            else:
                error_msg = f"❌ HTTP error from Ollama server: {e.response.status_code} - {e.response.reason}"
                print(error_msg)
            return SummarizerResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"❌ Ollama summarization failed: {e}"
            print(error_msg)
            return SummarizerResult(success=False, error=error_msg)


class SummarizerFactory:
    """Factory for creating summarizer instances."""

    @staticmethod
    def create_summarizer(config: SummarizerConfig) -> Summarizer:
        """
        Create a summarizer instance based on configuration.

        Args:
            config: Summarizer configuration

        Returns:
            Configured summarizer instance

        Raises:
            ValueError: If provider type is not supported
        """
        if config.provider_type == 'ollama':
            return OllamaSummarizer(config)
        else:
            raise ValueError(f"Unsupported summarizer provider: {config.provider_type}")


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

class NewsReaderConfig:
    """Centralized configuration management for the news reader."""

    def __init__(self, settings_file: str = "settings.json"):
        """
        Initialize configuration from file.

        Args:
            settings_file: Path to settings JSON file
        """
        self.settings_file = settings_file
        self._load_settings()
        self._ensure_sources_file()

    def _load_settings(self):
        """Load settings from JSON file with defaults."""
        # Check for settings in multiple locations, prioritize /app/data
        settings_paths = [
            "/app/data/settings.json",  # Priority 1: Mounted data directory
            self.settings_file,          # Priority 2: Specified location
            "settings.json",             # Priority 3: Current directory fallback
        ]

        for path in settings_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        self.settings = json.load(f)
                    return
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid JSON in {path}: {e}")
                    print(f"💡 Check for missing commas, quotes, or bracket mismatches")
                    continue

        # Config files are created by Docker entrypoint, use defaults as fallback
        self.settings = self._get_defaults()
        self._save_settings()

    def _ensure_sources_file(self):
        """Ensure sources file exists (JSON or text), creating from settings or example if needed."""
        sources_file = self.settings.get("files", {}).get("sources", "sources.txt")

        # Check if sources are defined inline in settings
        if "sources" in self.settings and "groups" in self.settings["sources"]:
            print("✅ Using inline sources from settings.json")
            return  # Sources defined inline

        # Priority: JSON first (new format), then TXT (legacy)
        sources_paths = [
            "sources.json",      # Preferred JSON format
            "sources.txt",       # Legacy text format
            sources_file,        # Configured location (fallback)
        ]

        for path in sources_paths:
            if os.path.exists(path):
                # Update settings to point to the found file
                self.settings["files"]["sources"] = path
                return  # File found

        # Create default sources file (TXT format for simplicity)
        self._create_default_sources_text("sources.txt")

    def _create_default_sources_json(self, filepath: str):
        """Create default sources file in JSON format."""
        default_sources = {
            "groups": {
                "general-news": {
                    "description": "General news sources for all channels",
                    "channels": [],
                    "prompt": None,
                    "sources": [
                        "https://feeds.bbci.co.uk/news/rss.xml",
                        "https://rss.cnn.com/rss/edition.rss"
                    ]
                },
                "tech-news": {
                    "description": "Technology news for Discord",
                    "channels": ["discord"],
                    "prompt": None,
                    "sources": [
                        "https://feeds.feedburner.com/TechCrunch/",
                        "https://www.reddit.com/r/technology/.rss"
                    ]
                }
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default_sources, f, indent=2, ensure_ascii=False)

        print(f"✅ Created default {filepath} with sample grouped sources")

    def _create_default_sources_text(self, filepath: str):
        """Create default sources file in text format (legacy)."""
        with open(filepath, 'w') as f:
            f.write("# Add your RSS feeds and websites here\n")
            f.write("# RSS feeds (automatically detected)\n")
            f.write("https://feeds.bbci.co.uk/news/rss.xml\n")
            f.write("https://rss.cnn.com/rss/edition.rss\n")
            f.write("\n")
            f.write("# Websites for scraping (automatically detected)\n")
            f.write("# https://example.com/news\n")
        print(f"✅ Created default {filepath} with sample feeds")

    def _get_defaults(self) -> Dict:
        """Get default settings."""
        return {
            "ollama": {
                "host": "localhost",
                "model": "smollm2:135m",
                "overview_model": "llama2",
                "timeout": 120
            },
            "processing": {
                "max_overview_summaries": 50,
                "scrape_timeout": 30,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "prompts": {
                "article_summary": "Summarize this article briefly:",
                "overview_summary": "Based on the following news summaries, provide a comprehensive overview..."
            },
            "files": {
                "sources": "sources.txt",
                "database": "news_reader.db"
            },
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
                    "type": "console",
                    "config": {
                        "output_file": None
                    }
                }
            ],
            "interval": 60
        }

    def _save_settings(self):
        """Save current settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save settings: {e}")

    def get_summarizer_config(self) -> SummarizerConfig:
        """Get configuration for the summarizer."""
        summarizer_settings = self.settings.get('summarizer', {})
        provider = summarizer_settings.get('provider', 'ollama')
        config_options = summarizer_settings.get('config', {})

        # For backward compatibility, use ollama settings if no summarizer config
        if not config_options and provider == 'ollama':
            config_options = self.settings.get('ollama', {})

        return SummarizerConfig(provider, **config_options)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value and save."""
        self.settings[key] = value
        self._save_settings()

    def get_output_channels(self, channel_names: Optional[List[str]] = None) -> List[Any]:
        """
        Get configured output channels.

        Args:
            channel_names: Optional list of channel names to filter by.
                         If None, returns all available channels.

        Returns:
            List of configured output channel instances
        """
        output_settings = self.settings.get('output', {})
        print(f"   🔍 get_output_channels called with channel_names={channel_names}")
        print(f"   🔍 output_settings structure: {list(output_settings.keys()) if isinstance(output_settings, dict) else type(output_settings)}")

        # Support both old array format and new named channels format
        if isinstance(output_settings, list):
            # Legacy format: array of channel configs
            return self._get_output_channels_legacy(output_settings, channel_names)
        else:
            # New format: named channels object
            return self._get_output_channels_named(output_settings, channel_names)

    def _get_output_channels_legacy(self, output_settings: List[Dict], channel_names: Optional[List[str]] = None) -> List[Any]:
        """Get output channels from legacy array format."""
        channels = []

        for channel_config in output_settings:
            channel_type = channel_config.get('type')
            if channel_type:
                config = OutputChannelConfig(channel_type, **channel_config.get('config', {}))
                try:
                    channel = OutputChannelFactory.create_channel(config)
                    if channel.is_available():
                        channels.append(channel)
                    else:
                        print(f"Warning: Output channel {channel_type} not available (not configured)")
                except ValueError as e:
                    print(f"Warning: {e}")

        return channels

    def _get_output_channels_named(self, output_settings: Dict, channel_names: Optional[List[str]] = None) -> List[Any]:
        """Get output channels from named channels format."""
        channels = []
        named_channels = output_settings.get('channels', {})
        print(f"   🔍 Found {len(named_channels)} named channels: {list(named_channels.keys())}")

        # If no specific channel names requested, get all channels
        if channel_names is None:
            print("   🔍 Getting ALL channels")
            for channel_name, channel_def in named_channels.items():
                channel_type = channel_def.get('type')
                channel_config = channel_def.get('config', {})
                print(f"   🔍 Creating channel '{channel_name}' of type '{channel_type}'")
                self._create_channel(channels, channel_type, channel_config)
            return channels

        # Get specific channels by name
        print(f"   🔍 Getting specific channels: {channel_names}")
        for channel_name in channel_names:
            if channel_name in named_channels:
                channel_def = named_channels[channel_name]
                channel_type = channel_def.get('type')
                channel_config = channel_def.get('config', {})
                print(f"   🔍 Creating channel '{channel_name}' of type '{channel_type}'")
                self._create_channel(channels, channel_type, channel_config)
            else:
                print(f"Warning: Output channel '{channel_name}' not found in configuration")

        return channels

    def _create_channel(self, channels, channel_type, channel_config):
        """Helper to create and add a channel."""
        if channel_type:
            config = OutputChannelConfig(channel_type, **channel_config)
            try:
                channel = OutputChannelFactory.create_channel(config)
                if channel.is_available():
                    channels.append(channel)
                else:
                    print(f"Warning: Output channel '{channel_type}' not available (not configured)")
            except ValueError as e:
                print(f"Warning: {e}")

    def get_interval(self) -> int:
        """Get the run interval in minutes from settings or environment."""
        import os
        # First check settings file, then environment variable
        interval = self.settings.get('interval', os.getenv('INTERVAL'))
        if interval is None:
            return 60  # Default 60 minutes
        try:
            return int(interval)
        except (ValueError, TypeError):
            return 60  # Default if invalid


# ============================================================================
# CONTENT EXTRACTION
# ============================================================================

class ContentExtractor:
    """Handles content extraction from various sources."""

    def __init__(self, config: NewsReaderConfig):
        """
        Initialize content extractor.

        Args:
            config: Application configuration
        """
        self.config = config

    def extract_from_url(self, url: str, timeout: Optional[int] = None) -> str:
        """
        Extract content from a URL (RSS or website).

        Args:
            url: URL to extract content from
            timeout: Request timeout (uses config default if None)

        Returns:
            Extracted content or error message
        """
        if timeout is None:
            timeout = self.config.get('processing', {}).get('scrape_timeout', 30)

        try:
            headers = {
                'User-Agent': self.config.get('processing', {}).get(
                    'user_agent',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
            }

            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')

            # Check for YouTube content
            if self._is_youtube_video_url(url):
                transcript = self._extract_youtube_transcript(url)
                if transcript and not (transcript.startswith('[Error') or
                                     transcript.startswith('[Could not') or
                                     transcript.startswith('[Invalid') or
                                     transcript.startswith('[YouTube')):
                    return transcript

            # Extract main article content
            return self._extract_main_content(soup)

        except Exception as e:
            return f"[Error extracting content from {url}: {e}]"

    def _is_youtube_video_url(self, url: str) -> bool:
        """Check if URL is a YouTube video URL (not channel, playlist, etc.)."""
        if 'youtu.be/' in url:
            return True
        if 'youtube.com/watch?v=' in url:
            return True
        if 'youtube.com/embed/' in url:
            return True
        if 'youtube.com/shorts/' in url:
            return True
        return False

    def _extract_youtube_transcript(self, url: str) -> str:
        """Extract YouTube transcript if available."""
        if not YOUTUBE_TRANSCRIPTS_AVAILABLE:
            return "[YouTube transcript extraction not available]"

        try:
            # Extract video ID from URL - handle multiple YouTube URL formats
            video_id = None

            # Standard YouTube watch URL
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0].split('#')[0]
            # Short YouTube URL
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0].split('#')[0]
            # YouTube embed URL
            elif 'youtube.com/embed/' in url:
                video_id = url.split('youtube.com/embed/')[1].split('?')[0].split('&')[0].split('#')[0]
            # YouTube shorts URL
            elif 'youtube.com/shorts/' in url:
                video_id = url.split('youtube.com/shorts/')[1].split('?')[0].split('&')[0].split('#')[0]

            # Validate video ID format (YouTube video IDs are 11 characters)
            if not video_id or len(video_id) != 11:
                print(f"⚠️ Invalid YouTube video ID format for URL: {url} (extracted ID: '{video_id}')")
                return "[Invalid YouTube video ID format]"

            # Get transcript using correct API
            transcript_api = YouTubeTranscriptApi()
            transcript = transcript_api.fetch(video_id)

            # Combine transcript text
            transcript_text = ""
            for entry in transcript:
                transcript_text += entry.text + " "

            # Clean up the text
            transcript_text = ' '.join(transcript_text.split())
            return transcript_text if transcript_text else "[Empty transcript]"

        except Exception as e:
            return f"[Error extracting YouTube transcript: {e}]"

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML soup."""
        # Try multiple selectors for main content
        content_selectors = [
            'article',
            '[class*="content"]',
            '[class*="article"]',
            '[class*="post"]',
            'main',
            '.entry-content',
            '#content'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Remove unwanted elements
                for unwanted in content_elem.select('script, style, nav, header, footer, aside, .ads, .comments'):
                    unwanted.decompose()

                text = content_elem.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Minimum content length
                    return text

        # Fallback: extract from body
        body = soup.find('body')
        if body:
            # Remove common unwanted elements
            for unwanted in body.select('script, style, nav, header, footer, aside, .ads, .comments'):
                unwanted.decompose()

            text = body.get_text(separator=' ', strip=True)
            return text

        return "[Could not extract content]"


# ============================================================================
# DATA MANAGEMENT
# ============================================================================

class DataManager:
    """Manages data persistence operations."""

    def __init__(self, config: NewsReaderConfig):
        """
        Initialize data manager.

        Args:
            config: Application configuration
        """
        self.config = config
        self.db_file = config.get('files', {}).get('database', 'news_reader.db')


# ============================================================================
# OUTPUT CHANNELS
# ============================================================================

class OutputChannelConfig:
    """Configuration for an output channel."""

    def __init__(self, channel_type: str, **kwargs):
        """
        Initialize output channel configuration.

        Args:
            channel_type: Type of output channel ('telegram', 'discord', 'console', etc.)
            **kwargs: Channel-specific configuration options
        """
        self.channel_type = channel_type
        self.options = kwargs


class OutputChannelResult:
    """Result of an output operation."""

    def __init__(self, success: bool, message: str = "", error: str = ""):
        """
        Initialize output result.

        Args:
            success: Whether output was successful
            message: Success message or identifier
            error: Error message if failed
        """
        self.success = success
        self.message = message
        self.error = error


class OutputChannel(ABC):
    """Abstract base class for output channels."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize the output channel.

        Args:
            config: Configuration for this channel
        """
        self.config = config

    @abstractmethod
    def send_summary(self, title: str, summary: str, source: str = "", category: str = "") -> OutputChannelResult:
        """
        Send a summary to this output channel.

        Args:
            title: Article title
            summary: Article summary
            source: Source name
            category: Article category

        Returns:
            OutputChannelResult with success status and message
        """
        pass

    @abstractmethod
    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        """
        Send a daily overview to this output channel.

        Args:
            overview: The overview content
            date: Date string for the overview

        Returns:
            OutputChannelResult with success status and message
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this output channel is available and properly configured.

        Returns:
            True if the channel can be used
        """
        pass


class ConsoleOutputChannel(OutputChannel):
    """Console/file output channel."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize console output channel.

        Args:
            config: Must contain 'output_file' option for file output
        """
        super().__init__(config)
        self.output_file = config.options.get('output_file')

    def is_available(self) -> bool:
        """Console is always available."""
        return True

    def send_summary(self, title: str, summary: str, source: str = "", category: str = "") -> OutputChannelResult:
        """
        Print summary to console or file.

        Args:
            title: Article title
            summary: Article summary
            source: Source name
            category: Article category

        Returns:
            OutputChannelResult with success status
        """
        try:
            output = f"📄 {title}\n"
            if source:
                output += f"Source: {source}\n"
            if category:
                output += f"Category: {category}\n"
            output += f"Summary: {summary}\n\n"

            if self.output_file:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(output)
                print(f"✅ Console: Summary written to {self.output_file}")
                return OutputChannelResult(success=True, message=f"Written to {self.output_file}")
            else:
                print(output)
                print(f"✅ Console: Summary printed to console")
                return OutputChannelResult(success=True, message="Printed to console")

        except Exception as e:
            error_msg = f"Console output failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)

    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        """
        Print overview to console or file.

        Args:
            overview: The overview content
            date: Date string for the overview

        Returns:
            OutputChannelResult with success status
        """
        try:
            header = f"🌍 Daily News Overview"
            if date:
                header += f" - {date}"
            header += "\n" + "="*50 + "\n\n"

            output = header + overview

            if self.output_file:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"✅ Console: Overview written to {self.output_file}")
                return OutputChannelResult(success=True, message=f"Overview written to {self.output_file}")
            else:
                print(output)
                print(f"✅ Console: Overview printed to console")
                return OutputChannelResult(success=True, message="Overview printed to console")

        except Exception as e:
            error_msg = f"Console overview output failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)


class TelegramOutputChannel(OutputChannel):
    """Telegram bot output channel."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize Telegram output channel.

        Args:
            config: Must contain 'bot_token' and 'chat_id' options
        """
        super().__init__(config)
        self.bot_token = config.options.get('bot_token')
        self.chat_id = config.options.get('chat_id')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_available(self) -> bool:
        """Check if Telegram bot is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def send_summary(self, title: str, summary: str, source: str = "", category: str = "") -> OutputChannelResult:
        """
        Send summary to Telegram chat.

        Args:
            title: Article title
            summary: Article summary
            source: Source name
            category: Article category

        Returns:
            OutputChannelResult with success status
        """
        if not self.is_available():
            return OutputChannelResult(success=False, error="Telegram not properly configured")

        try:
            message = f"📄 *{title}*\n"
            if source:
                message += f"Source: _{source}_\n"
            if category:
                message += f"Category: _{category}_\n"
            message += f"\n{summary}"

            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }

            response = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get('ok'):
                message_id = result['result']['message_id']
                print(f"✅ Telegram: Summary sent to chat {self.chat_id} (message ID: {message_id})")
                return OutputChannelResult(success=True, message=f"Message sent (ID: {message_id})")
            else:
                error_msg = f"Telegram API error: {result}"
                print(f"❌ {error_msg}")
                return OutputChannelResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Telegram send failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)

    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        """
        Send overview to Telegram chat.

        Args:
            overview: The overview content
            date: Date string for the overview

        Returns:
            OutputChannelResult with success status
        """
        try:
            title = "🌍 Daily News Overview"
            if date:
                title += f" - {date}"

            # Telegram has message length limits, so we may need to split
            message = f"*{title}*\n\n{overview}"

            # Check if message is too long (Telegram limit is 4096 characters)
            if len(message) > 4000:
                # Split into chunks
                chunks = self._split_message(message, 4000)
                for i, chunk in enumerate(chunks):
                    payload = {
                        'chat_id': self.chat_id,
                        'text': chunk,
                        'parse_mode': 'Markdown'
                    }
                    if i > 0:
                        payload['parse_mode'] = None  # Only first message uses markdown

                    response = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=30)
                    response.raise_for_status()
                    import time
                    time.sleep(0.1)  # Small delay between messages

                print(f"✅ Telegram: Overview sent to chat {self.chat_id} in {len(chunks)} messages")
                return OutputChannelResult(success=True, message=f"Overview sent in {len(chunks)} messages")
            else:
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }

                response = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=30)
                response.raise_for_status()

                result = response.json()
                if result.get('ok'):
                    message_id = result['result']['message_id']
                    print(f"✅ Telegram: Overview sent to chat {self.chat_id} (message ID: {message_id})")
                    return OutputChannelResult(success=True, message=f"Overview sent (ID: {message_id})")
                else:
                    error_msg = f"Telegram API error: {result}"
                    print(f"❌ {error_msg}")
                    return OutputChannelResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Telegram overview send failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)

    def _split_message(self, text: str, max_length: int) -> List[str]:
        """Split a long message into chunks at word boundaries."""
        chunks = []
        while len(text) > max_length:
            # Find the last space within the limit
            split_point = text.rfind(' ', 0, max_length)
            if split_point == -1:
                split_point = max_length

            chunks.append(text[:split_point])
            text = text[split_point:].lstrip()

        if text:
            chunks.append(text)

        return chunks


class DiscordOutputChannel(OutputChannel):
    """Discord output channel supporting both webhooks and bot tokens."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize Discord output channel.

        Args:
            config: Must contain either 'webhook_url' or 'bot_token' + 'channel_id'
        """
        super().__init__(config)
        self.webhook_url = config.options.get('webhook_url')
        self.bot_token = config.options.get('bot_token')
        self.channel_id = config.options.get('channel_id')
        self.username = config.options.get('username', 'News Reader')
        self.avatar_url = config.options.get('avatar_url')

        # Determine authentication method
        if self.webhook_url:
            self.auth_method = 'webhook'
        elif self.bot_token and self.channel_id:
            self.auth_method = 'bot'
            self.api_url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
            self.headers = {
                'Authorization': f'Bot {self.bot_token}',
                'Content-Type': 'application/json'
            }
        else:
            self.auth_method = None

    def is_available(self) -> bool:
        """Check if Discord is properly configured and connected."""
        if self.auth_method is None:
            print("❌ Discord: No valid authentication method configured")
            return False

        if self.auth_method == 'bot':
            # Test bot token by getting user info
            try:
                response = requests.get("https://discord.com/api/v10/users/@me",
                                      headers={'Authorization': f'Bot {self.bot_token}'},
                                      timeout=10)
                if response.status_code == 200:
                    # Check channel access
                    channel_response = requests.get(f"https://discord.com/api/v10/channels/{self.channel_id}",
                                                   headers={'Authorization': f'Bot {self.bot_token}'},
                                                   timeout=10)
                    if channel_response.status_code == 200:
                        return True
                    else:
                        print(f"❌ Discord: Cannot access channel {self.channel_id} ({channel_response.status_code}: {channel_response.text})")
                        return False
                else:
                    print(f"❌ Discord: Invalid bot token ({response.status_code}: {response.text})")
                    return False
            except Exception as e:
                print(f"❌ Discord: Connection failed ({e})")
                return False
        elif self.auth_method == 'webhook':
            # For webhook, just check if URL is set (can't test without posting)
            if self.webhook_url:
                return True
            else:
                print("❌ Discord: Webhook URL not configured")
                return False

        return False

    def send_summary(self, title: str, summary: str, source: str = "", category: str = "") -> OutputChannelResult:
        """
        Send summary to Discord via webhook or bot token.

        Args:
            title: Article title
            summary: Article summary
            source: Source name
            category: Article category

        Returns:
            OutputChannelResult with success status
        """
        if not self.is_available():
            return OutputChannelResult(success=False, error="Discord not properly configured")

        try:
            embed = {
                "title": title,
                "description": summary,
                "color": 0x3498db,  # Blue color
                "footer": {
                    "text": f"Source: {source}" if source else "News Reader"
                }
            }

            if category:
                embed["fields"] = [{
                    "name": "Category",
                    "value": category,
                    "inline": True
                }]

            if self.auth_method == 'webhook':
                payload = {
                    "username": self.username,
                    "embeds": [embed]
                }
                if self.avatar_url:
                    payload["avatar_url"] = self.avatar_url
                response = requests.post(self.webhook_url, json=payload, timeout=30)
                print(f"✅ Discord webhook: Summary sent successfully")

            elif self.auth_method == 'bot':
                payload = {
                    "embeds": [embed]
                }
                response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
                print(f"✅ Discord bot: Summary sent to channel {self.channel_id}")

            response.raise_for_status()
            return OutputChannelResult(success=True, message="Summary sent to Discord")

        except Exception as e:
            error_msg = f"Discord send failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)

    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        """
        Send overview to Discord webhook.

        Args:
            overview: The overview content
            date: Date string for the overview

        Returns:
            OutputChannelResult with success status
        """
        try:
            title = "🌍 Daily News Overview"
            if date:
                title += f" - {date}"

            # Discord has embed description limits, so we may need to split
            if len(overview) > 4000:
                # Split overview into multiple embeds
                chunks = self._split_overview(overview, 4000)
                embeds = []

                for i, chunk in enumerate(chunks):
                    embed = {
                        "title": f"{title} (Part {i+1}/{len(chunks)})" if len(chunks) > 1 else title,
                        "description": chunk,
                        "color": 0x2ecc71  # Green color
                    }
                    embeds.append(embed)
            else:
                embeds = [{
                    "title": title,
                    "description": overview,
                    "color": 0x2ecc71
                }]

            if self.auth_method == 'webhook':
                payload = {
                    "username": self.username,
                    "embeds": embeds
                }
                if self.avatar_url:
                    payload["avatar_url"] = self.avatar_url
                response = requests.post(self.webhook_url, json=payload, timeout=30)
                print(f"✅ Discord webhook: Overview sent successfully ({len(embeds)} embeds)")

            elif self.auth_method == 'bot':
                payload = {
                    "embeds": embeds
                }
                response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
                print(f"✅ Discord bot: Overview sent to channel {self.channel_id} ({len(embeds)} embeds)")

            response.raise_for_status()
            return OutputChannelResult(success=True, message=f"Overview sent to Discord ({len(embeds)} embed(s))")

        except Exception as e:
            error_msg = f"Discord overview send failed: {e}"
            print(f"❌ {error_msg}")
            return OutputChannelResult(success=False, error=error_msg)

    def _split_overview(self, text: str, max_length: int) -> List[str]:
        """Split overview text into chunks at paragraph boundaries."""
        chunks = []
        while len(text) > max_length:
            # Try to split at double newlines (paragraphs)
            split_point = text.rfind('\n\n', 0, max_length)
            if split_point == -1:
                # Try single newlines
                split_point = text.rfind('\n', 0, max_length)
            if split_point == -1:
                # Force split at max_length
                split_point = max_length

            chunks.append(text[:split_point])
            text = text[split_point:].lstrip()

        if text:
            chunks.append(text)

        return chunks


class SourceGroup:
    """Represents a group of sources that should be sent to specific output channels."""

    def __init__(self, name: str, urls: List[str], output_channels: List[str], prompt: Optional[str] = None):
        """
        Initialize a source group.

        Args:
            name: Group name (for identification)
            urls: List of source URLs in this group
            output_channels: List of output channel names this group should use
            prompt: Custom summarization prompt for this group (optional)
        """
        self.name = name
        self.urls = urls
        self.output_channels = output_channels
        self.prompt = prompt

    def __repr__(self):
        return f"SourceGroup(name='{self.name}', urls={len(self.urls)}, channels={self.output_channels}, prompt={bool(self.prompt)})"


def parse_source_groups(filepath: str, settings: Optional[Dict] = None) -> Dict[str, SourceGroup]:
    """
    Parse sources from file or settings and return groups with their associated output channels and prompts.

    Args:
        filepath: Path to sources file (supports both .json and .txt formats)
        settings: Settings dictionary to check for inline sources

    Returns:
        Dictionary mapping group names to SourceGroup objects
    """
    # Check for inline sources in settings first
    if settings and "sources" in settings and "groups" in settings["sources"]:
        return _parse_source_groups_inline(settings["sources"]["groups"])

    # Fall back to file-based parsing
    try:
        if filepath.endswith('.json'):
            return _parse_source_groups_json(filepath)
        else:
            return _parse_source_groups_text(filepath)

    except FileNotFoundError:
        print(f"⚠️ Sources file not found: {filepath}")
        return {}


def _parse_source_groups_inline(groups_data: Dict) -> Dict[str, SourceGroup]:
    """Parse inline sources from settings."""
    groups = {}
    for group_name, group_data in groups_data.items():
        urls = group_data.get("sources", [])
        channels = group_data.get("channels", [])
        prompt = group_data.get("prompt")

        if urls:  # Only create group if it has sources
            groups[group_name] = SourceGroup(group_name, urls, channels, prompt)

    return groups


def _parse_source_groups_json(filepath: str) -> Dict[str, SourceGroup]:
    """Parse JSON format sources file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = {}
    for group_name, group_data in data.get("groups", {}).items():
        urls = group_data.get("sources", [])
        channels = group_data.get("channels", [])
        prompt = group_data.get("prompt")

        if urls:  # Only create group if it has sources
            groups[group_name] = SourceGroup(group_name, urls, channels, prompt)

    return groups


def _parse_source_groups_text(filepath: str) -> Dict[str, SourceGroup]:
    """
    Parse text format sources file (legacy support).

    Args:
        filepath: Path to sources file

    Returns:
        Dictionary mapping group names to SourceGroup objects
    """
    try:
        with open(filepath, "r") as f:
            content = f.read()

        lines = content.split('\n')
        current_group = None
        groups = {}
        current_urls = []
        current_channels = []
        current_prompt = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('[') and line.endswith(']'):
                # Save previous group if exists
                if current_group and current_urls:
                    groups[current_group] = SourceGroup(current_group, current_urls, current_channels, current_prompt)

                # Start new group
                group_header = line[1:-1]  # Remove brackets

                # Parse group header: [name:channels:prompt] or [name:channels] or [name]
                parts = group_header.split(':')
                group_name = parts[0]

                current_channels = []
                current_prompt = None

                if len(parts) >= 2:
                    # Has channels specification
                    channels_str = parts[1]
                    current_channels = [c.strip() for c in channels_str.split(',') if c.strip()]

                if len(parts) >= 3:
                    # Has prompt specification
                    current_prompt = ':'.join(parts[2:])  # Rejoin in case prompt contains colons

                current_group = group_name
                current_urls = []
            elif current_group:
                # URL in current group
                current_urls.append(line)

        # Save final group
        if current_group and current_urls:
            groups[current_group] = SourceGroup(current_group, current_urls, current_channels, current_prompt)

        return groups

    except Exception as e:
        print(f"⚠️ Error parsing text sources file: {e}")
        return {}


class OutputChannelFactory:
    """Factory for creating output channel instances."""

    @staticmethod
    def create_channel(config: OutputChannelConfig) -> OutputChannel:
        """
        Create an output channel instance based on configuration.

        Args:
            config: Output channel configuration

        Returns:
            Configured output channel instance

        Raises:
            ValueError: If channel type is not supported
        """
        if config.channel_type == 'console':
            return ConsoleOutputChannel(config)
        elif config.channel_type == 'telegram':
            return TelegramOutputChannel(config)
        elif config.channel_type == 'discord':
            return DiscordOutputChannel(config)
        else:
            raise ValueError(f"Unsupported output channel: {config.channel_type}")





def categorize_error(error_message: str) -> str:
    """Categorize error types for better tracking and handling."""
    error_msg = str(error_message).lower()

    # Content extraction errors
    if any(term in error_msg for term in ['could not extract', 'no content found', 'extraction failed']):
        return "content_extraction"

    # YouTube specific errors
    if any(term in error_msg for term in ['transcript', 'youtube']):
        return "youtube"

    # DNS and network errors
    if any(term in error_msg for term in ['name resolution', 'dns', 'network unreachable']):
        return "network"

    # Default category
    return "unknown"

def load_error_tracking() -> Dict:
    """Load error tracking data from file."""
    try:
        with open("error_tracking.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_error_tracking(error_data: Dict):
    """Save error tracking data to file."""
    try:
        with open("error_tracking.json", "w") as f:
            json.dump(error_data, f, indent=2)
    except Exception as e:
        print(f"[Error saving error tracking: {e}]")

def track_source_error(source_url: str, error_message: str, error_tracking: Dict):
    """Track errors for a specific source."""
    error_category = categorize_error(error_message)
    source_domain = urlparse(source_url).netloc

    if source_domain not in error_tracking:
        error_tracking[source_domain] = {
            "total_errors": 0,
            "categories": {},
            "last_error": None,
            "first_error": None,
            "consecutive_failures": 0
        }

    source_data = error_tracking[source_domain]
    current_time = datetime.now().isoformat()

    # Update error counts
    source_data["total_errors"] += 1
    source_data["last_error"] = current_time

    if source_data["first_error"] is None:
        source_data["first_error"] = current_time

    # Update category counts
    if error_category not in source_data["categories"]:
        source_data["categories"][error_category] = 0
    source_data["categories"][error_category] += 1

    # Check for consecutive failures (simple heuristic)
    # If we get errors within a short time frame, increment consecutive counter
    # This tracks if errors are happening repeatedly without successful processing
    if source_data.get("last_success"):
        last_success = datetime.fromisoformat(source_data["last_success"])
        time_since_success = datetime.now() - last_success
        # If no success in more than 24 hours, count as consecutive failure
        if time_since_success.days > 1:
            source_data["consecutive_failures"] += 1
    else:
        # No recorded success, so this is a consecutive failure
        source_data["consecutive_failures"] += 1

    # Reset consecutive failures on success (will be called separately)
    return error_tracking

def track_source_success(source_url: str, error_tracking: Dict):
    """Track successful processing for a source."""
    source_domain = urlparse(source_url).netloc
    if source_domain in error_tracking:
        error_tracking[source_domain]["consecutive_failures"] = 0
        error_tracking[source_domain]["last_success"] = datetime.now().isoformat()

def should_exclude_source(source_url: str, error_tracking: Dict, max_consecutive_failures: int = 5) -> bool:
    """Check if a source should be excluded due to excessive failures."""
    source_domain = urlparse(source_url).netloc
    if source_domain in error_tracking:
        source_data = error_tracking[source_domain]
        return source_data.get("consecutive_failures", 0) >= max_consecutive_failures
    return False

def report_source_health(error_tracking: Dict):
    """Generate a report of source health status."""
    if not error_tracking:
        return "All sources healthy."

    report = "Source Health Report:\n"
    unhealthy_sources = []

    for domain, data in error_tracking.items():
        total_errors = data.get("total_errors", 0)
        consecutive_failures = data.get("consecutive_failures", 0)
        categories = data.get("categories", {})

        if consecutive_failures >= 3 or total_errors >= 10:
            unhealthy_sources.append(f"⚠️  {domain}: {consecutive_failures} consecutive failures, {total_errors} total errors")
            # Show top error categories
            if categories:
                top_category = max(categories.items(), key=lambda x: x[1])
                report += f"     Top error: {top_category[0]} ({top_category[1]} times)\n"

    if unhealthy_sources:
        report += "\nUnhealthy sources:\n" + "\n".join(unhealthy_sources)
    else:
        report += "✅ All sources operating normally."

    return report

def track_error(source_url: str, error_type: str, error_message: str, error_tracking: Dict = None):
    """Track an error for a source using the existing error tracking system."""
    if error_tracking is None:
        error_tracking = load_error_tracking()
    
    # Track the error using the existing function
    updated_tracking = track_source_error(source_url, error_message, error_tracking)
    save_error_tracking(updated_tracking)

def init_database(db_file: str = "news_reader.db"):
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            summary TEXT,
            category TEXT,
            source TEXT,
            timestamp TEXT,
            created_at REAL DEFAULT (datetime('now')),
            updated_at REAL DEFAULT (datetime('now'))
        )
    ''')

    # Create error_tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT UNIQUE NOT NULL,
            total_errors INTEGER DEFAULT 0,
            categories TEXT,  -- JSON string of error categories
            last_error TEXT,
            first_error TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            last_success TEXT,
            created_at REAL DEFAULT (datetime('now')),
            updated_at REAL DEFAULT (datetime('now'))
        )
    ''')

    # Create overviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS overviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,  -- YYYY-MM-DD format
            content TEXT NOT NULL,
            created_at REAL DEFAULT (datetime('now')),
            updated_at REAL DEFAULT (datetime('now'))
        )
    ''')

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_timestamp ON articles(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_error_tracking_domain ON error_tracking(domain)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_overviews_date ON overviews(date)')

    conn.commit()
    conn.close()

def migrate_json_to_sqlite():
    """Migrate data from JSON files to SQLite database."""
    print("🔄 Starting database migration...")

    # Initialize database
    init_database()

    conn = sqlite3.connect("news_reader.db")
    cursor = conn.cursor()

    # Migrate summaries.json
    if os.path.exists("summaries.json"):
        print("📄 Migrating summaries.json...")
        try:
            with open("summaries.json", "r", encoding="utf-8") as f:
                summaries_data = json.load(f)

            migrated_count = 0
            for feed_name, articles in summaries_data.items():
                for article in articles:
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO articles
                            (title, link, summary, category, source, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            article.get('title', ''),
                            article.get('link', ''),
                            article.get('summary', ''),
                            article.get('category', 'Other'),
                            feed_name,
                            article.get('timestamp', datetime.now().isoformat())
                        ))
                        migrated_count += 1
                    except Exception as e:
                        print(f"⚠️ Error migrating article: {e}")
                        continue

            print(f"✅ Migrated {migrated_count} articles")

        except Exception as e:
            print(f"⚠️ Error reading summaries.json: {e}")

    # Migrate error_tracking.json
    if os.path.exists("error_tracking.json"):
        print("📄 Migrating error_tracking.json...")
        try:
            with open("error_tracking.json", "r", encoding="utf-8") as f:
                error_data = json.load(f)

            migrated_count = 0
            for domain, data in error_data.items():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO error_tracking
                        (domain, total_errors, categories, last_error, first_error, consecutive_failures, last_success)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        domain,
                        data.get('total_errors', 0),
                        json.dumps(data.get('categories', {})),
                        data.get('last_error'),
                        data.get('first_error'),
                        data.get('consecutive_failures', 0),
                        data.get('last_success')
                    ))
                    migrated_count += 1
                except Exception as e:
                    print(f"⚠️ Error migrating error tracking for {domain}: {e}")
                    continue

            print(f"✅ Migrated {migrated_count} error tracking records")

        except Exception as e:
            print(f"⚠️ Error reading error_tracking.json: {e}")

    conn.commit()
    conn.close()

    print("✅ Database migration complete!")
    print("📝 Note: Old JSON files are kept as backup. You can delete them manually if migration is successful.")

def load_summaries_from_db(db_file: str = "news_reader.db") -> Dict:
    """Load summaries from SQLite database."""
    if not os.path.exists(db_file):
        init_database(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Group articles by source for compatibility with existing code
    summaries = {}
    cursor.execute('SELECT title, link, summary, category, source, timestamp FROM articles ORDER BY created_at DESC')

    for row in cursor.fetchall():
        title, link, summary, category, source, timestamp = row

        if source not in summaries:
            summaries[source] = []

        summaries[source].append({
            'title': title,
            'link': link,
            'summary': summary,
            'category': category,
            'timestamp': timestamp
        })

    conn.close()
    return summaries

def save_summaries_to_db(summaries: Dict, db_file: str = "news_reader.db"):
    """Save summaries to SQLite database with cleanup."""
    if not os.path.exists(db_file):
        init_database(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    current_time = datetime.now()
    cutoff_date = current_time - timedelta(days=10)

    # Insert/update articles
    for feed_name, articles in summaries.items():
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO articles
                    (title, link, summary, category, source, timestamp, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    article.get('title', ''),
                    article.get('link', ''),
                    article.get('summary', ''),
                    article.get('category', 'Other'),
                    feed_name,
                    article.get('timestamp', current_time.isoformat())
                ))
            except Exception as e:
                print(f"⚠️ Error saving article: {e}")
                continue

    # Clean up old articles (older than 10 days)
    cursor.execute('DELETE FROM articles WHERE datetime(timestamp) < datetime(?)',
                  (cutoff_date.isoformat(),))

    deleted_count = cursor.rowcount
    if deleted_count > 0:
        print(f"🧹 Cleaned up {deleted_count} old articles (older than 10 days)")

    conn.commit()
    conn.close()

def load_error_tracking_from_db(db_file: str = "news_reader.db") -> Dict:
    """Load error tracking from SQLite database."""
    if not os.path.exists(db_file):
        init_database(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    error_tracking = {}
    cursor.execute('SELECT domain, total_errors, categories, last_error, first_error, consecutive_failures, last_success FROM error_tracking')

    for row in cursor.fetchall():
        domain, total_errors, categories_json, last_error, first_error, consecutive_failures, last_success = row

        try:
            categories = json.loads(categories_json) if categories_json else {}
        except:
            categories = {}

        error_tracking[domain] = {
            'total_errors': total_errors,
            'categories': categories,
            'last_error': last_error,
            'first_error': first_error,
            'consecutive_failures': consecutive_failures,
            'last_success': last_success
        }

    conn.close()
    return error_tracking

def save_error_tracking_to_db(error_data: Dict, db_file: str = "news_reader.db"):
    """Save error tracking to SQLite database."""
    if not os.path.exists(db_file):
        init_database(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    for domain, data in error_data.items():
        cursor.execute('''
            INSERT OR REPLACE INTO error_tracking
            (domain, total_errors, categories, last_error, first_error, consecutive_failures, last_success, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            domain,
            data.get('total_errors', 0),
            json.dumps(data.get('categories', {})),
            data.get('last_error'),
            data.get('first_error'),
            data.get('consecutive_failures', 0),
            data.get('last_success')
        ))

    conn.commit()
    conn.close()

def load_settings(settings_file: str = "settings.json") -> Dict:
    """Load settings from JSON file."""
    try:
        with open(settings_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Settings file {settings_file} not found. Using defaults.")
        return {
            "ollama": {
                "host": "localhost",
                "model": "smollm2:135m",
                "overview_model": "llama2",
                "timeout": 120
            },
            "processing": {
                "max_overview_summaries": 50,
                "scrape_timeout": 30
            },
            "prompts": {
                "article_summary": "Summarize this article briefly:",
                "overview_summary": "Based on the following news summaries, provide a comprehensive overview of the current state of the world. Organize your response by major themes and regions, highlighting the most significant developments, trends, and concerns. Focus on factual information and avoid speculation.\n\nPlease structure your response as:\n1. Major Global Developments\n2. Regional Highlights (US, International, etc.)\n3. Key Trends and Concerns\n4. Notable Individual Stories\n\nKeep the overview concise but comprehensive."
            },
            "files": {
                "sources": "sources.txt",
                "summaries": "summaries.json",
                "overviews": "overviews"
            }
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing settings file: {e}. Using defaults.")
        return {
            "ollama": {
                "host": "localhost",
                "model": "smollm2:135m",
                "overview_model": "llama2",
                "timeout": 120
            },
            "prompts": {
                "article_summary": "Summarize this article briefly:",
                "overview_summary": "Based on the following news summaries, provide a comprehensive overview of the current state of the world..."
            },
            "files": {
                "sources": "sources.txt",
                "summaries": "summaries.json",
                "overviews": "overviews"
            }
        }

def detect_source_type(url: str) -> str:
    """
    Detect whether a URL is an RSS feed or a website to scrape.

    Returns:
        "rss" for RSS feeds, "website" for websites to scrape
    """
    # Common RSS feed indicators
    rss_indicators = [
        '/feed', '/rss', 'feeds/videos.xml', '.xml', '.rss',
        'feed.xml', 'rss.xml', 'atom.xml'
    ]

    url_lower = url.lower()
    if any(indicator in url_lower for indicator in rss_indicators):
        return "rss"

    # If it doesn't match RSS patterns, assume it's a website to scrape
    return "website"


# Legacy function for backward compatibility
def summarize_text(text: str, prompt: str = "Summarize this article briefly:",
                  summarizer: Optional[Summarizer] = None) -> str:
    """
    Summarize text content (backward compatibility function).

    This function now uses the new summarizer architecture.
    For new code, use the Summarizer classes directly.

    Args:
        text: Text to summarize
        prompt: Summarization prompt
        summarizer: Summarizer instance to use (creates default if None)

    Returns:
        Summarized text or error message
    """
    if summarizer is None:
        # Create default summarizer for backward compatibility
        config = NewsReaderConfig()
        summarizer_config = config.get_summarizer_config()
        summarizer = SummarizerFactory.create_summarizer(summarizer_config)

    result = summarizer.summarize(text, prompt)
    return result.content if result.success else f"[Error: {result.error}]"

def load_summaries(file_path: str) -> Dict:
    """
    Load article summaries from a JSON file.

    Args:
        file_path: Path to the JSON file containing summaries

    Returns:
        Dictionary of summaries grouped by feed name, or empty dict if file not found/invalid
    """
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_summaries(file_path: str, data: dict):
    """Save summaries with timestamps and cleanup old entries."""
    try:
        # Add timestamp to new entries and clean up old ones
        current_time = datetime.now()
        cutoff_date = current_time - timedelta(days=10)

        cleaned_data = {}

        for feed_name, articles in data.items():
            cleaned_articles = []
            for article in articles:
                # Add timestamp if not present
                if 'timestamp' not in article:
                    article['timestamp'] = current_time.isoformat()

                # Parse timestamp and check if it's within cutoff
                try:
                    article_date = datetime.fromisoformat(article['timestamp'])
                    if article_date >= cutoff_date:
                        cleaned_articles.append(article)
                except (ValueError, TypeError):
                    # If timestamp is invalid, keep the article but add current timestamp
                    article['timestamp'] = current_time.isoformat()
                    cleaned_articles.append(article)

            if cleaned_articles:  # Only keep feeds that have articles
                cleaned_data[feed_name] = cleaned_articles

        with open(file_path, "w") as f:
            json.dump(cleaned_data, f, indent=2)

        # Report cleanup
        original_count = sum(len(articles) for articles in data.values())
        cleaned_count = sum(len(articles) for articles in cleaned_data.values())
        if original_count > cleaned_count:
            print(f"🧹 Cleaned up {original_count - cleaned_count} old summaries (older than 10 days)")

    except Exception as e:
        print(f"[Error saving summaries: {e}]")

def summarize_rss_feed(rss_url: str, summarizer: Summarizer, summaries: Dict, content_extractor: ContentExtractor, prompt: str, timeout: int = 120, output_channels: Optional[List[Any]] = None):
    """
    Process an RSS feed, extract articles, and generate summaries.

    Fetches RSS feed entries, checks for new content, extracts full article content
    if RSS summaries are insufficient, summarizes using provided summarizer, and categorizes articles.

    Args:
        rss_url: URL of the RSS feed to process
        summarizer: Summarizer instance to use for text summarization
        summaries: Dictionary to store processed summaries
        content_extractor: Content extractor for fetching full article content
        prompt: Summarization prompt
        timeout: Request timeout in seconds
        output_channels: List of output channels to send summaries to
    """
    error_tracking = load_error_tracking()

    try:
        print(f"📡 Processing RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)

        # Check for network/parsing errors
        if feed.bozo:  # Check if there was a parsing error
            error_msg = f"RSS parsing error for {rss_url}: {feed.bozo_exception}"
            print(f"❌ {error_msg}")
            # Track the error
            track_error(rss_url, "rss_parsing", str(feed.bozo_exception))
            return

        if hasattr(feed, 'status') and feed.status >= 400:
            error_msg = f"HTTP error {feed.status} for {rss_url}"
            print(f"❌ {error_msg}")
            track_error(rss_url, "http_error", f"Status: {feed.status}")
            return

        feed_title = feed.feed.get('title', rss_url)
        print(f"📡 Feed: {feed_title}")
        print(f"Found {len(feed.entries)} entries")

        if len(feed.entries) == 0:
            print(f"⚠️ No entries found in RSS feed {rss_url} - feed might be empty or unreachable")
            track_error(rss_url, "empty_feed", "No entries found")
            return

    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout fetching RSS feed {rss_url} (30s timeout)"
        print(f"❌ {error_msg}")
        track_error(rss_url, "timeout", str(e))
        return
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error fetching RSS feed {rss_url} - network unreachable"
        print(f"❌ {error_msg}")
        track_error(rss_url, "connection_error", str(e))
        return
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error fetching RSS feed {rss_url}: {e}"
        print(f"❌ {error_msg}")
        track_error(rss_url, "network_error", str(e))
        return
    except Exception as e:
        error_msg = f"Unexpected error processing RSS feed {rss_url}: {e}"
        print(f"❌ {error_msg}")
        track_error(rss_url, "unexpected_error", str(e))
        return

        # Initialize feed entry in summaries if not exists
        if feed_title not in summaries:
            summaries[feed_title] = []

        # Build set of already processed article links to avoid duplicates
        known_links = {entry["link"] for entry in summaries[feed_title] if "link" in entry}

        for entry in feed.entries:
            link = entry.get("link")
            title = entry.get("title", "Untitled")

            if not link:
                print(f"Skipping entry with no link: {title}")
                continue

            if link in known_links:
                print(f"⏩ Skipping already summarized: {title}")
                continue

            print(f"🔹 Summarizing: {title}")

            # Get initial content from RSS feed (summary or description field)
            summary_input = str(entry.get("summary", entry.get("description", "")))

            # Enhance content if RSS summary is too short (< 100 chars)
            # This ensures we have sufficient content for meaningful summarization
            if not summary_input or len(summary_input.strip()) < 100:
                if link:
                    print(f"📖 RSS content insufficient, fetching full article...")
                    print(f"   Article URL: {link}")
                    full_content = get_full_article_content(str(link), timeout)
                    if not full_content.startswith("[Error") and not full_content.startswith("[Could not"):
                        summary_input = full_content
                        print(f"✅ Retrieved full article content ({len(summary_input)} chars)")
                    else:
                        print(f"⚠️ Could not retrieve full content: {full_content[:100]}...")

            if not summary_input:
                print("No content to summarize.\n")
                continue

            # Summarize the content
            summary_result = summarizer.summarize(summary_input, prompt)

            # Check if summarization was successful
            if not summary_result.success:
                print(f"❌ Summarization failed: {summary_result.error}")
                print("⏭️ Skipping article - not marking as complete\n")
                continue

            summary = summary_result.content

            # Extract category from the summary
            category = extract_category_from_summary(summary)
            print(f"🏷️ Category: {category}")
            print(f"Summary: {summary}\n")

            # Send summary to configured output channels
            if output_channels:
                for channel in output_channels:
                    try:
                        result = channel.send_summary(title, summary, rss_url, category)
                        if result.success:
                            print(f"✅ Sent to {type(channel).__name__}: {result.message}")
                        else:
                            print(f"❌ Failed to send to {type(channel).__name__}: {result.error}")
                    except Exception as e:
                        print(f"❌ Error sending to {type(channel).__name__}: {e}")

            summaries[feed_title].append({
                "title": title,
                "link": link,
                "summary": summary,
                "category": category
            })

        save_summaries_to_db(summaries, "news_reader.db")  # Save progress incrementally

        # Track successful processing
        track_source_success(rss_url, error_tracking)
        save_error_tracking_to_db(error_tracking)

    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ Error processing RSS feed {rss_url}: {error_msg}")
        track_source_error(rss_url, error_msg, error_tracking)
        save_error_tracking_to_db(error_tracking)

def read_urls_from_file(filepath: str) -> List[str]:
    """Read URLs from file, supporting flat format, grouped format, and JSON format."""
    try:
        print(f"📖 Reading sources from: {filepath}")
        with open(filepath, "r") as f:
            content = f.read()
        
        print(f"📄 File content preview (first 200 chars): {content[:200]}...")

        # Try to parse as JSON first
        try:
            data = json.loads(content)
            if "groups" in data:
                print(f"🔍 Detected JSON format with groups")
                return _parse_json_sources(data, filepath)
            print(f"🔍 Detected JSON format without groups")
        except json.JSONDecodeError:
            print(f"🔍 Not JSON format, trying text parsing...")
            pass  # Not JSON, continue with text parsing

        # Check if file uses grouped format (has section headers)
        if '[' in content and ']' in content:
            return _parse_grouped_sources(content, filepath)
        else:
            return _parse_flat_sources(content, filepath)

    except FileNotFoundError:
        print(f"⚠️ Sources file not found: {filepath}")
        print("Creating default sources file...")
        return _create_default_sources_file(filepath)


def _parse_json_sources(data: Dict, filepath: str) -> List[str]:
    """Parse JSON sources file format and flatten to URLs."""
    urls = []
    groups = data.get("groups", {})

    for group_name, group_data in groups.items():
        group_urls = group_data.get("sources", [])
        urls.extend(group_urls)

    print(f"📄 Loaded {len(urls)} URLs from {filepath} (JSON format):")
    for group_name, group_data in groups.items():
        group_urls = group_data.get("sources", [])
        print(f"   📁 {group_name}: {len(group_urls)} sources")
        for i, url in enumerate(group_urls[:2]):  # Show first 2 per group
            print(f"      {i+1}. {url}")
        if len(group_urls) > 2:
            print(f"      ... and {len(group_urls) - 2} more")

    return urls


def _parse_flat_sources(content: str, filepath: str) -> List[str]:
    """Parse traditional flat sources file format."""
    urls = []
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)

    print(f"📄 Loaded {len(urls)} URLs from {filepath} (flat format):")
    for i, url in enumerate(urls[:3]):  # Show first 3
        print(f"   {i}. {url}")
    if len(urls) > 3:
        print(f"   ... and {len(urls) - 3} more")
    return urls


def _parse_grouped_sources(content: str, filepath: str) -> List[str]:
    """Parse grouped sources format with support for multiple output channel mapping.
    
    Format: [group-name] or [group-name:output1,output2] or [group-name:output1,output2:custom-prompt]
    Examples:
        [tech-news]                          # Goes to all outputs
        [urgent-news:discord,telegram]         # Goes to Discord and Telegram outputs
        [finance:bloomberg-bot,email-digest]   # Goes to specific named outputs
        [sports:discord-webhook: Sports only summary]  # Custom prompt
    """
    urls = []
    current_group = None
    current_outputs = []
    current_prompt = None
    
    for line in content.split('\n'):
        line = line.strip()
        
        if not line or line.startswith('#'):
            continue
            
        # Check for group header
        if line.startswith('[') and line.endswith(']'):
            header_content = line[1:-1].strip()
            parts = header_content.split(':')
            
            current_group = parts[0].strip()
            
            if len(parts) >= 2:
                # Parse output channels
                output_names = parts[1].strip().split(',')
                current_outputs = [out.strip() for out in output_names if out.strip()]
                
                # Check for custom prompt
                if len(parts) >= 3:
                    current_prompt = parts[2].strip()
                else:
                    current_prompt = None
            else:
                # No outputs specified = send to all
                current_outputs = []
                current_prompt = None
            
            print(f"   📝 Group: {current_group}")
            if current_outputs:
                print(f"   📤 Outputs: {', '.join(current_outputs)}")
            else:
                print(f"   📤 Outputs: all configured outputs")
            if current_prompt:
                print(f"   📝 Custom prompt: {current_prompt[:50]}...")
            continue
            
        # Check if it's a URL
        if line.startswith(('http://', 'https://')):
            urls.append((line.strip(), current_group, current_outputs, current_prompt))
    
    print(f"📄 Loaded {len(urls)} URLs from {filepath} (grouped format):")
    for url, group, outputs, prompt in urls[:3]:  # Show first 3 examples
        output_str = ', '.join(outputs) if outputs else 'all'
        print(f"   📁 {group} → {output_str}: {url}")
    if len(urls) > 3:
        print(f"   ... and {len(urls) - 3} more")
    
    return urls


def _create_default_sources_file(filepath: str) -> List[str]:
    """Create default sources file and return URLs."""
    default_content = """# News Sources Configuration
# You can organize sources into groups that send to different output channels
# Format: [group-name] or [group-name:channel1,channel2:custom prompt]

[telegram-news]
# General news sources for Telegram (default prompt)
https://feeds.bbci.co.uk/news/rss.xml
https://rss.cnn.com/rss/edition.rss
https://feeds.npr.org/1001/rss.xml

[discord-tech:discord:Summarize this technology article, focusing on innovations, technical details, and industry impact]
# Technology news for Discord with custom tech-focused prompt
https://feeds.feedburner.com/TechCrunch/
https://www.reddit.com/r/technology/.rss

[all-channels]
# Sources that go to all configured channels (default prompt)
# https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
"""

    with open(filepath, "w") as f:
        f.write(default_content)

    print(f"✅ Created default sources file with grouped format: {filepath}")

    # Return URLs from default content
    return _parse_grouped_sources(default_content, filepath)

def generate_world_overview(summarizer: Summarizer, summaries: Dict, prompt: str, max_summaries: int = 50) -> str:
    """
    Generate a consolidated overview of the current state of the world from all summaries.

    Args:
        summarizer: Summarizer instance to use for overview generation
        summaries: Dictionary of all summaries
        prompt: Overview generation prompt
        max_summaries: Maximum number of summaries to include (to avoid token limits)

    Returns:
        Consolidated overview summary
    """
    # Collect all valid summaries and group them by category
    # Skip articles with error summaries to ensure overview quality
    categorized_summaries = {}
    for feed_name, articles in summaries.items():
        for article in articles:
            summary = article.get('summary', '')
            category = article.get('category', 'Other')
            # Only include articles with valid summaries (not error messages)
            if summary and not summary.startswith('[Error'):
                if category not in categorized_summaries:
                    categorized_summaries[category] = []

                categorized_summaries[category].append({
                    'feed': feed_name,
                    'title': article.get('title', ''),
                    'summary': summary,
                    'category': category
                })

    if not categorized_summaries:
        return "No valid summaries found to generate overview."

    # Limit summaries per category to avoid exceeding LLM token limits
    # Ensure at least 2 articles per category for balanced coverage
    limited_summaries = {}
    total_count = 0
    max_per_category = max(2, max_summaries // len(categorized_summaries)) if categorized_summaries else max_summaries

    for category, articles in categorized_summaries.items():
        limited_summaries[category] = articles[:max_per_category]
        total_count += len(limited_summaries[category])

    # Create consolidated text organized by categories
    overview_text = "Here are recent news summaries organized by category:\n\n"

    for category, articles in limited_summaries.items():
        overview_text += f"**{category}**\n"
        for i, item in enumerate(articles, 1):
            overview_text += f"{i}. {item['title']} ({item['feed']}): {item['summary']}\n"
        overview_text += "\n"

    # Use the custom overview prompt
    full_prompt = f"{prompt}\n\n{overview_text}"

    try:
        result = summarizer.summarize("", full_prompt)  # Empty text since prompt contains all content
        return result.content if result.success else f"[Error generating overview: {result.error}]"

    except Exception as e:
        return f"[Error generating overview: {e}]"

def save_overview_to_db(overview_text: str, db_file: str = "news_reader.db"):
    """Save overview to SQLite database, keeping overviews for 40 days."""
    try:
        init_database(db_file)
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        current_time = datetime.now()
        date_str = current_time.strftime("%Y-%m-%d")

        # Insert or replace today's overview
        cursor.execute('''
            INSERT OR REPLACE INTO overviews (date, content, updated_at)
            VALUES (?, ?, datetime('now'))
        ''', (date_str, overview_text))

        # Clean up overviews older than 40 days
        cutoff_date = (current_time - timedelta(days=40)).strftime("%Y-%m-%d")
        cursor.execute('DELETE FROM overviews WHERE date < ?', (cutoff_date,))

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old overviews (older than 40 days)")

        conn.commit()
        conn.close()

        print(f"📝 Saved daily overview for {date_str}")
        return f"Database: {date_str}"

    except Exception as e:
        print(f"[Error saving overview to database: {e}]")
        return None

def save_overview_to_file(overview_text: str, overview_file: str = "daily_overview.txt"):
    """Save overview to a single file (overwrites previous content)."""
    try:
        current_time = datetime.now()

        with open(overview_file, "w", encoding="utf-8") as f:
            f.write(f"Daily News Overview\n")
            f.write(f"Generated: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")
            f.write(overview_text)

        print(f"📝 Saved overview to: {overview_file}")
        return overview_file

    except Exception as e:
        print(f"[Error saving overview to file: {e}]")
        return None

def save_overview(overview_text: str, use_database: bool = True):
    """Save overview using the configured method."""
    if use_database:
        # Save to database (keeps only latest)
        return save_overview_to_db(overview_text)
    else:
        # Save to file (overwrites daily)
        return save_overview_to_file(overview_text)

def load_latest_overview(db_file: str = "news_reader.db") -> Optional[str]:
    """Load the latest overview from database."""
    try:
        if not os.path.exists(db_file):
            return None

        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute('SELECT content, date FROM overviews ORDER BY date DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()

        if row:
            content, date = row
            return content
        return None

    except Exception as e:
        print(f"[Error loading overview: {e}]")
        return None

def export_overview_for_home_assistant(output_file: str = "daily_news_overview.txt", db_file: str = "news_reader.db"):
    """Export the latest overview in a format suitable for Home Assistant TTS."""
    try:
        overview_content = load_latest_overview(db_file)
        if not overview_content:
            overview_content = "No news overview available today."

        # Format for Home Assistant TTS
        formatted_content = f"Good morning. Here's your daily news briefing.\n\n{overview_content}"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(formatted_content)

        print(f"📤 Exported overview for Home Assistant to: {output_file}")
        return output_file

    except Exception as e:
        print(f"[Error exporting overview: {e}]")
        return None

def cleanup_old_overviews(overview_dir: str, max_age_days: int = 40):
    """Delete overview files older than specified days."""
    try:
        current_time = datetime.now()
        cutoff_date = current_time - timedelta(days=max_age_days)

        cleaned_count = 0
        for filename in os.listdir(overview_dir):
            if filename.startswith("overview_") and filename.endswith(".txt"):
                try:
                    # Extract date from filename (overview_YYYY-MM-DD_HH-MM-SS.txt)
                    date_part = filename.split("_")[1]  # YYYY-MM-DD
                    file_date = datetime.strptime(date_part, "%Y-%m-%d")

                    if file_date < cutoff_date:
                        filepath = os.path.join(overview_dir, filename)
                        os.remove(filepath)
                        cleaned_count += 1
                except (ValueError, IndexError):
                    continue

        if cleaned_count > 0:
            print(f"🧹 Cleaned up {cleaned_count} old overviews (older than {max_age_days} days)")

    except Exception as e:
        print(f"[Error cleaning up overviews: {e}]")

def is_listing_page(url: str, soup: BeautifulSoup) -> bool:
    """
    Determine if a page is a listing/index page that contains article links.

    Args:
        url: The page URL
        soup: Parsed HTML content

    Returns:
        True if this appears to be a listing page
    """
    url_path = urlparse(url).path.lower()

    # Check URL patterns for listing pages
    if url_path == '/' or url_path == '':
        return True  # homepage

    listing_patterns = [
        '/seccion/',  # section pages
        '/categoria/',  # category pages
        '/tag/',  # tag pages
        '/page/',  # pagination
    ]

    if any(pattern in url_path for pattern in listing_patterns):
        return True

    # For diario.mx specifically, check if URL follows article pattern
    # Article URLs: /section/YYYY/MMM/DD/slug-ID.html
    path_parts = url_path.strip('/').split('/')
    if len(path_parts) >= 5:
        try:
            section = path_parts[0]
            year = path_parts[1]
            month = path_parts[2]
            day = path_parts[3]

            # If this looks like an article URL, it's NOT a listing page
            valid_month = month.isdigit() or month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
            if (year.isdigit() and len(year) == 4 and
                valid_month and
                day.isdigit() and len(day) == 2 and
                url.endswith('.html')):
                return False  # This is an article, not a listing
        except (ValueError, IndexError):
            pass

    # Check content patterns - listing pages typically have multiple article links
    # But be more sophisticated: if there's substantial text content, it's likely an article
    text_content = soup.get_text()
    total_text_length = len(text_content.strip())

    # If there's a lot of text content, it's probably an article, not a listing
    if total_text_length > 2000:
        return False

    article_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href and any(pattern in href for pattern in ['/20', '/noticia', '/news', '/article']):
            if href.startswith('http') or href.startswith('/'):
                article_links.append(href)

    # Only consider it a listing if there are many article links AND little text content
    return len(article_links) >= 5 and total_text_length < 1000

def extract_article_links(url: str, soup: BeautifulSoup, max_links: int = 10) -> list[str]:
    """
    Extract article links from a listing page.

    Args:
        url: Base URL
        soup: Parsed HTML content
        max_links: Maximum number of links to extract

    Returns:
        List of full article URLs
    """
    article_links = []
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    # If we're on the homepage, look for section links first
    url_path = urlparse(url).path
    if url_path in ['/', '']:
        print("🏠 On homepage, looking for section links...")
        section_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href and '/seccion/' in href:
                if href.startswith('/'):
                    full_url = f"{base_url}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                if full_url not in section_links:
                    section_links.append(full_url)

        # Try to fetch articles from the first section (juarez)
        juarez_section = None
        for link in section_links:
            if 'juarez' in link:
                juarez_section = link
                break

        if juarez_section:
            print(f"📂 Following section: {juarez_section}")
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(juarez_section, headers=headers, timeout=30)
                soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')
                print("✅ Loaded section page")
            except Exception as e:
                print(f"⚠️ Failed to load section: {e}")
                return []

    # Now extract article links from the page (homepage or section)
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue

        # Convert relative URLs to absolute
        if href.startswith('/'):
            full_url = f"{base_url}{href}"
        elif href.startswith('http'):
            full_url = href
        else:
            continue

        # Check if URL matches article pattern for diario.mx
        # Pattern: /section/YYYY/MM/DD/slug-ID.html
        parsed = urlparse(full_url)
        path_parts = parsed.path.strip('/').split('/')

        # Must have at least 5 path components: section/year/month/day/slug
        if len(path_parts) >= 5:
            try:
                section = path_parts[0]
                year = path_parts[1]
                month = path_parts[2]
                day = path_parts[3]

                # Validate URL components follow expected article pattern
                # Supports both numeric months (01-12) and abbreviated months (jan-dec)
                valid_month = False
                if month.isdigit() and len(month) == 2 and 1 <= int(month) <= 12:
                    valid_month = True  # Numeric month like "01"
                elif month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']:
                    valid_month = True  # Abbreviated month like "dec"

                # Validate all components: year >= 2020, valid month/day, not section/page links, .html extension
                if (year.isdigit() and len(year) == 4 and int(year) >= 2020 and
                    valid_month and
                    day.isdigit() and len(day) == 2 and 1 <= int(day) <= 31 and
                    not section.startswith('seccion') and  # exclude section navigation links
                    not section.startswith('pages') and    # exclude pagination links
                    full_url.endswith('.html')):
                    # Add unique article URL to results
                    if full_url not in article_links:
                        article_links.append(full_url)
                        if len(article_links) >= max_links:
                            break
            except (ValueError, IndexError):
                # Skip malformed URLs
                continue

    return article_links

def scrape_article_content(url: str, timeout: int = 30) -> tuple[str, str]:
    """
    Scrape article content from a website URL.
    If it's a listing page, extract and summarize individual articles.

    Args:
        url: The website URL to scrape

    Returns:
        Tuple of (title, content) extracted from the page
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')

        # Check if this is a listing page
        if is_listing_page(url, soup):
            # Extract article links and process the first few
            article_links = extract_article_links(url, soup, max_links=5)

            if article_links:
                print(f"📄 Found {len(article_links)} articles on listing page, processing first article...")
                # Process the first article instead of the listing page
                return scrape_article_content(article_links[0], timeout)

        # Extract title
        title = ""
        title_candidates = [
            soup.find('title'),
            soup.find('h1'),
            soup.find('meta', attrs={'property': 'og:title'}),
            soup.find('meta', attrs={'name': 'title'})
        ]

        for candidate in title_candidates:
            if candidate:
                title = candidate.get('content') or candidate.get_text().strip()
                if title:
                    break

        if not title:
            title = urlparse(url).netloc

        # Extract main content
        content = extract_main_content(soup)

        return title, content

    except Exception as e:
        return f"Error scraping {url}", f"[Error scraping content: {e}]"

def extract_youtube_transcript(video_url: str) -> str:
    """Extract transcript from YouTube video URL."""
    if not YOUTUBE_TRANSCRIPTS_AVAILABLE:
        return "[YouTube transcript extraction not available - install youtube-transcript-api]"

    try:
        # Extract video ID from URL
        video_id = None
        if 'youtube.com/watch?v=' in video_url:
            video_id = video_url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in video_url:
            video_id = video_url.split('youtu.be/')[1].split('?')[0]

        if not video_id:
            return "[Could not extract YouTube video ID]"

        # Get transcript using the correct API
        transcript_api = YouTubeTranscriptApi()
        transcript = transcript_api.fetch(video_id)

        # Combine transcript text
        transcript_text = ""
        for entry in transcript:
            transcript_text += entry.text + " "

        # Clean up the text
        transcript_text = ' '.join(transcript_text.split())
        return transcript_text if transcript_text else "[Empty transcript]"

    except Exception as e:
        return f"[Error extracting YouTube transcript: {e}]"

# Legacy function for backward compatibility
def get_full_article_content(url: str, timeout: int = 30) -> str:
    """
    Get full article content (backward compatibility function).

    This function now uses the new content extraction architecture.
    For new code, use ContentExtractor directly.

    Args:
        url: Article URL
        timeout: Request timeout

    Returns:
        Full article content or error message
    """
    config = NewsReaderConfig()
    extractor = ContentExtractor(config)
    return extractor.extract_from_url(url, timeout)

def extract_main_content(soup: BeautifulSoup) -> str:
    """
    Extract the main article content from a BeautifulSoup object.

    Args:
        soup: Parsed HTML content

    Returns:
        Extracted article text
    """
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
        script.decompose()

    # Try common article content selectors
    content_selectors = [
        'article',
        '[class*="article"]',
        '[class*="content"]',
        '[class*="post"]',
        '[class*="entry"]',
        'main',
        '.main-content',
        '#main-content',
        '.article-content',
        '.post-content'
    ]

    content_text = ""

    # Try to find main content area
    for selector in content_selectors:
        content_area = soup.select_one(selector)
        if content_area:
            content_text = content_area.get_text(separator=' ', strip=True)
            if len(content_text) > 200:  # Minimum content length
                break

    # Fallback: get all paragraph text
    if not content_text or len(content_text) < 200:
        paragraphs = soup.find_all('p')
        content_text = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Clean up the text
    content_text = ' '.join(content_text.split())  # Normalize whitespace

    # Limit content length for summarization
    if len(content_text) > 5000:
        content_text = content_text[:5000] + "..."

    return content_text or "[No readable content found]"

def process_website(url: str, summarizer: Summarizer, content_extractor: ContentExtractor, summaries: Dict, output_channels: List[Any], prompt: str, timeout: int = 120):
    """Process a website URL by scraping content and summarizing articles."""
    print(f"\n🌐 Scraping: {url}")

    error_tracking = load_error_tracking()
    processing_error = None

    try:
        # Check if this is a YouTube video URL
        def _is_youtube_video_url(url: str) -> bool:
            if 'youtu.be/' in url:
                return True
            if 'youtube.com/watch?v=' in url:
                return True
            if 'youtube.com/embed/' in url:
                return True
            if 'youtube.com/shorts/' in url:
                return True
            return False

        if _is_youtube_video_url(url):
            print("🎥 Detected YouTube video, extracting transcript...")
            transcript = extract_youtube_transcript(url)
            if transcript and not (transcript.startswith('[Error') or
                                 transcript.startswith('[Could not') or
                                 transcript.startswith('[Invalid') or
                                 transcript.startswith('[YouTube')):
                # Get video title from transcript API or scrape page
                title = extract_youtube_title(url, timeout)
                print(f"📺 Title: {title}")
                print("🔹 Summarizing transcript...")
                process_single_article(url, title, transcript, summarizer, summaries, output_channels, prompt, timeout)
                track_source_success(url, error_tracking)
                save_error_tracking_to_db(error_tracking)
                return
            else:
                processing_error = f"Could not extract transcript: {transcript}"
                print(f"⚠️ {processing_error}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')

        # Check if this is a listing page
        if is_listing_page(url, soup):
            # Extract article links and process each one
            article_links = extract_article_links(url, soup, max_links=5)
            print(f"📄 Found {len(article_links)} articles on listing page")

            if not article_links:
                print("No article links found, treating as regular page")
                # Fall back to treating as regular article
                title, content = scrape_article_content(url, timeout)
                if content and not content.startswith("[Error"):
                    process_single_article(url, title, content, summarizer, summaries, output_channels, prompt, timeout)
                    track_source_success(url, error_tracking)
                else:
                    processing_error = "No article links found and failed to extract content"
                return

            # Process each article
            articles_processed = 0
            for article_url in article_links:
                try:
                    print(f"🔗 Processing article: {article_url}")
                    title, content = scrape_article_content(article_url, timeout)

                    if content and not content.startswith("[Error"):
                        process_single_article(article_url, title, content, summarizer, summaries, output_channels, prompt, timeout)
                        articles_processed += 1
                    else:
                        print(f"⚠️ Failed to extract content from {article_url}")

                except Exception as e:
                    print(f"⚠️ Error processing article {article_url}: {e}")
                    continue

            print(f"✅ Processed {articles_processed} articles from {url}")
            if articles_processed > 0:
                track_source_success(url, error_tracking)
            else:
                processing_error = f"No articles could be processed from {len(article_links)} links"

        else:
            # Single article page - try to get full content
            content = get_full_article_content(url, timeout)
            if content and not content.startswith("[Error"):
                title, _ = scrape_article_content(url, timeout)  # Get title from scraping
                print(f"📄 Title: {title}")
                print("🔹 Summarizing content...")
                process_single_article(url, title, content, summarizer, summaries, output_channels, prompt, timeout)
                track_source_success(url, error_tracking)
            else:
                processing_error = f"Failed to extract content from {url}"

    except Exception as e:
        processing_error = str(e)
        print(f"⚠️ Error processing website {url}: {processing_error}")

    # Track error if processing failed
    if processing_error:
        track_source_error(url, processing_error, error_tracking)

    save_error_tracking(error_tracking)

def extract_youtube_title(video_url: str, timeout: int = 30) -> str:
    """Extract title from YouTube video page."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(video_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            # Remove " - YouTube" suffix if present
            if title.endswith(' - YouTube'):
                title = title[:-9].strip()
            return title

        return "YouTube Video"
    except Exception as e:
        return f"YouTube Video (Error getting title: {e})"

def extract_category_from_summary(summary_text: str) -> str:
    """Extract category from a formatted summary response."""
    if "CATEGORY:" in summary_text:
        # Extract category from the formatted response
        category_line = [line for line in summary_text.split('\n') if line.startswith("CATEGORY:")]
        if category_line:
            category = category_line[0].replace("CATEGORY:", "").strip()
            return category

    # Fallback: try to detect category from content
    summary_lower = summary_text.lower()
    category_keywords = {
        "Politics": ["politics", "government", "election", "president", "policy", "political"],
        "Business/Economy": ["business", "economy", "market", "stock", "finance", "economic", "company", "industry"],
        "Technology": ["technology", "tech", "software", "ai", "digital", "internet", "computer", "app"],
        "Science/Health": ["science", "health", "medical", "research", "study", "disease", "treatment", "vaccine"],
        "Sports": ["sports", "game", "team", "player", "match", "tournament", "athlete"],
        "Entertainment": ["entertainment", "movie", "music", "celebrity", "film", "actor", "show"],
        "Crime/Law": ["crime", "law", "police", "court", "arrest", "legal", "criminal"],
        "International": ["international", "global", "world", "foreign", "diplomatic"],
        "US News": ["america", "united states", "us ", "national"],
        "Environment": ["environment", "climate", "weather", "natural", "disaster"],
        "Education": ["education", "school", "university", "student", "learning"],
    }

    for category, keywords in category_keywords.items():
        if any(keyword in summary_lower for keyword in keywords):
            return category

    return "Other"

def process_single_article(url: str, title: str, content: str, summarizer: Summarizer, summaries: Dict, output_channels: List[Any], prompt: str, timeout: int = 120):
    """Process and summarize a single article."""
    print(f"📄 Title: {title}")
    print("🔹 Summarizing content...")

    summary_result = summarizer.summarize(content, prompt)

    # Check if summarization was successful
    if not summary_result.success:
        print(f"❌ Summarization failed: {summary_result.error}")
        print(f"   Article title: {title}")
        print(f"   Content length: {len(content)} chars")
        print("⏭️ Skipping article - not marking as complete\n")
        return

    summary = summary_result.content

    # Extract category from the summary
    category = extract_category_from_summary(summary)
    print(f"🏷️ Category: {category}")
    print(f"Summary: {summary}\n")

    # Use domain as feed title for websites
    domain = urlparse(url).netloc
    feed_title = f"Website: {domain}"

    if feed_title not in summaries:
        summaries[feed_title] = []

    # Check if this URL was already processed
    known_links = {entry.get("link") for entry in summaries[feed_title] if "link" in entry}
    if url in known_links:
        print(f"⏩ Skipping already summarized: {title}")
        return

    # Send summary to configured output channels
    for channel in output_channels:
        try:
            result = channel.send_summary(title, summary, domain, category)
            if result.success:
                print(f"✅ Sent to {type(channel).__name__}: {result.message}")
            else:
                print(f"❌ Failed to send to {type(channel).__name__}: {result.error}")
        except Exception as e:
            print(f"❌ Error sending to {type(channel).__name__}: {e}")

    # Save the successfully summarized article
    summaries[feed_title].append({
        "title": title,
        "link": url,
        "summary": summary,
        "category": category
    })

    save_summaries_to_db(summaries, "news_reader.db")

if __name__ == "__main__":
    # Parse arguments first to get workdir
    parser = argparse.ArgumentParser(description="Summarize RSS feeds or scrape websites using a remote Ollama model.")
    parser.add_argument("--workdir", default=os.getcwd(), help="Working directory for config files")
    args, remaining = parser.parse_known_args()

    # Change to working directory
    workdir = args.workdir
    os.chdir(workdir)

    print(f"📁 Working directory: {workdir}")

    # Load settings and initialize new architecture components
    config = NewsReaderConfig("settings.json")
    settings = config.settings  # Keep backward compatibility

    # Initialize new architecture components
    summarizer_config = config.get_summarizer_config()
    summarizer = SummarizerFactory.create_summarizer(summarizer_config)
    content_extractor = ContentExtractor(config)
    data_manager = DataManager(config)
    output_channels = config.get_output_channels()

    # Debug: Show loaded settings
    print(f"⚙️  Loaded settings from: {config.settings_file}")
    print(f"📋 Available output channels: {[type(ch).__name__ for ch in output_channels]}")

    files_section = settings.get('files', {})
    sources_file = files_section.get('sources', 'sources.txt')
    print(f"📁 Sources file from settings: {sources_file}")
    ollama_config = settings.get('summarizer', {}).get('config', {})
    print(f"🤖 Ollama host: {ollama_config.get('host', 'localhost')}")
    print(f"🧠 Ollama model: {ollama_config.get('model', 'smollm2:135m')}")

    # Now parse the full arguments
    default_sources_file = settings.get("files", {}).get("sources", "sources.txt")
    default_summaries_file = settings.get("files", {}).get("summaries", "summaries.json")
    default_model = settings.get('summarizer', {}).get('config', {}).get('model', 'smollm2:135m')
    default_host = settings.get('summarizer', {}).get('config', {}).get('host', 'http://localhost:11434')
    default_timeout = settings.get('summarizer', {}).get('config', {}).get('timeout', 120)
    overview_model_default = settings.get('summarizer', {}).get('config', {}).get('overview_model', default_model)

    parser = argparse.ArgumentParser(description="Summarize RSS feeds or scrape websites using a remote Ollama model.")
    parser.add_argument("--url", "-u", help="Single RSS feed URL or website URL")
    parser.add_argument("--file", "-f", default=default_sources_file, help=f"File containing mixed source URLs (default: {default_sources_file})")
    parser.add_argument("--scrape", "-s", action="store_true", help="Force all URLs to be treated as websites to scrape")
    parser.add_argument("--overview", action="store_true", help="Generate a consolidated overview of all summaries (state of the world)")
    parser.add_argument("--migrate", action="store_true", help="Migrate data from JSON files to SQLite database")
    parser.add_argument("--export-overview", action="store_true", help="Export latest overview to file for Home Assistant TTS")
    parser.add_argument("--model", "-m", default=default_model, help=f"Model name on Ollama host (default: {default_model})")
    parser.add_argument("--overview-model", default=overview_model_default, help=f"Model for overview generation (default: {overview_model_default})")
    parser.add_argument("--host", "-H", default=default_host, help=f"Ollama host IP or hostname (default: {default_host})")
    parser.add_argument("--timeout", "-t", type=int, default=default_timeout, help=f"Timeout for requests (default: {default_timeout})")
    parser.add_argument("--output", "-o", default=default_summaries_file, help=f"Path to output file (default: {default_summaries_file})")
    parser.add_argument("--article-prompt", default=settings.get("prompts", {}).get("article_summary", "Summarize this article briefly:"), help="Custom prompt for article summarization")
    parser.add_argument("--overview-prompt", default=settings.get("prompts", {}).get("overview_summary", "Based on the following news summaries, provide a comprehensive overview..."), help="Custom prompt for overview generation")
    parser.add_argument("--interval", "-i", type=int, help="Run in a loop with specified interval in minutes (for continuous monitoring)")
    args = parser.parse_args(remaining)

    # Setup timezone and overview scheduling
    try:
        import pytz
    except ImportError:
        pytz = None

    timezone_str = config.settings.get('timezone', 'UTC')
    if pytz and timezone_str != 'UTC':
        tz = pytz.timezone(timezone_str)
    else:
        tz = timezone.utc
        if timezone_str != 'UTC':
            print(f"⚠️ Timezone '{timezone_str}' not supported without pytz, using UTC")

    overview_interval_hours = config.settings.get('overview_interval_hours', 24)
    overview_start = config.settings.get('overview_start_time', '04:00')
    start_hour, start_min = map(int, overview_start.split(':'))

    def get_next_overview_time():
        now = datetime.now(tz)
        today_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        if now >= today_start:
            next_time = today_start + timedelta(hours=overview_interval_hours)
        else:
            next_time = today_start
        return next_time

    # Log current database status
    try:
        summaries = load_summaries_from_db("news_reader.db")
        total_articles = sum(len(articles) for articles in summaries.values())
        print(f"📊 Database status: {total_articles} summarized articles from {len(summaries)} sources")
    except Exception as e:
        print(f"⚠️ Could not read database status: {e}")

    # Handle migration if requested
    if args.migrate:
        print("🔄 Migrating from JSON to SQLite database...")
        migrate_json_to_sqlite()
        print("✅ Migration complete! You can now use the database.")
        sys.exit(0)

    # Handle overview export if requested
    if args.export_overview:
        print("📤 Exporting latest overview for Home Assistant...")
        exported_file = export_overview_for_home_assistant("daily_news_overview.txt", "news_reader.db")
        if exported_file:
            print(f"✅ Overview exported to: {exported_file}")
            print("📱 Ready for Home Assistant TTS integration!")
        else:
            print("❌ Failed to export overview")
        sys.exit(0)

    # Initialize database and load data
    init_database("news_reader.db")
    error_tracking = load_error_tracking_from_db()

    urls = []
    source_groups = {}

    if args.file:
        urls.extend(read_urls_from_file(args.file))
        # Parse groups for channel routing
        source_groups = parse_source_groups(args.file, settings)
    if args.url:
        urls.append(args.url)

    summaries = load_summaries_from_db("news_reader.db")

    # Handle overview generation (doesn't require URLs)
    if args.overview:
        print("🌍 Generating state of the world overview...")
        overview_model = getattr(args, 'overview_model', settings.get("ollama", {}).get("overview_model", "llama2"))
        overview_prompt = getattr(args, 'overview_prompt', settings.get("prompts", {}).get("overview_summary", "Based on the following news summaries, provide a comprehensive overview..."))
        # Create overview summarizer with overview model
        overview_config = SummarizerConfig('ollama', host=args.host, model=overview_model, timeout=300)
        overview_summarizer = SummarizerFactory.create_summarizer(overview_config)

        max_summaries = settings.get("processing", {}).get("max_overview_summaries", 50)
        overview = generate_world_overview(overview_summarizer, summaries, overview_prompt, max_summaries)

        # Save overview (database by default, can be configured for file)
        saved_path = save_overview(overview, use_database=True)
        if saved_path:
            print(f"💾 Overview saved to: {saved_path}")

        # Send overview to configured output channels
        current_date = datetime.now().strftime("%Y-%m-%d")
        successful_sends = 0
        total_channels = len(output_channels)

        for channel in output_channels:
            try:
                result = channel.send_overview(overview, current_date)
                if result.success:
                    successful_sends += 1
                    print(f"✅ Overview sent to {type(channel).__name__}: {result.message}")
                else:
                    print(f"❌ Failed to send overview to {type(channel).__name__}: {result.error}")
            except Exception as e:
                print(f"❌ Error sending overview to {type(channel).__name__}: {e}")

        print(f"\n📊 Overview delivery: {successful_sends}/{total_channels} channels successful")

        # Display overview
        print("\n" + "="*80)
        print("STATE OF THE WORLD OVERVIEW")
        print("="*80)
        print(overview)
        print("="*80)
        sys.exit(0)

    # Process URLs if provided
    if not urls:
        print("Error: You must provide either --url or --file.")
        sys.exit(1)

    # Process sources by group with appropriate output channels
    print("🔍 Processing sources with channel routing...")
    rss_count = 0
    website_count = 0
    skipped_sources = 0

    # Create mappings for URL to channels and prompts
    url_channel_map = {}
    url_prompt_map = {}

    # If using grouped format, build channel and prompt mappings
    if source_groups:
        for group in source_groups.values():
            for url in group.urls:
                if group.output_channels:
                    # Group specifies specific channels
                    url_channel_map[url] = group.output_channels
                else:
                    # Empty channel list means use all channels
                    url_channel_map[url] = None

                # Store group-specific prompt if available
                if group.prompt:
                    url_prompt_map[url] = group.prompt
    else:
        # Flat format - all URLs go to all channels, use default prompt
        for url in urls:
            url_channel_map[url] = None
            url_prompt_map[url] = None

    for url in urls:
        # Ensure URL is a string to prevent type errors
        if not isinstance(url, str):
            print(f"Warning: Skipping invalid URL type {type(url)}: {url}")
            continue

        # Check if source should be excluded due to excessive failures
        if should_exclude_source(url, error_tracking):
            print(f"🚫 Skipping unreliable source: {url}")
            skipped_sources += 1
            continue

        # Get appropriate output channels for this URL
        channel_names = url_channel_map.get(url)
        print(f"   📤 Channel names for {url}: {channel_names}")
        specific_channels = config.get_output_channels(channel_names)
        print(f"   📤 Selected {len(specific_channels)} output channels: {[type(ch).__name__ for ch in specific_channels]}")

        source_type = detect_source_type(url)

        # Get prompt for this URL (group-specific or default)
        custom_prompt = url_prompt_map.get(url)
        if custom_prompt:
            article_prompt = custom_prompt
            print(f"   📝 Using custom prompt: {custom_prompt[:50]}...")
        else:
            article_prompt = settings.get("prompts", {}).get("article_summary", "Summarize this article briefly:")

        if args.scrape or source_type == "website":
            print(f"🌐 Scraping website: {url}")
            if channel_names:
                print(f"   📤 Channels: {', '.join(channel_names)}")
            process_website(url, summarizer, content_extractor, summaries, specific_channels, article_prompt, args.timeout)
            website_count += 1
        else:  # RSS feed
            print(f"📡 Processing RSS feed: {url}")
            if channel_names:
                print(f"   📤 Channels: {', '.join(channel_names)}")
            summarize_rss_feed(url, summarizer, summaries, content_extractor, article_prompt, args.timeout, specific_channels)
            rss_count += 1

    # Report final statistics
    print(f"\n✅ Processing complete: {rss_count} RSS feeds, {website_count} websites processed")
    if skipped_sources > 0:
        print(f"🚫 Skipped {skipped_sources} unreliable sources")
    print(f"📄 Summaries saved to: {args.output}")

    # Show health report if there are tracked errors
    if error_tracking:
        print("\n" + "="*60)
        health_report = report_source_health(error_tracking)
        print(health_report)
        print("="*60)

    # Handle continuous running with interval
    # Use command line arg if provided, otherwise use config setting
    run_interval = args.interval if args.interval and args.interval > 0 else config.get_interval()

    if run_interval > 0:
        import time
        print(f"\n🔄 Running in continuous mode with {run_interval} minute intervals...")
        print("Press Ctrl+C to stop")

        try:
            while True:
                # Wait for the specified interval
                time.sleep(run_interval * 60)

                print(f"\n{'='*80}")
                print(f"🔄 Starting scheduled run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*80}")

                # Reload configuration on each cycle to pick up changes
                print("🔄 Reloading configuration...")
                config = NewsReaderConfig("/app/data/settings.json")
                settings = config.settings
                
                # Reload output channels in case settings changed
                output_channels = config.get_output_channels()
                print(f"📋 Reloaded output channels: {[type(ch).__name__ for ch in output_channels]}")

                # Recalculate next overview time in case settings changed
                next_overview = get_next_overview_time()
                
                # Reload sources in case settings or sources file changed
                default_sources_file = settings.get('files', {}).get('sources', 'sources.txt')
                sources_file_path = f"/app/data/{default_sources_file}"
                urls = read_urls_from_file(sources_file_path)
                
                summaries = load_summaries_from_db("news_reader.db")
                error_tracking = load_error_tracking_from_db("news_reader.db")

                rss_count = 0
                website_count = 0
                skipped_sources = 0

                for url in urls:
                    if should_exclude_source(url, error_tracking):
                        skipped_sources += 1
                        continue

                    source_type = detect_source_type(url)

                    if args.scrape or source_type == "website":
                        print(f"🌐 Processing website: {url}")
                        article_prompt = settings.get("prompts", {}).get("article_summary", "Summarize this article briefly:")
                        process_website(url, summarizer, content_extractor, summaries, output_channels, article_prompt, args.timeout)
                        website_count += 1
                    else:  # RSS feed
                        print(f"📡 Processing RSS feed: {url}")
                        article_prompt = settings.get("prompts", {}).get("article_summary", "Summarize this article briefly:")
                        summarize_rss_feed(url, summarizer, summaries, content_extractor, article_prompt, args.timeout, output_channels)
                        rss_count += 1

                # Generate overview if requested
                if args.overview:
                    print("🌍 Generating state of the world overview...")
                    overview_prompt_final = settings.get("prompts", {}).get("overview_summary", "Based on the following news summaries, provide a comprehensive overview...")
                    max_summaries_final = settings.get("processing", {}).get("max_overview_summaries", 50)
                    overview = generate_world_overview(summarizer, summaries, overview_prompt_final, max_summaries_final)

                    if overview:
                        saved_path = save_overview(overview)
                        if saved_path:
                            print(f"💾 Overview saved to: {saved_path}")

                        # Send overview to configured output channels
                        current_date = datetime.now().strftime("%Y-%m-%d")
                        for channel in output_channels:
                            try:
                                result = channel.send_overview(overview, current_date)
                                if result.success:
                                    print(f"✅ Overview sent to {type(channel).__name__}: {result.message}")
                                else:
                                    print(f"❌ Failed to send overview to {type(channel).__name__}: {result.error}")
                            except Exception as e:
                                print(f"❌ Error sending overview to {type(channel).__name__}: {e}")

                        print("\n" + "="*80)
                        print("STATE OF THE WORLD OVERVIEW")
                        print("="*80)
                        print(overview)
                        print("="*80)

                print(f"\n✅ Scheduled run complete: {rss_count} RSS feeds, {website_count} websites processed")
                if skipped_sources > 0:
                    print(f"🚫 Skipped {skipped_sources} unreliable sources")

                print(f"⏰ Next run in {run_interval} minutes...")

        except KeyboardInterrupt:
            print("\n\n🛑 Continuous mode stopped by user")
        except Exception as e:
            print(f"\n❌ Error in continuous mode: {e}")
    

