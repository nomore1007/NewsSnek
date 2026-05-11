"""
News Snek - Configuration Management
Handles runtime reloading of settings.json and sources.json.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from .summarizers import ProviderRegistry, create_provider_from_config

logger = logging.getLogger(__name__)

class NewsReaderConfig:
    """
    Centralized configuration management for the news reader.
    Supports runtime reloading of settings and sources files.
    """

    def __init__(self, base_dir: str = ".", settings_file: str = "settings.json", sources_file: str = "sources.json"):
        # Use absolute path for base_dir to avoid CWD issues
        self.base_dir = os.path.abspath(base_dir)
        self.settings_file = settings_file
        self.sources_file = sources_file
        
        self.settings: Dict[str, Any] = {}
        self.sources: Dict[str, Any] = {}
        self.registry = ProviderRegistry()
        
        # Initial load
        self.reload()

    def reload(self):
        """
        Reload settings and sources from disk.
        Call this at the start of every processing cycle to ensure updates take effect.
        """
        logger.info(f"🔄 Reloading configuration from base_dir: {self.base_dir}")
        self._load_settings()
        self._load_sources()
        self._setup_providers()
        logger.info("✅ Configuration reloaded successfully.")

    def _load_settings(self):
        """Load settings from JSON file with defaults."""
        settings_paths = [
            "/app/data/settings.json", 
            os.path.join(self.base_dir, self.settings_file),
            os.path.join(self.base_dir, "settings.json"),
        ]

        for path in settings_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        self.settings = json.load(f)
                    logger.debug(f"Loaded settings from {path}")
                    return
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON in {path}: {e}")
                    continue

        # Fallback to defaults
        logger.warning("⚠️ No valid settings file found. Using defaults.")
        self.settings = self._get_defaults()

    def _load_sources(self):
        """Load source groups from JSON or TXT file."""
        sources_filename = self.settings.get("files", {}).get("sources", self.sources_file)
        
        if os.path.isabs(sources_filename):
            sources_path = sources_filename
        else:
            sources_path = os.path.join(self.base_dir, sources_filename)

        # Check for inline sources in settings first
        if "sources" in self.settings and "groups" in self.settings["sources"]:
            self.sources = self.settings["sources"]
            return

        if os.path.exists(sources_path):
            try:
                if sources_path.endswith('.json'):
                    with open(sources_path, 'r', encoding='utf-8') as f:
                        self.sources = json.load(f)
                else:
                    self.sources = self._parse_legacy_sources(sources_path)
                return
            except Exception as e:
                logger.error(f"❌ Failed to load sources from {sources_path}: {e}")

        self.sources = {"groups": {}}

    def _parse_legacy_sources(self, filepath: str) -> Dict:
        """Convert legacy .txt sources to the internal group structure."""
        urls = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        
        return {
            "groups": {
                "default": {
                    "description": "Legacy sources from text file",
                    "channels": ["console"],
                    "prompt": None,
                    "sources": urls
                }
            }
        }

    def _setup_providers(self):
        """Initialize the ProviderRegistry based on named providers in settings.json."""
        providers_cfg = self.settings.get("providers", {})
        if not providers_cfg:
            logger.warning("⚠️ No 'providers' registry found in settings.json. AI features may fail.")
            return

        # Reset registry
        self.registry = ProviderRegistry()

        for name, cfg in providers_cfg.items():
            try:
                p_type = cfg.get("type")
                # The 'config' is the whole dict minus the 'type' key (flat structure)
                p_config = {k: v for k, v in cfg.items() if k != 'type'}
                
                provider_instance = create_provider_from_config(p_type, name, p_config)
                self.registry.register(name, provider_instance)
            except Exception as e:
                logger.error(f"❌ Failed to register provider '{name}': {e}")

    def _get_defaults(self) -> Dict:
        return {
            "providers": {},
            "processing": {
                "max_overview_summaries": 50,
                "scrape_timeout": 30,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "prompts": {
                "article_summary": "Summarize this article briefly:",
                "overview_summary": "Provide a comprehensive overview..."
            },
            "files": {
                "sources": "sources.json",
                "database": "news_reader.db"
            },
            "interval": 60
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        val = self.settings
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

    def get_source_groups(self) -> Dict[str, Any]:
        return self.sources.get("groups", {})

    def get_output_channel_configs(self) -> Dict[str, Any]:
        return self.settings.get("output", {}).get("channels", {})

    def get_interval(self) -> int:
        return int(self.get("interval", 60))
