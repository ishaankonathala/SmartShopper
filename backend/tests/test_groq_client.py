"""Groq HTTP client tests using only mocked HTTP transports."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.services.groq_client import (
    GROQ_CHAT_COMPLETIONS_URL,
    GroqAPIKeyMissingError,
    GroqClient,
    GroqHTTPError,
    GroqInvalidResponseError,
    GroqNetworkError,
    GroqRateLimitError,
    GroqTimeoutError,
    MAX_COMPLETION_TOKENS,
    MAX_RESPONSE_BODY_BYTES,
    REQUEST_TIMEOUT_SECONDS,
)

TEST_API_KEY = "test-groq-key-never-log"


def _client(
    handler,
    *,
    api_key: str | None = TEST_API_KEY,
) -> GroqClient:
    settings = Settings(groq_api_key=api_key, groq_model="test-model")
    return GroqClient(settings=settings, transport=httpx.MockTransport(handler))


def test_groq_client_sends_json_mode_request_over_https() -> None:
    content = '{"category":"Headphones"}'

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GROQ_CHAT_COMPLETIONS_URL
        assert request.url.scheme == "https"
        assert request.headers["authorization"] == f"Bearer {TEST_API_KEY}"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["temperature"] == 0
        assert body["max_tokens"] == MAX_COMPLETION_TOKENS
        assert body["response_format"] == {"type": "json_object"}
        assert request.extensions["timeout"]["read"] == REQUEST_TIMEOUT_SECONDS
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    result = _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert result == content


def test_groq_client_rejects_missing_api_key_without_request() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("A request must not be sent without an API key.")

    client = _client(handler, api_key=None)

    with pytest.raises(GroqAPIKeyMissingError):
        client.complete_json([{"role": "user", "content": "Headphones"}])


def test_groq_client_maps_timeout_to_sanitized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out", request=request)

    with pytest.raises(GroqTimeoutError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert TEST_API_KEY not in str(error.value)


def test_groq_client_maps_network_errors_to_sanitized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(GroqNetworkError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert TEST_API_KEY not in str(error.value)


def test_groq_client_maps_rate_limit_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with pytest.raises(GroqRateLimitError):
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])


def test_groq_client_maps_other_http_errors_without_exposing_response_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="provider detail")

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 503
    assert "provider detail" not in str(error.value)
    assert TEST_API_KEY not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    ],
)
def test_groq_client_rejects_invalid_provider_responses(response: httpx.Response) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(GroqInvalidResponseError):
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"content-length": "1"},
    ],
)
def test_groq_client_rejects_oversized_response_body_safely(headers: dict[str, str]) -> None:
    provider_detail = "provider-private-detail"
    content = (provider_detail * (MAX_RESPONSE_BODY_BYTES // len(provider_detail) + 1)).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers=headers)

    with pytest.raises(GroqInvalidResponseError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert "allowed size" in str(error.value)
    assert provider_detail not in str(error.value)
    assert TEST_API_KEY not in str(error.value)
