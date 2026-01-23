import requests
from urllib.parse import urlparse
from typing import Protocol
import json

from .config import SummarizerConfig, SummarizerResult


class Summarizer(Protocol):
    """Protocol for text summarization providers."""

    def is_available(self) -> bool:
        """Check if the summarizer is available and properly configured."""
        ...

    def summarize(self, text: str, prompt: str = "Summarize this text:") -> SummarizerResult:
        """
        Summarize the given text using the specified prompt.

        Args:
            text: The text to summarize
            prompt: The summarization prompt

        Returns:
            SummarizerResult with the summary or error
        """
        ...


class OllamaSummarizer:
    """Ollama-based text summarizer."""

    def __init__(self, config: SummarizerConfig):
        """
        Initialize Ollama summarizer.

        Args:
            config: Must contain 'host', 'model', and 'timeout' options
        """
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
        except Exception as e:
            error_msg = f"❌ Ollama summarization failed: {e}"
            print(error_msg)
            return SummarizerResult(success=False, error=error_msg)

    def detect_language(self, text: str) -> str:
        """Detect the language of the text."""
        try:
            from langdetect import detect
            return detect(text)
        except ImportError:
            return 'unknown'

    def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language."""
        try:
            from googletrans import Translator
            translator = Translator()
            result = translator.translate(text, dest=target_language)
            return result.text
        except ImportError:
            print("⚠️ Translation not available (googletrans not installed)")
            return text
        except Exception as e:
            print(f"⚠️ Translation failed: {e}")
            return text


class SummarizerFactory:
    """Factory for creating summarizer instances."""

    @staticmethod
    def create_summarizer(config: SummarizerConfig) -> Summarizer:
        """Create a summarizer instance based on configuration."""
        if config.provider_type == 'ollama':
            return OllamaSummarizer(config)
        else:
            raise ValueError(f"Unsupported summarizer provider: {config.provider_type}")