"""Compare Groq responses to production intent messages with two system roles."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings
from app.services.assistant_intent import _deterministic_intent, extract_assistant_intent
from app.services.groq_client import (
    GroqAPIKeyMissingError,
    GroqClient,
    GroqClientError,
    GroqHTTPError,
    GroqInvalidResponseError,
    GroqNetworkError,
    GroqRateLimitError,
    GroqTimeoutError,
)

HARMLESS_REQUEST = "I need comfortable headphones under 5000 rupees"


class _IntentCaptureClient(GroqClient):
    def __init__(self, intent_json: str) -> None:
        self.intent_json = intent_json
        self.messages: list[dict[str, str]] | None = None

    def complete_json(self, messages: Sequence[Mapping[str, str]]) -> str:
        self.messages = [dict(message) for message in messages]
        return self.intent_json


class _RequestObserver:
    status_code: int | None = None


class _StatusClient(httpx.Client):
    observer: _RequestObserver | None = None

    def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        response = super().send(request, **kwargs)
        observer = type(self).observer
        if observer is not None:
            observer.status_code = response.status_code
        return response


def _production_intent_messages() -> list[dict[str, str]]:
    intent, _ = _deterministic_intent(HARMLESS_REQUEST)
    capture_client = _IntentCaptureClient(intent.model_dump_json())
    extract_assistant_intent(
        HARMLESS_REQUEST,
        groq_client=capture_client,
    )
    messages = capture_client.messages
    if messages is None or len(messages) < 2 or messages[0].get("role") != "system":
        raise RuntimeError("Could not capture production intent messages.")
    if messages[1].get("role") != "user":
        raise RuntimeError("Production intent messages did not contain a user message.")
    return messages


def _error_fields(error: GroqClientError) -> tuple[str | None, str | None]:
    if isinstance(error, (GroqHTTPError, GroqRateLimitError)):
        return error.error_type, error.error_code
    if isinstance(error, GroqTimeoutError):
        return "timeout", None
    if isinstance(error, GroqNetworkError):
        return "network_error", None
    if isinstance(error, GroqAPIKeyMissingError):
        return "configuration_error", None
    if isinstance(error, GroqInvalidResponseError):
        return "invalid_response", None
    return "client_error", None


def _run_test(
    label: str,
    messages: Sequence[Mapping[str, str]],
    settings: Settings,
) -> None:
    observer = _RequestObserver()
    _StatusClient.observer = observer
    succeeded = False
    error_type: str | None = None
    error_code: str | None = None
    status_code: int | None = None

    try:
        with patch.object(httpx, "Client", _StatusClient):
            GroqClient(settings=settings).complete_json(messages)
        succeeded = True
    except (GroqHTTPError, GroqRateLimitError) as error:
        status_code = error.status_code
        error_type, error_code = _error_fields(error)
    except (
        GroqTimeoutError,
        GroqNetworkError,
        GroqAPIKeyMissingError,
        GroqInvalidResponseError,
    ) as error:
        status_code = observer.status_code
        error_type, error_code = _error_fields(error)
    except GroqClientError as error:
        status_code = observer.status_code
        error_type, error_code = _error_fields(error)
    else:
        status_code = observer.status_code
    finally:
        _StatusClient.observer = None

    roles = ",".join(
        message["role"]
        if message.get("role") in {"system", "developer", "user", "assistant", "tool"}
        else "other"
        for message in messages
    )
    print(
        f"{label} | HTTP status={status_code if status_code is not None else 'N/A'} "
        f"| result={'success' if succeeded else 'failure'} "
        f"| error_type={error_type or 'none'} "
        f"| error_code={error_code or 'none'} "
        f"| message_roles={roles}"
    )


def main() -> int:
    settings = get_settings()
    production_messages = _production_intent_messages()
    test_a = [dict(message) for message in production_messages]
    test_b = [dict(message) for message in production_messages]
    test_b[0]["role"] = "developer"

    _run_test("Test A", test_a, settings)
    _run_test("Test B", test_b, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
