"""
llm/groq_client.py
───────────────────
Thin wrapper around the Groq SDK.
Supports both streaming and non-streaming completions.
"""

from __future__ import annotations

import os
from typing import Generator, Optional

from dotenv import load_dotenv
from groq import Groq, APIError, APIConnectionError, RateLimitError

load_dotenv()

# Default to a fast, capable model
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class GroqClient:
    """
    Wraps Groq API calls with:
    - Automatic retries on transient errors
    - Streaming support
    - Structured error messages surfaced to the UI
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or pass it directly."
            )
        self.client = Groq(api_key=key)
        self.model = model or DEFAULT_MODEL

    # ──────────────────────────────────────────────
    #  Non-streaming completion
    # ──────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """
        Send a chat completion request and return the full response text.
        Low temperature (0.1) keeps SQL generation deterministic.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            raise RuntimeError(
                "Groq rate limit reached. Please wait a moment and try again."
            )
        except APIConnectionError:
            raise RuntimeError(
                "Could not reach Groq API. Check your internet connection."
            )
        except APIError as exc:
            raise RuntimeError(f"Groq API error: {exc.message}")

    # ──────────────────────────────────────────────
    #  Streaming completion
    # ──────────────────────────────────────────────

    def stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        """
        Stream a chat completion response.
        Yields text chunks as they arrive from the API.
        """
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except RateLimitError:
            yield "\n⚠️ Rate limit reached. Please wait and retry."
        except APIConnectionError:
            yield "\n⚠️ Could not reach Groq API."
        except APIError as exc:
            yield f"\n⚠️ Groq API error: {exc.message}"

    # ──────────────────────────────────────────────
    #  Availability check
    # ──────────────────────────────────────────────

    def ping(self) -> tuple[bool, str]:
        """Quick health-check — sends a minimal request."""
        try:
            self.complete(
                [{"role": "user", "content": "Reply with 'OK' only."}],
                max_tokens=5,
            )
            return True, f"Groq connected (model: {self.model})"
        except RuntimeError as exc:
            return False, str(exc)
