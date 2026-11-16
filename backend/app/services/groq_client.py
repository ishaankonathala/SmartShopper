"""Minimal, provider-specific HTTP client for Groq chat completions."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.core.config import Settings, get_settings

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_COMPLETION_TOKENS = 256
MAX_RESPONSE_BODY_BYTES = 64 * 1024


class GroqClientError(Exception):
    """Base class for sanitized Groq client failures."""


class GroqAPIKeyMissingError(GroqClientError):
    """Raised when no Groq API key is configured."""


class GroqTimeoutError(GroqClientError):
    """Raised when the Groq request exceeds its timeout."""


class GroqNetworkError(GroqClientError):
    """Raised when the Groq endpoint cannot be reached."""


class GroqRateLimitError(GroqClientError):
    """Raised when Groq returns a rate-limit response."""


class GroqHTTPError(GroqClientError):
    """Raised for other unsuccessful Groq HTTP responses."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Groq returned HTTP status {status_code}.")


class GroqInvalidResponseError(GroqClientError):
    """Raised when Groq returns a malformed or unexpected response."""


class GroqClient:
    """Perform one JSON-mode request using the configured Groq model."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    def complete_json(self, messages: Sequence[Mapping[str, str]]) -> str:
        """Return the assistant message content from a JSON-mode completion."""
        api_key = (self._settings.groq_api_key or "").strip()
        if not api_key:
            raise GroqAPIKeyMissingError("Groq API key is not configured.")

        model = self._settings.groq_model.strip()
        if not model:
            raise GroqInvalidResponseError("Groq model is not configured.")

        request_body: dict[str, Any] = {
            "model": model,
            "messages": [dict(message) for message in messages],
            "temperature": 0,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(
                timeout=REQUEST_TIMEOUT_SECONDS,
                transport=self._transport,
            ) as client:
                response_context = client.stream(
                    "POST",
                    GROQ_CHAT_COMPLETIONS_URL,
                    headers=headers,
                    json=request_body,
                )
                with response_context as response:
                    if response.status_code == 429:
                        raise GroqRateLimitError("Groq rate limit was reached.")
                    if not 200 <= response.status_code < 300:
                        raise GroqHTTPError(response.status_code)

                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_length = int(content_length)
                        except ValueError:
                            declared_length = None
                        if (
                            declared_length is not None
                            and declared_length > MAX_RESPONSE_BODY_BYTES
                        ):
                            raise GroqInvalidResponseError(
                                "Groq response exceeded the allowed size."
                            )

                    response_body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(response_body) + len(chunk) > MAX_RESPONSE_BODY_BYTES:
                            raise GroqInvalidResponseError(
                                "Groq response exceeded the allowed size."
                            )
                        response_body.extend(chunk)
        except httpx.TimeoutException:
            raise GroqTimeoutError("Groq request timed out.") from None
        except httpx.RequestError:
            raise GroqNetworkError("Groq request failed due to a network error.") from None

        try:
            payload = json.loads(response_body)
        except (ValueError, UnicodeDecodeError):
            raise GroqInvalidResponseError("Groq returned invalid JSON.") from None

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise GroqInvalidResponseError("Groq returned an unexpected response shape.") from None
        if not isinstance(content, str):
            raise GroqInvalidResponseError("Groq returned non-text message content.")
        return content
