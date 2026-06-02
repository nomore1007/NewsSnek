"""
News Snek - Output Channel Implementations
Provides Console, Telegram, and Discord output channels and a factory to create them.
"""

import logging
import requests
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper for cleaning OpenRouter <think> tags
# ---------------------------------------------------------------------------

def _strip_think(text: str) -> str:
    """Remove any <think>...<\/think> blocks from the text.
    OpenRouter responses sometimes include reasoning in this tag; for
    public channel output we want the final answer only.
    """
    if not text:
        return ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# ---------------------------------------------------------------------------
# Configuration & Result helper classes
# ---------------------------------------------------------------------------

class OutputChannelConfig:
    """Configuration holder for an output channel."""

    def __init__(self, channel_type: str, **kwargs: Any):
        self.channel_type = channel_type
        self.options = kwargs


class OutputChannelResult:
    """Result object returned by channel send operations."""

    def __init__(self, success: bool, message: str = "", error: str = ""):
        self.success = success
        self.message = message
        self.error = error


# ---------------------------------------------------------------------------
# Abstract base channel
# ---------------------------------------------------------------------------

class OutputChannel(ABC):
    """Base class for all output channels."""

    def __init__(self, config: OutputChannelConfig):
        self.config = config

    @abstractmethod
    def send_summary(self, title: str, summary: str, source: str = "", category: str = "", article_url: str = "", thumbnail_url: Optional[str] = None) -> OutputChannelResult:
        pass

    @abstractmethod
    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


# ---------------------------------------------------------------------------
# Concrete channel implementations
# ---------------------------------------------------------------------------

class ConsoleOutputChannel(OutputChannel):
    """Writes output to stdout or an optional file."""

    def __init__(self, config: OutputChannelConfig):
        super().__init__(config)
        self.output_file: Optional[str] = config.options.get('output_file')

    def is_available(self) -> bool:
        return True

    def _format_message(self, title: str, summary: str, source: str, category: str, article_url: str, thumbnail_url: Optional[str]) -> str:
        title = _strip_think(title)
        summary = _strip_think(summary)
        parts = [f"📄 {title}\n"]
        if source:
            parts.append(f"Channel: {source}\n")
        if category:
            parts.append(f"Category: {category}\n")
        if article_url:
            parts.append(f"URL: {article_url}\n")
        if thumbnail_url:
            parts.append(f"Thumbnail: {thumbnail_url}\n")
        parts.append(f"Summary: {summary}\n\n")
        return "".join(parts)

    def send_summary(self, title: str, summary: str, source: str = "", category: str = "", article_url: str = "", thumbnail_url: Optional[str] = None) -> OutputChannelResult:
        try:
            msg = self._format_message(title, summary, source, category, article_url, thumbnail_url)
            if self.output_file:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(msg)
                logger.info(f"✅ Console: Summary written to {self.output_file}")
                return OutputChannelResult(True, f"Written to {self.output_file}")
            else:
                print(msg)
                logger.info("✅ Console: Summary printed to stdout")
                return OutputChannelResult(True, "Printed to console")
        except Exception as e:
            logger.error(f"❌ Console output failed: {e}")
            return OutputChannelResult(False, error=str(e))

    def send_overview(self, overview: str, date: str = "", sources: list = None) -> OutputChannelResult:
        try:
            header = f"🌍 Daily News Overview"
            if date:
                header += f" - {date}"
            header += "\n" + "=" * 50 + "\n\n"
            
            # Add sources if provided
            if sources:
                unique_sources = sorted(list(set(sources)))
                header += f"Sources: {', '.join(unique_sources)}\n\n"
            
            output = header + overview
            if self.output_file:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                logger.info(f"✅ Console: Overview written to {self.output_file}")
                return OutputChannelResult(True, f"Overview written to {self.output_file}")
            else:
                print(output)
                logger.info("✅ Console: Overview printed to stdout")
                return OutputChannelResult(True, "Overview printed to console")
        except Exception as e:
            logger.error(f"❌ Console overview failed: {e}")
            return OutputChannelResult(False, error=str(e))


