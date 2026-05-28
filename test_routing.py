
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

# Mocking the src components to avoid dependency issues during a standalone test
class MockConfig:
    def __init__(self):
        self.settings = {
            "output": {
                "channels": {
                    "tech": {"type": "mock", "config": {}},
                    "first-world": {"type": "mock", "config": {}},
                    "daily-overview": {"type": "mock", "config": {}},
                }
            },
            "overview": {
                "time": datetime.utcnow().strftime("%H:%M"), # Set to NOW for testing
                "max_items": 5
            },
            "summarizer": {"overview_model": "mock-llm"},
            "prompts": {
                "article_summary": "Summarize: ",
                "overview_summary": "Overview: "
            },
            "interval": 60
        }
        self.sources = {
            "groups": {
                "tech_group": {
                    "sources": ["http://tech.com/1", "http://tech.com/2"],
                    "channels": ["tech"]
                },
                "world_group": {
                    "sources": ["http://world.com/1"],
                    "channels": ["first-world"]
                }
            }
        }
        self.registry = MockRegistry()

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        try:
            for k in keys: val = val[k]
            return val
        except: return default

    def get_source_groups(self): return self.sources["groups"]
    def get_output_channel_configs(self): return self.settings["output"]["channels"]
    def get_interval(self): return self.settings["interval"]
    def reload(self): pass

class MockRegistry:
    def get(self, name): return MockProvider(name)
    def list_providers(self): return ["mock-llm"]

class MockProvider:
    def __init__(self, name): self.name = name
    def summarize(self, text, prompt): return f"[{self.name}] Summary of {text[:20]}..."

class MockChannel:
    def __init__(self, name): self.name = name
    def send_summary(self, title, summary, source, extra, url, thumb):
        print(f"SENDING TO [{self.name}] | {title} | {summary}")
    def send_overview(self, text, date, sources):
        print(f"SENDING OVERVIEW TO [{self.name}] | {text} | Date: {date}")
    def send(self, text, title=None):
        print(f"SENDING GENERIC TO [{self.name}] | {title} | {text}")

class MockExtractor:
    def parse_rss_feed(self, url):
        if "tech" in url: return [{"link": url, "title": "Tech News", "author": "TechBot"}]
        if "world" in url: return [{"link": url, "title": "World News", "author": "WorldBot"}]
        return None
    def extract_from_url(self, url): return (f"Content of {url}", "thumb.jpg")

class MockDB:
    def __init__(self): self.data = []
    def has_article(self, url): return False
    def store_article(self, url, title, summary, group):
        self.data.append({"source": url, "title": title, "summary": summary})
    def fetch_summaries_for_overview(self, max_items=50): return self.data

class NewsSnekTestEngine:
    def __init__(self):
        self.config = MockConfig()
        self.extractor = MockExtractor()
        self.db = MockDB()
        self.registry = self.config.registry

    def _get_channel_instance(self, name):
        return MockChannel(name)

    def process_cycle(self):
        groups = self.config.get_source_groups()
        for group_name, group_data in groups.items():
            urls = group_data.get("sources", [])
            target_channels = group_data.get("channels", [])
            
            for url in urls:
                entries = self.extractor.parse_rss_feed(url)
                if entries:
                    for entry in entries:
                        title = entry['title']
                        summary = "Short summary"
                        self.db.store_article(url, title, summary, group_name)
                        for ch_name in target_channels:
                            ch = self._get_channel_instance(ch_name)
                            ch.send_summary(title, summary, "Source", "", url, "")

    def generate_daily_overview(self):
        overview_cfg = self.config.settings.get("overview", {})
        schedule_time = overview_cfg.get("time")
        now = datetime.utcnow()
        
        # Match time
        h, m = map(int, schedule_time.split(":"))
        if now.hour == h and now.minute == m:
            summaries = self.db.fetch_summaries_for_overview()
            overview_text = "WORLD STATE SUMMARY"
            
            # TARGET ROUTING: Only send to 'daily-overview' channel
            target_channel = "daily-overview"
            ch = self._get_channel_instance(target_channel)
            if ch:
                ch.send_overview(overview_text, now.strftime("%Y-%m-%d"), [])

if __name__ == "__main__":
    engine = NewsSnekTestEngine()
    print("--- Testing Article Routing ---")
    engine.process_cycle()
    print("\n--- Testing Overview Routing ---")
    engine.generate_daily_overview()
