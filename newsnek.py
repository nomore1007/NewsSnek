"""
News Snek - Main Orchestrator
Ties together config, extraction, summarization, and delivery into a continuous loop.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any

from src.config import NewsReaderConfig
from src.extractor import ContentExtractor
from src.summarizers import ProviderChain, ProviderRegistry
from src.channels import OutputChannelFactory, OutputChannelConfig
from src.database import DataManager

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Set external library logging to WARNING unless debug is on
    if not debug:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("bs4").setLevel(logging.WARNING)

logger = logging.getLogger("news-snek")

# ============================================================================
# CORE ENGINE
# ============================================================================

class NewsSnekEngine:
    """The main execution engine for the News Snek project."""

    def __init__(self, base_dir: str, debug: bool = False):
        self.debug = debug
        self.base_dir = base_dir
        
        # Initialize core components
        self.config = NewsReaderConfig(base_dir=self.base_dir)
        self.extractor = ContentExtractor(self.config)
        self.db = DataManager(os.path.join(self.base_dir, self.config.get("files.database", "news_reader.db")))
        
        # We use the registry managed by config.py
        self.registry = self.config.registry

    def _get_publisher_name(self, url: str, author: str = "") -> str:
        """Attempt to derive a human-friendly publisher name from a URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc
        
        if not netloc:
            return "Unknown Source"
        
        # Handle YouTube URLs - use author/channel name if available
        if 'youtube.com' in netloc or 'youtu.be' in netloc:
            if author:
                return author
            return "YouTube"
        
        # Handle a few common domains with friendly names
        domain_map = {
            "nypost.com": "NY Post",
            "hackaday.com": "Hackaday",
            "arstechnica.com": "Ars Technica",
            "zdnet.com": "ZDNet",
            "bleepingcomputer.com": "Bleeping Computer",
        }
        
        # Strip 'www.' and 'm.' for cleaner matching
        clean_domain = netloc.replace("www.", "").replace("m.", "")
        
        if clean_domain in domain_map:
            return domain_map[clean_domain]
        
        # Generic fallback: capitalize the main domain name
        # e.g., "bbc.com" -> "Bbc", "foxnews.com" -> "Foxnews"
        main_domain = clean_domain.split('.')[0]
        return main_domain.capitalize()


    def _get_summarizer_for_group(self, group_name: str, group_data: Dict) -> ProviderChain:
        """
        Determines the correct provider chain for a source group.
        Checks for group-specific providers, otherwise falls back to a default.
        """
        # 1. Check for group-specific providers in sources.json
        provider_names = group_data.get("providers", [])
        
        # 2. Fallback to a global default if the group has none
        if not provider_names:
            # Try to find a default in settings.json or just use everything available
            provider_names = self.config.settings.get("summarizer", {}).get("providers", self.registry.list_providers())
            if not provider_names:
                # Last ditch: use whatever is registered
                provider_names = self.registry.list_providers()

        if not provider_names:
            raise Exception(f"No AI providers available for group '{group_name}' and no defaults found.")

        return ProviderChain(
            name=f"chain-{group_name}",
            provider_names=provider_names,
            registry=self.registry
        )

    def _get_channel_instance(self, channel_name: str):
        """
        Creates or retrieves a channel instance based on configuration.
        """
        channel_defs = self.config.get_output_channel_configs()
        if channel_name not in channel_defs:
            logger.warning(f"Channel '{channel_name}' not found in configuration.")
            return None
        
        channel_def = channel_defs[channel_name]
        cfg = OutputChannelConfig(
            channel_type=channel_def.get("type"),
            **channel_def.get("config", {})
        )
        return OutputChannelFactory.create_channel(cfg)

    def process_cycle(self):
        """One complete pass: Reload -> Fetch -> Summarize -> Store -> Dispatch."""
        logger.info("🚀 Starting processing cycle...")
        
        # 1. Runtime Reload
        self.config.reload()
        
        # 2. Identify source groups
        groups = self.config.get_source_groups()
        if not groups:
            logger.warning("No source groups found to process.")
            return

        for group_name, group_data in groups.items():
            logger.info(f"📦 Processing group: {group_name}")
            
            # Setup summarizer chain for this group
            try:
                chain = self._get_summarizer_for_group(group_name, group_data)
                prompt = group_data.get("prompt") or self.config.get("prompts.article_summary", "Summarize this article briefly:")
            except Exception as e:
                logger.error(f"❌ Could not setup summarizer for {group_name}: {e}")
                continue

            urls = group_data.get("sources", [])
            target_channels = group_data.get("channels", [])

            for url in urls:
                # Determine if this URL is an RSS feed
                feed_entries = self.extractor.parse_rss_feed(url)
                
                if feed_entries:
                    # It's an RSS feed - process each entry
                    for entry in feed_entries:
                        article_url = entry.get('link')
                        if not article_url:
                            continue
                            
                        # Skip if already processed
                        if self.db.has_article(article_url):
                            logger.debug(f"⏭️ Skipping duplicate article: {article_url}")
                            continue
                        
                        logger.info(f"🔎 Extracting content: {article_url}")
                        content, thumbnail = self.extractor.extract_from_url(article_url)
                        
                        # Check for known extraction failure markers
                        error_markers = ["[Error", "[Could not extract content]", "[Invalid", "[YouTube"]
                        if not content or any(marker in content for marker in error_markers):
                            logger.error(f"❌ Extraction failed for {article_url}: {content}")
                            continue

                        # Use the entry title from the feed, fallback to first line of content
                        title = entry.get('title', 'No Title')[:100] or (content.split('\n')[0][:100] if content else "Untitled Article")
                        author = entry.get('author', '')
                        
                        # Summarize using the chain
                        try:
                            logger.info(f"🤖 Summarizing with chain {chain.name}...")
                            summary = chain.summarize(content, prompt)
                            
                            # Store in DB
                            self.db.store_article(article_url, title, summary, group_name)
                            
                            # Dispatch to channels only if summary is not an error message
                            if not (summary.startswith('[') and ('Error' in summary or 'Could not' in summary)):
                                for channel_name in target_channels:
                                    channel = self._get_channel_instance(channel_name)
                                    if channel:
                                        # Append author to source if available
                                        # Append author to source if available
                                        display_source = self._get_publisher_name(article_url, author)
                                        if author:
                                            display_source = f"{display_source} ({author})"
                                        channel.send_summary(
                                            title,
                                            summary,
                                            display_source,
                                            "",
                                            article_url,
                                            thumbnail
                                        )
                        except Exception as e:
                            logger.error(f"❌ Summarization/Dispatch failed for {article_url}: {e}")
                else:
                    # It's a direct article URL
                    if self.db.has_article(url):
                        logger.debug(f"⏭️ Skipping duplicate article: {url}")
                        continue
                    
                    logger.info(f"🔎 Extracting content: {url}")
                    content, thumbnail = self.extractor.extract_from_url(url)
                    
                    # Check for known extraction failure markers
                    error_markers = ["[Error", "[Could not extract content]", "[Invalid", "[YouTube"]
                    if not content or any(marker in content for marker in error_markers):
                        logger.error(f"❌ Extraction failed for {url}: {content}")
                        continue

                    # Try to get a title (usually first line of content or a fallback)
                    title = content.split('\n')[0][:100] if content else "Untitled Article"
                    
                    # Summarize using the chain
                    try:
                        logger.info(f"🤖 Summarizing with chain {chain.name}...")
                        summary = chain.summarize(content, prompt)
                        
                        # Store in DB
                        self.db.store_article(url, title, summary, group_name)
                        
                        # Dispatch to channels only if summary is not an error message
                        if not (summary.startswith('[') and ('Error' in summary or 'Could not' in summary)):
                            for channel_name in target_channels:
                                channel = self._get_channel_instance(channel_name)
                                if channel:
                                    channel.send_summary(
                                        title,
                                        summary,
                                        group_name if self.debug else self._get_publisher_name(url),
                                        "",
                                        url,
                                        thumbnail
                                    )
                    except Exception as e:
                        logger.error(f"❌ Summarization/Dispatch failed for {url}: {e}")

    def generate_daily_overview(self):
        """Pulls recent summaries from DB and generates a world-state overview."""
        logger.info("🌍 Generating daily overview...")
        
        # 1. Fetch recent summaries
        summaries = self.db.fetch_summaries_for_overview(max_items=50)
        if not summaries:
            logger.info("No recent summaries found. Skipping overview.")
            return

        # 2. Build source list for attribution
        source_list = [s['source'] for s in summaries]
        
        # 3. Format for the AI
        context = "\n\n".join([f"Source: {s['source']}\nTitle: {s['title']}\nSummary: {s['summary']}" for s in summaries])
        overview_prompt = self.config.get("prompts.overview_summary", "Provide a comprehensive overview of the following news summaries:")
        
        # 4. Use a high-quality provider for the overview (fallback to a chain)
        try:
            # For the overview, we try to use a specific 'overview' provider if configured, 
            # otherwise we use a general chain.
            overview_provider_name = self.config.settings.get("summarizer", {}).get("overview_model", "openrouter-auto")
            provider = self.registry.get(overview_provider_name)
            
            if not provider:
                # Fallback: create a chain of all available providers
                logger.info(f"Overview provider {overview_provider_name} not found, using fallback chain.")
                provider = ProviderChain("overview-fallback", self.registry.list_providers(), self.registry)

            overview_text = provider.summarize(context, overview_prompt)
            
            # 5. Dispatch overview to all configured channels, passing source list
            channel_defs = self.config.get_output_channel_configs()
            for channel_name in channel_defs:
                channel = self._get_channel_instance(channel_name)
                if channel:
                    # Updated call now includes sources
                    if hasattr(channel, "send_overview"):
                        channel.send_overview(overview_text, date=datetime.utcnow().strftime("%Y-%m-%d"), sources=source_list)
                    else:
                        # Fallback for channels without source support
                        channel.send(overview_text, title=f"News Overview - {datetime.utcnow().strftime('%Y-%m-%d')}")
            
            logger.info("✅ Daily overview dispatched.")
        except Exception as e:
            logger.error(f"❌ Failed to generate daily overview: {e}")

    def run_forever(self):
        """The main loop."""
        logger.info("🤖 News Snek is online. Starting loop...")
        try:
            while True:
                self.process_cycle()
                
                # Optional: run overview daily (once per 24 hours)
                self.generate_daily_overview()
                
                interval = self.config.get_interval()
                logger.info(f"💤 Sleeping for {interval} minutes...")
                time.sleep(interval * 60)
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user.")
        except Exception as e:
            logger.critical(f"💥 Fatal error in main loop: {e}", exc_info=True)

# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="News Snek - AI News Summarizer")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()

    setup_logging(args.debug)
    
    # Determine base directory relative to the script location
    base_dir = os.path.dirname(os.path.abspath(__file__))
    engine = NewsSnekEngine(base_dir=base_dir, debug=args.debug)
    
    if args.once:
        engine.process_cycle()
        engine.generate_daily_overview()
        logger.info("✅ Single cycle completed.")
    else:
        engine.run_forever()