"""
News Snek - Content Extraction Module
Handles RSS parsing, web scraping, YouTube transcripts, and Internet Archive fallbacks.
"""

import logging
import requests
from urllib.parse import urljoin, quote, urlparse
from typing import Tuple, Optional, List, Dict
import feedparser
from bs4 import BeautifulSoup

# YouTube Transcript handling (optional dependency)
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPTS_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPTS_AVAILABLE = False
    YouTubeTranscriptApi = None

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Handles content extraction from various sources (URLs, RSS, YouTube)."""

    def __init__(self, config):
        """
        Initialize content extractor.
        
        Args:
            config: NewsReaderConfig instance (provides settings like timeout, user_agent)
        """
        self.config = config
        # Get default timeout and user agent from config
        self.default_timeout = config.get("processing.scrape_timeout", 30)
        self.user_agent = config.get("processing.user_agent", 
                                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")


    def extract_from_url(self, url: str, timeout: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        Extract content and thumbnail from a URL.
        
        Args:
            url: URL to extract content from
            timeout: Request timeout (defaults to config value)
            
        Returns:
            Tuple of (content_text, thumbnail_url)
        """
        if timeout is None:
            timeout = self.default_timeout

        # Pre-emptively check for YouTube thumbnail
        thumbnail_url = None
        if self._is_youtube_video_url(url):
            thumbnail_url = self._get_youtube_thumbnail(url)

        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            # Only try to extract HTML thumbnail if we don't have a YouTube one
            if not thumbnail_url:
                thumbnail_url = self._extract_thumbnail_url(soup, base_url)

            # Check for YouTube content
            if self._is_youtube_video_url(url):
                transcript = self._extract_youtube_transcript(url)
                if transcript and not any(transcript.startswith(prefix) for prefix in 
                                         ['[Error', '[Could not', '[Invalid', '[YouTube']):
                    return transcript, thumbnail_url

            # Extract main article content
            content = self._extract_main_content(soup)
            return content, thumbnail_url

        except Exception as e:
            logger.warning(f"Failed to extract content from {url}: {e}. Trying Internet Archive.")
            archive_url = self.get_internet_archive_url(url)
            if archive_url:
                logger.info(f"Found Internet Archive snapshot: {archive_url}")
                try:
                    response = requests.get(archive_url, headers=headers, timeout=timeout)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content.decode('utf-8', errors='ignore'), 'html.parser')
                    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    
                    # Again, check for YouTube thumbnail if fallback is also a YT link
                    if not thumbnail_url and self._is_youtube_video_url(archive_url):
                        thumbnail_url = self._get_youtube_thumbnail(archive_url)
                    elif not thumbnail_url:
                        thumbnail_url = self._extract_thumbnail_url(soup, base_url)
                        
                    content = self._extract_main_content(soup)
                    return content, thumbnail_url
                except Exception as archive_e:
                    return f"[Error extracting content from Internet Archive {archive_url}: {archive_e}]", None
            else:
                return f"[Error extracting content from {url}: {e}]", None


    def get_internet_archive_url(self, url: str) -> Optional[str]:
        """Get the latest Internet Archive snapshot URL for a given URL."""
        try:
            archive_url = f"https://archive.org/wayback/available?url={quote(url)}"
            response = requests.get(archive_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("archived_snapshots", {}).get("closest"):
                return data["archived_snapshots"]["closest"]["url"]
            return None
        except Exception as e:
            logger.error(f"Failed to get Internet Archive URL for {url}: {e}")
            return None


    def _get_youtube_thumbnail(self, url: str) -> Optional[str]:
        """Get high-res thumbnail for a YouTube video."""
        video_id = None
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0].split('#')[0]
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0].split('#')[0]
        elif 'youtube.com/embed/' in url:
            video_id = url.split('youtube.com/embed/')[1].split('?')[0].split('&')[0].split('#')[0]
        elif 'youtube.com/shorts/' in url:
            video_id = url.split('youtube.com/shorts/')[1].split('?')[0].split('&')[0].split('#')[0]
        
        if video_id and len(video_id) == 11:
            return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return None

    def _extract_thumbnail_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract thumbnail URL from HTML soup."""
        # Try OpenGraph and Twitter card images first
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image['content'])

        twitter_image = soup.find('meta', property='twitter:image')
        if twitter_image and twitter_image.get('content'):
            return urljoin(base_url, twitter_image['content'])

        # Find a prominent image in the article body
        article_body = soup.find('article') or soup.find('main')
        if article_body:
            first_img = article_body.find('img')
            if first_img and first_img.get('src'):
                return urljoin(base_url, first_img['src'])

        return None

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
            # Extract video ID from URL
            video_id = None
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0].split('#')[0]
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0].split('#')[0]
            elif 'youtube.com/embed/' in url:
                video_id = url.split('youtube.com/embed/')[1].split('?')[0].split('&')[0].split('#')[0]
            elif 'youtube.com/shorts/' in url:
                video_id = url.split('youtube.com/shorts/')[1].split('?')[0].split('&')[0].split('#')[0]

            # Validate video ID (YouTube IDs are 11 characters)
            if not video_id or len(video_id) != 11:
                return f"[Invalid YouTube video ID format for URL: {url}]"

            transcript_api = YouTubeTranscriptApi()
            transcript = transcript_api.fetch(video_id)

            # Combine transcript text
            transcript_text = " ".join([entry.text for entry in transcript])
            transcript_text = ' '.join(transcript_text.split())  # Clean up whitespace
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
            for unwanted in body.select('script, style, nav, header, footer, aside, .ads, .comments'):
                unwanted.decompose()
            text = body.get_text(separator=' ', strip=True)
            return text

        return "[Could not extract content]"

    def parse_rss_feed(self, url: str) -> List[Dict]:
        """
        Parse an RSS feed and return a list of entries.
        
        Args:
            url: RSS feed URL
            
        Returns:
            List of dicts with keys: title, link, published, summary
        """
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.warning(f"RSS feed {url} may be malformed: {feed.bozo_exception}")
            
            entries = []
            for entry in feed.entries:
                entries.append({
                    'title': entry.get('title', 'No Title'),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'summary': entry.get('summary', ''),
                    'author': entry.get('author', '')
                })
            return entries
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {url}: {e}")
            return []
