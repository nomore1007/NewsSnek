import requests
from typing import Protocol, Any
import json

from .config import OutputChannelConfig, OutputChannelResult


class OutputChannel(Protocol):
    """Protocol for output channels."""

    def is_available(self) -> bool:
        """Check if the output channel is available and properly configured."""
        ...

    def send(self, message: str, title: str = "") -> OutputChannelResult:
        """
        Send a message to the output channel.

        Args:
            message: The message content
            title: Optional title for the message

        Returns:
            OutputChannelResult with success status
        """
        ...


class ConsoleOutputChannel:
    """Console output channel for printing to terminal."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize console output channel.

        Args:
            config: Must contain 'output_file' option
        """
        self.output_file = config.options.get('output_file')

    def is_available(self) -> bool:
        """Console is always available."""
        return True

    def send(self, message: str, title: str = "") -> OutputChannelResult:
        """
        Print message to console or file.

        Args:
            message: Message to print
            title: Optional title

        Returns:
            OutputChannelResult with success status
        """
        try:
            output = ""
            if title:
                output += f"{title}\n{'='*len(title)}\n"
            output += f"{message}\n"

            if self.output_file:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(output)
                return OutputChannelResult(success=True, message=f"Written to {self.output_file}")
            else:
                print(output)
                return OutputChannelResult(success=True, message="Printed to console")
        except Exception as e:
            return OutputChannelResult(success=False, error=str(e))

    def send_overview(self, overview: str, date: str) -> OutputChannelResult:
        """
        Send overview to console.

        Args:
            overview: Overview content
            date: Date string

        Returns:
            OutputChannelResult
        """
        title = f"News Overview - {date}"
        return self.send(overview, title)


class DiscordOutputChannel:
    """Discord output channel supporting both webhooks and bot tokens."""

    def __init__(self, config: OutputChannelConfig):
        """
        Initialize Discord output channel.

        Args:
            config: Must contain either 'webhook_url' or 'bot_token' + 'channel_id'
        """
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

    def send(self, message: str, title: str = "") -> OutputChannelResult:
        """
        Send message to Discord via webhook or bot token.

        Args:
            message: Message content
            title: Optional title

        Returns:
            OutputChannelResult with success status
        """
        if not self.is_available():
            return OutputChannelResult(success=False, error="Discord not properly configured")

        try:
            if self.auth_method == 'webhook':
                payload = {
                    "content": f"**{title}**\n\n{message}" if title else message,
                    "username": self.username
                }
                if self.avatar_url:
                    payload["avatar_url"] = self.avatar_url

                response = requests.post(self.webhook_url, json=payload, timeout=30)
                response.raise_for_status()
                return OutputChannelResult(success=True, message="Sent via webhook")

            elif self.auth_method == 'bot':
                embed = {
                    "title": title,
                    "description": message,
                    "color": 3447003  # Blue color
                }
                payload = {"embeds": [embed]}

                response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                return OutputChannelResult(success=True, message="Sent via bot")

        except requests.exceptions.RequestException as e:
            return OutputChannelResult(success=False, error=f"Discord API error: {e}")
        except Exception as e:
            return OutputChannelResult(success=False, error=f"Discord send failed: {e}")

    def send_overview(self, overview: str, date: str) -> OutputChannelResult:
        """
        Send overview to Discord.

        Args:
            overview: Overview content
            date: Date string

        Returns:
            OutputChannelResult
        """
        title = f"Daily News Overview - {date}"
        return self.send(overview, title)


class OutputChannelFactory:
    """Factory for creating output channel instances."""

    @staticmethod
    def create_channel(config: OutputChannelConfig) -> OutputChannel:
        """Create an output channel instance based on configuration."""
        if config.channel_type == 'console':
            return ConsoleOutputChannel(config)
        elif config.channel_type == 'discord':
            return DiscordOutputChannel(config)
        else:
            raise ValueError(f"Unsupported output channel type: {config.channel_type}")