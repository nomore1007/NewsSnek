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
        
        self.config = NewsReaderConfig(base_dir=self.base_dir)
        self.extractor = ContentExtractor(self.config)
        self.db = DataManager(os.path.join(self.base_dir, "data", self.config.get("files.database", "news_reader.db")))
        self.registry = self.config.registry

    def _get_publisher_name(self, url: str, author: str = "") -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc
        if not netloc: return "Unknown Source"
        if 'youtube.com' in netloc or 'youtu.be' in netloc:
            return author if author else "YouTube"
        
        domain_map = {
            "nypost.com": "NY Post",
            "hackaday.com": "Hackaday",
            "arstechnica.com": "Ars Technica",
            "zdnet.com": "ZDNet",
            "bleepingcomputer.com": "Bleeping Computer",
        }
        clean_domain = netloc.replace("www.", "").replace("m.", "")
        if clean_domain in domain_map: return domain_map[clean_domain]
        return clean_domain.split('.')[0].capitalize()

    def _get_summarizer_for_group(self, group_name: str, group_data: Dict) -> ProviderChain:
        provider_names = group_data.get("providers", [])
        if not provider_names:
            provider_names = self.config.settings.get("summarizer", {}).get("providers", self.registry.list_providers())
            if not provider_names: provider_names = self.registry.list_providers()
        
        if not provider_names:
            raise Exception(f"No AI providers available for group '{group_name}'.")
        
        return ProviderChain(name=f"chain-{group_name}", provider_names=provider_names, registry=self.registry)

    def _get_channel_instance(self, channel_name: str):
        channel_defs = self.config.get_output_channel_configs()
        if channel_name not in channel_defs:
            logger.warning(f"Channel '{channel_name}' not found.")
            return None
        
        channel_def = channel_defs[channel_name]
        cfg = OutputChannelConfig(channel_type=channel_def.get("type"), **channel_def.get("config", {}))
        return OutputChannelFactory.create_channel(cfg)

    def process_cycle(self):
        """One complete pass: Reload -> Fetch -> Summarize -> Store -> Dispatch."""
        logger.info("🚀 Starting processing cycle...")
        self.config.reload()
        groups = self.config.get_source_groups()
        if not groups:
            logger.warning("No source groups found.")
            return

        for group_name, group_data in groups.items():
            logger.info(f"📦 Processing group: {group_name}")
            try:
                chain = self._get_summarizer_for_group(group_name, group_data)
                prompt = group_data.get("prompt") or self.config.get("prompts.article_summary", "Summarize this article briefly:")
                silent_fail = group_data.get("silent_fail", False)
            except Exception as e:
                logger.error(f"❌ Setup failed for {group_name}: {e}")
                continue

            urls = group_data.get("sources", [])
            target_channels = group_data.get("channels", [])

            for url in urls:
                # Only attempt RSS parsing if the URL looks like a feed
                is_feed = any(ext in url.lower() for ext in ['/feed', '.xml', '.rss'])
                feed_entries = self.extractor.parse_rss_feed(url) if is_feed else []
                
                if feed_entries:
                    for entry in feed_entries:
                        article_url = entry.get('link')
                        if not article_url or self.db.has_article(article_url): continue
                        
                        logger.info(f"🔎 Extracting: {article_url}")
                        content, thumbnail = self.extractor.extract_from_url(article_url)
                        if not content or any(m in content for m in ["[Error", "[Could not extract content]"]): continue
                        
                        title = entry.get('title', 'No Title')[:250]

                        author = entry.get('author', '')
                        
                        try:
                            summary = chain.summarize(content, prompt, silent_fail=silent_fail)
                            if summary:
                                self.db.store_article(article_url, title, summary, group_name)
                                if not (summary.startswith('[') and 'Error' in summary):
                                    for ch_name in target_channels:
                                        ch = self._get_channel_instance(ch_name)
                                        if ch:
                                            src = self._get_publisher_name(article_url, author)
                                            ch.send_summary(title, summary, src, "", article_url, thumbnail)
                        except Exception as e:
                            if not silent_fail:
                                logger.error(f"❌ Summary failed for {article_url}: {e}")
                else:
                    if self.db.has_article(url): continue
                    logger.info(f"🔎 Extracting: {url}")
                    content, thumbnail = self.extractor.extract_from_url(url)
                    if not content or any(m in content for m in ["[Error", "[Could not extract content]"]): continue
                    title = content.split('\n')[0][:250] if content else "Untitled"
                    
                    try:
                        summary = chain.summarize(content, prompt, silent_fail=silent_fail)
                        if summary:
                            self.db.store_article(url, title, summary, group_name)
                            if not (summary.startswith('[') and 'Error' in summary):
                                for ch_name in target_channels:
                                    ch = self._get_channel_instance(ch_name)
                                    if ch:
                                        src = self._get_publisher_name(url, '')
                                        ch.send_summary(title, summary, src, "", url, thumbnail)
                    except Exception as e:
                        if not silent_fail:
                            logger.error(f"❌ Summary failed for {url}: {e}")

    def generate_daily_overview(self):
        """Generate and dispatch a daily overview if the configured time matches."""
        overview_cfg = self.config.settings.get("overview", {})
        if not overview_cfg: return
        schedule_time = overview_cfg.get("time")
        if not schedule_time: return
        try:
            h, m = map(int, schedule_time.split(":"))
        except: return

        now = datetime.utcnow()
        if now.hour != h or now.minute != m: return

        target_channels = overview_cfg.get("channels")
        if target_channels is None: target_channels = list(self.config.get_output_channel_configs().keys())
        
        logger.info(f"🌍 Generating daily overview at {schedule_time}...")
        summaries = self.db.fetch_summaries_for_overview(max_items=overview_cfg.get("max_items", 50))
        if not summaries: return

        source_list = [s['source'] for s in summaries]
        context = "\n\n".join([f"Source: {s['source']}\nTitle: {s['title']}\nSummary: {s['summary']}" for s in summaries])
        prompt = self.config.get("prompts.overview_summary", "Provide a comprehensive overview:")
        
        try:
            model_name = self.config.settings.get("summarizer", {}).get("overview_model", "openrouter-auto")
            provider = self.registry.get(model_name) or ProviderChain("overview-fallback", self.registry.list_providers(), self.registry)
            overview_text = provider.summarize(context, prompt)
            
            for ch_name in target_channels:
                ch = self._get_channel_instance(ch_name)
                if ch:
                    if hasattr(ch, "send_overview"):
                        ch.send_overview(overview_text, date=now.strftime("%Y-%m-%d"), sources=source_list)
                    else:
                        ch.send(overview_text, title=f"News Overview - {now.strftime('%Y-%m-%d')}")
            logger.info("✅ Daily overview dispatched.")
        except Exception as e:
            logger.error(f"❌ Overview failed: {e}")

    def run_forever(self):
        logger.info("🤖 News Snek is online.")
        try:
            while True:
                self.process_cycle()
                self.generate_daily_overview()
                time.sleep(self.config.get_interval() * 60)
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested.")
        except Exception as e:
            logger.critical(f"💥 Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    setup_logging(args.debug)
    engine = NewsSnekEngine(base_dir=os.path.dirname(os.path.abspath(__file__)), debug=args.debug)
    if args.once:
        engine.process_cycle()
        engine.generate_daily_overview()
    else:
        engine.run_forever()
