import json
import os
from typing import Dict, Any, Optional, List


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
            success: Whether the summarization was successful
            content: The summarized content
            error: Error message if failed
            original_language: Detected language of original text
            translated: Whether the text was translated before summarization
        """
        self.success = success
        self.content = content
        self.error = error
        self.original_language = original_language
        self.translated = translated


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
            success: Whether the output was successful
            message: Success message or additional info
            error: Error message if failed
        """
        self.success = success
        self.message = message
        self.error = error


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

        # Support both old array format and new named channels format
        if isinstance(output_settings, list):
            return self._get_output_channels_legacy(output_settings, channel_names)
        else:
            return self._get_output_channels_named(output_settings, channel_names)

    def _get_output_channels_legacy(self, output_settings: List[Dict], channel_names: Optional[List[str]] = None) -> List[Any]:
        """Get output channels from legacy array format."""
        channels = []

        for output_channel in output_settings:
            channel_type = output_channel.get('type')
            if channel_type:
                config = OutputChannelConfig(channel_type, **output_channel.get('config', {}))
                try:
                    channel = OutputChannelFactory.create_channel(config)
                    if channel.is_available():
                        channels.append(channel)
                    else:
                        print(f"Warning: Output channel '{channel_type}' not available (not configured)")
                except ValueError as e:
                    print(f"Warning: {e}")

        return channels

    def _get_output_channels_named(self, output_settings: Dict, channel_names: Optional[List[str]] = None) -> List[Any]:
        """Get output channels from named channels format."""
        channels = []
        groups = output_settings.get('groups', {})

        # If no specific channel names requested, get all channels
        if channel_names is None:
            channel_names = list(output_settings.get('channels', {}).keys())

        # Expand groups to channel names
        all_channel_names = []
        for name in channel_names:
            if name in groups:
                group_channels = groups[name]
                if isinstance(group_channels, list):
                    all_channel_names.extend(group_channels)
                else:
                    print(f"Warning: Group '{name}' should be a list of channel names")
            else:
                all_channel_names.append(name)

        for channel_name in set(all_channel_names):
            channel_config = output_settings.get('channels', {}).get(channel_name)
            if channel_config:
                channel_type = channel_config.get('type')
                if channel_type:
                    config = OutputChannelConfig(channel_type, **channel_config.get('config', {}))
                    try:
                        channel = OutputChannelFactory.create_channel(config)
                        if channel.is_available():
                            channels.append(channel)
                        else:
                            print(f"Warning: Output channel '{channel_name}' ({channel_type}) not available (not configured)")
                    except ValueError as e:
                        print(f"Warning: {e}")
            else:
                print(f"Warning: Output channel '{channel_name}' not found in configuration")

        return channels

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