class TelegramOutputChannel(OutputChannel):
    """Sends messages via the Telegram Bot API with robust image handling."""

    def __init__(self, config: OutputChannelConfig):
        super().__init__(config)
        self.bot_token: Optional[str] = config.options.get('bot_token')
        self.chat_id: Optional[str] = config.options.get('chat_id')
        self.api_url: Optional[str] = (
            f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        )

    def is_available(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _post(self, method: str, payload: Dict) -> Dict:
        if not self.api_url:
            raise RuntimeError("Telegram API URL is not configured")
        url = f"{self.api_url}/{method}"
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _is_image_url_valid(self, url: str) -> bool:
        """
        Very small sanity check: make sure the URL points to something that
        looks like an image and is reachable with a HEAD request.
        """
        if not url:
            return False
        # Basic pattern check – must end with a common image extension
        if not re.search(r"\.(png|jpe?g|gif|bmp|webp)(\?.*)?$", url, re.IGNORECASE):
            logger.warning(f"Telegram: thumbnail URL does not look like an image: {url}")
            return False
        try:
            head = requests.head(url, timeout=5, allow_redirects=True)
            # Telegram only accepts images up to ~10 MB; we just check the MIME type
            ct = head.headers.get("Content-Type", "")
            if not ct.startswith("image/"):
                logger.warning(f"Telegram: thumbnail URL is not an image (Content-Type={ct}): {url}")
                return False
            return True
        except Exception as exc:
            logger.warning(f"Telegram: could not verify thumbnail URL {url}: {exc}")
            return False

    def send_summary(
        self,
        title: str,
        summary: str,
        source: str = "",
        category: str = "",
        article_url: str = "",
        thumbnail_url: Optional[str] = None,
    ) -> OutputChannelResult:
        title = _strip_think(title)
        summary = _strip_think(summary)

        if not self.is_available():
            return OutputChannelResult(False, error="Telegram not configured")

        # Build the common message body (Markdown)
        message = f"📄 *{title}*\n"
        if source:
            message += f"Channel: _{source}_\n"
        if category:
            message += f"Category: _{category}_\n"
        if article_url:
            message += f"[Original Article]({article_url})\n"
        message += f"\n{summary}"

        # Try to send a photo if we have a *valid* thumbnail URL
        if thumbnail_url and self._is_image_url_valid(thumbnail_url):
            payload = {
                "chat_id": self.chat_id,
                "photo": thumbnail_url,
                "caption": message,
                "parse_mode": "Markdown",
            }
            try:
                result = self._post("sendPhoto", payload)
                if result.get("ok"):
                    logger.info(
                        f"✅ Telegram: Summary with photo sent (msg_id={result['result']['message_id']})"
                    )
                    return OutputChannelResult(True, f"Message ID {result['result']['message_id']}")
                else:
                    logger.warning(
                        f"Telegram sendPhoto returned error: {result}. Falling back to text."
                    )
            except Exception as e:
                logger.warning(f"Telegram sendPhoto failed ({e}). Falling back to text.")

        # Fallback – plain text message (no photo)
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }
            result = self._post("sendMessage", payload)
            if result.get("ok"):
                logger.info(
                    f"✅ Telegram: Summary (text‑only) sent (msg_id={result['result']['message_id']})"
                )
                return OutputChannelResult(True, f"Message ID {result['result']['message_id']}")
            else:
                logger.error(f"❌ Telegram sendMessage error: {result}")
                return OutputChannelResult(False, error=str(result))
        except Exception as e:
            logger.error(f"❌ Telegram sendMessage failed: {e}")
            return OutputChannelResult(False, error=str(e))

    def send_overview(self, overview: str, date: str = "") -> OutputChannelResult:
        if not self.is_available():
            return OutputChannelResult(False, error="Telegram not configured")
        try:
            title = "🌍 Daily News Overview"
            if date:
                title += f" - {date}"
            message = f"*{title}*\n\n{overview}"
            # Telegram's max message length is 4096 characters
            if len(message) > 4000:
                # Split into chunks to stay under limit
                chunks = self._split_message(message, 4000)
                for i, chunk in enumerate(chunks):
                    payload = {
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown" if i == 0 else None,
                    }
                    self._post("sendMessage", payload)
                logger.info(f"✅ Telegram: Overview sent in {len(chunks)} chunks")
                return OutputChannelResult(True, f"Sent in {len(chunks)} messages")
            else:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
                result = self._post("sendMessage", payload)
                if result.get("ok"):
                    msg_id = result['result']['message_id']
                    logger.info(f"✅ Telegram: Overview sent (msg_id={msg_id})")
                    return OutputChannelResult(True, f"Message ID {msg_id}")
                else:
                    logger.error(f"❌ Telegram API error: {result}")
                    return OutputChannelResult(False, error=str(result))
        except Exception as e:
            logger.error(f"❌ Telegram overview failed: {e}")
            return OutputChannelResult(False, error=str(e))

    def _split_message(self, text: str, max_len: int) -> List[str]:
        chunks = []
        while len(text) > max_len:
            split_point = text.rfind(" ", 0, max_len)
            if split_point == -1:
                split_point = max_len
            chunks.append(text[:split_point])
            text = text[split_point:].lstrip()
        if text:
            chunks.append(text)
        return chunks


class DiscordOutputChannel(OutputChannel):
    """Sends messages to Discord via webhook or bot token."""

    def __init__(self, config: OutputChannelConfig):
        super().__init__(config)
        self.webhook_url: Optional[str] = config.options.get('webhook_url')
        self.bot_token: Optional[str] = config.options.get('bot_token')
        self.channel_id: Optional[str] = config.options.get('channel_id')
        self.username: str = config.options.get('username', 'News Reader')
        self.avatar_url: Optional[str] = config.options.get('avatar_url')

        if self.webhook_url:
            self.auth_method = 'webhook'
        elif self.bot_token and self.channel_id:
            self.auth_method = 'bot'
            self.api_url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
            self.headers = {'Authorization': f'Bot {self.bot_token}', 'Content-Type': 'application/json'}
        else:
            self.auth_method = None

    def is_available(self) -> bool:
        if self.auth_method == 'webhook':
            return bool(self.webhook_url)
        if self.auth_method == 'bot':
            # Simple sanity check – we will surface errors on send
            return bool(self.bot_token and self.channel_id)
        return False

    def send_summary(
        self,
        title: str,
        summary: str,
        source: str = "",
        category: str = "",
        article_url: str = "",
        thumbnail_url: Optional[str] = None,
    ) -> OutputChannelResult:
        title = _strip_think(title)
        summary = _strip_think(summary)
        if not self.is_available():
            return OutputChannelResult(False, error="Discord not configured")
        try:
            embed = {
                "title": title,
                "description": summary,
                "url": article_url or None,
                "color": 0x3498db,
                "footer": {"text": f"Channel: {source}" if source else "News Reader"},
            }
            if thumbnail_url:
                embed["thumbnail"] = {"url": thumbnail_url}
            if category:
                embed.setdefault('fields', []).append({"name": "Category", "value": category, "inline": True})

            payload = {"embeds": [embed]}
            if self.auth_method == 'webhook':
                payload.update({"username": self.username})
                if self.avatar_url:
                    payload["avatar_url"] = self.avatar_url
                resp = requests.post(self.webhook_url, json=payload, timeout=30)
            else:  # bot token
                resp = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)

            resp.raise_for_status()
            logger.info("✅ Discord: Summary sent successfully")
            return OutputChannelResult(True, "Summary sent to Discord")
        except Exception as e:
            logger.error(f"❌ Discord send failed: {e}")
            return OutputChannelResult(False, error=str(e))

    def send_overview(self, overview: str, date: str = "", sources: list = None) -> OutputChannelResult:
        if not self.is_available():
            return OutputChannelResult(False, error="Discord not configured")
        try:
            title = "🌍 Daily News Overview"
            if date:
                title += f" - {date}"
            
            # Build description with sources
            description = overview
            if sources:
                unique_sources = sorted(list(set(sources)))
                source_line = f"**Sources**: {', '.join(unique_sources)}"
                description = f"{source_line}\n\n{overview}"

            # Discord embed description limit ~4000 chars, split if needed
            if len(description) > 4000:
                chunks = self._split_overview(description, 4000)
                embeds = []
                for i, chunk in enumerate(chunks):
                    embed = {
                        "title": f"{title} (Part {i+1}/{len(chunks)})" if len(chunks) > 1 else title,
                        "description": chunk,
                        "color": 0x2ecc71
                    }
                    embeds.append(embed)
            else:
                embeds = [{"title": title, "description": description, "color": 0x2ecc71}]

            payload = {"embeds": embeds}
            if self.auth_method == 'webhook':
                payload.update({"username": self.username})
                if self.avatar_url:
                    payload["avatar_url"] = self.avatar_url
                resp = requests.post(self.webhook_url, json=payload, timeout=30)
            else:
                resp = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)

            resp.raise_for_status()
            logger.info(f"✅ Discord: Overview sent ({len(embeds)} embed(s))")
            return OutputChannelResult(True, f"Overview sent ({len(embeds)} embed(s))")
        except Exception as e:
            logger.error(f"❌ Discord overview failed: {e}")
            return OutputChannelResult(False, error=str(e))

    def _split_overview(self, text: str, max_len: int) -> List[str]:
        chunks = []
        while len(text) > max_len:
            split_point = text.rfind('\n\n', 0, max_len)
            if split_point == -1:
                split_point = text.rfind('\n', 0, max_len)
            if split_point == -1:
                split_point = max_len
            chunks.append(text[:split_point])
            text = text[split_point:].lstrip()
        if text:
            chunks.append(text)
        return chunks


# ---------------------------------------------------------------------------
# Factory for creating channel instances from config dicts
# ---------------------------------------------------------------------------

class OutputChannelFactory:
    @staticmethod
    def create_channel(config: OutputChannelConfig) -> OutputChannel:
        channel_type = config.channel_type.lower()
        if channel_type == 'console':
            return ConsoleOutputChannel(config)
        if channel_type == 'telegram':
            return TelegramOutputChannel(config)
        if channel_type == 'discord':
            return DiscordOutputChannel(config)
        raise ValueError(f"Unsupported output channel type: {channel_type}")
