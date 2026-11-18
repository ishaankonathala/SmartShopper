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
    MAX_ERROR_RESPONSE_BYTES,
    MAX_RESPONSE_BODY_BYTES,
    MAX_SAFE_FAILED_GENERATION_LENGTH,
    REQUEST_TIMEOUT_SECONDS,
    groq_http_status_message,
)

TEST_API_KEY = "test-groq-key-never-log"


def _client(
    handler,
    *,
    api_key: str | None = TEST_API_KEY,
    model: str = "test-model",
) -> GroqClient:
    settings = Settings(groq_api_key=api_key, groq_model=model)
    return GroqClient(settings=settings, transport=httpx.MockTransport(handler))


def _nested_json(depth: int = 1500) -> str:
    return "[" * depth + "0" + "]" * depth


def test_groq_client_sends_json_mode_request_over_https() -> None:
    content = '{"category":"Headphones"}'

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GROQ_CHAT_COMPLETIONS_URL
        assert request.url.scheme == "https"
        assert request.headers["authorization"] == f"Bearer {TEST_API_KEY}"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["temperature"] == 0
        assert body["max_completion_tokens"] == MAX_COMPLETION_TOKENS == 2048
        assert "max_tokens" not in body
        assert body["response_format"] == {"type": "json_object"}
        assert "reasoning_effort" not in body
        assert "include_reasoning" not in body
        assert request.extensions["timeout"]["read"] == REQUEST_TIMEOUT_SECONDS
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    result = _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert result == content


def test_groq_client_limits_gpt_oss_reasoning_and_returns_only_final_content() -> None:
    content = '{"category":"Headphones"}'

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-20b"
        assert body["max_completion_tokens"] == 2048
        assert body["reasoning_effort"] == "low"
        assert body["include_reasoning"] is False
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    result = _client(handler, model="openai/gpt-oss-20b").complete_json(
        [{"role": "user", "content": "Headphones"}]
    )

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
    assert error.value.__context__ is None
    assert error.value.__cause__ is None


def test_groq_client_maps_network_errors_to_sanitized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(GroqNetworkError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert TEST_API_KEY not in str(error.value)
    assert error.value.__context__ is None
    assert error.value.__cause__ is None


def test_groq_client_maps_rate_limit_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                    "message": "provider-private-detail",
                }
            },
        )

    with pytest.raises(GroqRateLimitError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 429
    assert error.value.error_type == "rate_limit_error"
    assert error.value.error_code == "rate_limit_exceeded"
    assert error.value.error_param is None
    assert error.value.safe_message == "Groq rate limit was reached."
    assert groq_http_status_message(error.value) == (
        "Groq returned HTTP 429 (rate limited) "
        "(type=rate_limit_error, code=rate_limit_exceeded): Groq rate limit was reached."
    )
    assert "provider-private-detail" not in str(error.value)


@pytest.mark.parametrize("status_code", [401, 403, 404, 500, 503])
def test_groq_client_preserves_other_http_status_without_exposing_response_body(
    status_code: int,
) -> None:
    provider_detail = "provider-private-detail"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=provider_detail)

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == status_code
    assert str(status_code) in str(error.value)
    assert provider_detail not in str(error.value)
    assert TEST_API_KEY not in str(error.value)


def test_groq_client_redacts_sensitive_provider_message() -> None:
    provider_message = (
        "Unsupported parameter max_tokens; echoed prompt: buy a laptop; "
        "authorization: Bearer provider-secret"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "unsupported_parameter",
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.error_type == "invalid_request_error"
    assert error.value.error_code == "unsupported_parameter"
    assert error.value.safe_message == "Groq rejected the request."
    diagnostic = groq_http_status_message(error.value)
    assert diagnostic == (
        "Groq returned HTTP 400 (type=invalid_request_error, "
        "code=unsupported_parameter): Groq rejected the request."
    )
    assert provider_message not in diagnostic
    assert "buy a laptop" not in diagnostic
    assert "provider-secret" not in diagnostic
    assert TEST_API_KEY not in diagnostic


def test_groq_client_uses_allowlisted_classification_for_secret_bearing_message() -> None:
    provider_message = (
        "Invalid request; api_key=gsk_sensitiveproviderkey123456789; "
        "password=hunter2; contact shopper@example.test; "
        "request headers: Authorization: Bearer provider-bearer-secret"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_value",
                    "param": "messages[0].content",
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.error_type == "invalid_request_error"
    assert error.value.error_code == "invalid_value"
    assert error.value.error_param == "messages[0].content"
    assert error.value.safe_message == "Groq rejected the request."
    assert provider_message not in diagnostic
    for sensitive_value in (
        "gsk_sensitiveproviderkey123456789",
        "hunter2",
        "shopper@example.test",
        "provider-bearer-secret",
        "Authorization",
    ):
        assert sensitive_value not in diagnostic
    assert "Groq rejected the request." in diagnostic
    assert provider_message not in str(error.value)


@pytest.mark.parametrize(
    "provider_message",
    [
        "Request rejected for prompt: Headphones under $500",
        "Provider echoed prompt text: shopper asks for a red laptop",
        "Referer: https://internal.example/path",
        "Origin: https://private.example",
        "Authorization: Bearer provider-secret-value",
        "X-Custom-Metadata: internal-value",
        "Custom-Trace-Header: private-header-value",
        "Request body: {\"shopper_message\":\"private prompt\"}",
    ],
)
def test_groq_client_never_echoes_provider_messages_or_headers(
    provider_message: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_request",
                    "param": provider_message,
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Private shopper prompt"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.error_param is None
    assert diagnostic.endswith(": Groq rejected the request.")
    assert provider_message not in diagnostic
    assert "param=" not in diagnostic
    assert "Private shopper prompt" not in diagnostic
    assert "provider-secret-value" not in diagnostic
    assert "internal-value" not in diagnostic
    assert "private-header-value" not in diagnostic


def test_groq_client_classifies_ordinary_api_key_error_without_echoing_it() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": {
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                    "message": "API key is invalid",
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.safe_message == "Groq authentication failed."
    assert "API key is invalid" not in diagnostic
    assert "invalid_api_key" in diagnostic
    assert diagnostic.endswith(": Groq authentication failed.")


def test_groq_client_does_not_echo_oversized_provider_message() -> None:
    provider_message = "Invalid request: " + "invalid-field " * 40

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": provider_message}},
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.safe_message == "Groq rejected the request."
    assert provider_message not in groq_http_status_message(error.value)


def test_groq_client_preserves_safe_failed_generation() -> None:
    failed_generation = '{"category":"Headphones","comfort_priority":"high"}'

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "param": "messages",
                    "message": "Failed to validate JSON.",
                    "failed_generation": failed_generation,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.error_type == "invalid_request_error"
    assert error.value.error_code == "json_validate_failed"
    assert error.value.error_param == "messages"
    assert error.value.safe_message == "Groq rejected the messages field."
    assert error.value.failed_generation == failed_generation
    default_diagnostic = groq_http_status_message(error.value)
    assert "failed_generation=" not in default_diagnostic
    explicit_opt_in_diagnostic = groq_http_status_message(
        error.value,
        include_failed_generation=True,
    )
    assert explicit_opt_in_diagnostic == default_diagnostic
    assert failed_generation not in explicit_opt_in_diagnostic
    assert "failed_generation" not in str(error.value)


def test_groq_client_handles_missing_failed_generation() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "message": "Failed to validate JSON.",
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.failed_generation is None
    assert "failed_generation=" not in groq_http_status_message(error.value)


@pytest.mark.parametrize(
    "failed_generation",
    [None, 42, [], {"partial": "json"}, "invalid\x01output", "\ud800"],
)
def test_groq_client_ignores_malformed_failed_generation_values(
    failed_generation: object,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        body = json.dumps(
            {
                "error": {
                    "message": "Failed to validate JSON.",
                    "failed_generation": failed_generation,
                }
            }
        )
        return httpx.Response(
            400,
            content=body.encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.safe_message == "Failed to validate JSON."
    assert error.value.failed_generation is None
    assert "failed_generation=" not in groq_http_status_message(error.value)


def test_groq_client_omits_oversized_failed_generation() -> None:
    failed_generation = "x" * (MAX_SAFE_FAILED_GENERATION_LENGTH + 1)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Failed to validate JSON.",
                    "failed_generation": failed_generation,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.failed_generation is None
    assert "failed_generation=" not in groq_http_status_message(error.value)


def test_groq_client_redacts_sensitive_failed_generation() -> None:
    failed_generation = (
        '{"client_secret":"client-secret-value",'
        '"authorization":"Bearer provider-bearer-secret",'
        '"cookie":"session=private-cookie",'
        '"email":"shopper@example.test",'
        '"api_key":"gsk_sensitiveproviderkey123456789"}'
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Failed to validate JSON.",
                    "failed_generation": failed_generation,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.status_code == 400
    assert error.value.failed_generation is None
    assert failed_generation not in diagnostic
    for sensitive_value in (
        "client-secret-value",
        "provider-bearer-secret",
        "private-cookie",
        "shopper@example.test",
        "gsk_sensitiveproviderkey123456789",
    ):
        assert sensitive_value not in diagnostic


@pytest.mark.parametrize(
    "failed_generation",
    [
        "Request rejected for prompt: private shopper text",
        "Referer: https://internal.example/path",
        "Custom-Trace-Header: private-header-value",
        "Provider error: Custom-Trace-Header: private-header-value",
        "Provider error: Referer: https://internal.example/path",
        "Provider error: Origin: https://private.example",
        "Provider error: The echoed shopper prompt is Headphones under $500",
    ],
)
def test_groq_client_rejects_prompt_echoes_and_headers_in_opt_in_generation(
    failed_generation: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Failed to validate JSON.",
                    "failed_generation": failed_generation,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(
        error.value,
        include_failed_generation=True,
    )
    assert "failed_generation=" not in diagnostic
    assert failed_generation not in diagnostic
    for sensitive_value in (
        "private-header-value",
        "https://internal.example/path",
        "https://private.example",
        "Headphones under $500",
    ):
        assert sensitive_value not in diagnostic


@pytest.mark.parametrize(
    ("param", "expected_message"),
    [
        ("model", "Groq rejected the selected model."),
        ("messages", "Groq rejected the messages field."),
        ("temperature", "Groq rejected the temperature parameter."),
        ("max_tokens", "Groq rejected the max_tokens parameter."),
        ("max_completion_tokens", "Groq rejected the max_completion_tokens parameter."),
        ("response_format", "Groq rejected the response_format parameter."),
        ("reasoning_format", "Groq rejected the reasoning_format parameter."),
        ("reasoning_effort", "Groq rejected the reasoning_effort parameter."),
    ],
)
def test_groq_client_classifies_allowlisted_error_param(
    param: str,
    expected_message: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"type": "invalid_request_error", "param": param}},
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.error_param == param
    assert error.value.safe_message == expected_message
    assert groq_http_status_message(error.value).endswith(f": {expected_message}")


def test_groq_client_classifies_field_from_rejection_message_without_echoing_it() -> None:
    provider_message = (
        "The max_tokens parameter is not supported; "
        "request prompt: buy a laptop; api key: provider-secret"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert diagnostic.endswith(": Groq rejected the request.")
    assert provider_message not in diagnostic
    assert "buy a laptop" not in diagnostic
    assert "provider-secret" not in diagnostic


@pytest.mark.parametrize(
    ("provider_message", "expected_message"),
    [
        (
            "Unsupported parameter 'max_tokens'.",
            "Groq rejected the max_tokens parameter.",
        ),
        (
            "Unrecognized request argument: 'temperature'.",
            "Groq rejected the temperature parameter.",
        ),
        (
            "The 'response_format' parameter is not allowed.",
            "Groq rejected the response_format parameter.",
        ),
        (
            "The model does not support a parameter: 'reasoning_effort'.",
            "Groq rejected the reasoning_effort parameter.",
        ),
        (
            "Invalid value for the parameter 'max_completion_tokens'.",
            "Groq rejected the max_completion_tokens parameter.",
        ),
        (
            "The response_format and reasoning_format parameters are incompatible.",
            "Groq rejected an incompatible combination of request parameters.",
        ),
    ],
)
def test_groq_client_classifies_common_provider_wording(
    provider_message: str,
    expected_message: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.safe_message == expected_message
    assert diagnostic.endswith(f": {expected_message}")
    assert provider_message not in diagnostic


def test_groq_client_does_not_echo_unknown_request_field_message() -> None:
    provider_message = "Unsupported parameter 'private_payload_field'."

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "message": provider_message,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.safe_message == "Groq rejected the request as invalid."
    assert diagnostic.endswith(": Groq rejected the request as invalid.")
    assert provider_message not in diagnostic


def test_groq_client_uses_recognized_message_when_param_is_unknown() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "unsupported_parameter",
                    "param": "body.max_tokens",
                    "message": "Unsupported parameter: max_tokens",
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    diagnostic = groq_http_status_message(error.value)
    assert error.value.error_param == "body.max_tokens"
    assert diagnostic.endswith(": Groq rejected the max_tokens parameter.")
    assert "param=body.max_tokens" in diagnostic


def test_groq_client_omits_unallowlisted_error_fields() -> None:
    provider_detail = "provider-private-detail"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "unrecognized-type",
                    "code": "unrecognized-code",
                    "param": "messages[0].content",
                    "message": provider_detail,
                }
            },
        )

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.error_type is None
    assert error.value.error_code is None
    assert error.value.error_param == "messages[0].content"
    assert error.value.safe_message == "Groq rejected the request."
    diagnostic = groq_http_status_message(error.value)
    assert diagnostic == (
        "Groq returned HTTP 400 (param=messages[0].content): Groq rejected the request."
    )


def test_groq_client_uses_status_only_for_malformed_error_json() -> None:
    provider_detail = "not-json-provider-detail"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=provider_detail)

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.error_type is None
    assert error.value.error_code is None
    assert error.value.safe_message is None
    assert groq_http_status_message(error.value) == "Groq returned HTTP 400"
    assert provider_detail not in str(error.value)


def test_groq_client_omits_details_from_oversized_error_bodies() -> None:
    provider_detail = "provider-private-detail"

    def handler(_request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "error": {
                    "type": "unrecognized-type",
                    "code": "unrecognized-code",
                    "message": provider_detail,
                }
            }
        )
        content += " " * MAX_ERROR_RESPONSE_BYTES
        return httpx.Response(400, content=content)

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.error_type is None
    assert error.value.error_code is None
    assert error.value.safe_message is None
    diagnostic = groq_http_status_message(error.value)
    assert diagnostic == "Groq returned HTTP 400"
    assert provider_detail not in diagnostic


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": "not-an-array"}),
        httpx.Response(200, json={"choices": [{}]}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
        httpx.Response(200, json={"choices": [{"message": ["unexpected"]}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    ],
)
def test_groq_client_rejects_invalid_provider_responses(response: httpx.Response) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(GroqInvalidResponseError):
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])


def test_groq_client_returns_non_json_string_content_for_schema_validation() -> None:
    provider_content = "not JSON"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": provider_content}}]},
        )

    result = _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert result == provider_content


def test_groq_client_handles_deeply_nested_success_json_safely() -> None:
    body = (
        '{"extra":'
        + _nested_json()
        + ',"choices":[{"message":{"content":"{}"}}]}'
    )
    assert len(body.encode()) <= MAX_RESPONSE_BODY_BYTES

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(GroqInvalidResponseError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert str(error.value) == "Groq returned invalid JSON."
    assert body not in str(error.value)
    assert error.value.__context__ is None


def test_groq_client_handles_deeply_nested_error_json_with_status_only() -> None:
    body = '{"error":' + _nested_json() + "}"
    assert len(body.encode()) <= MAX_ERROR_RESPONSE_BYTES

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=body)

    with pytest.raises(GroqHTTPError) as error:
        _client(handler).complete_json([{"role": "user", "content": "Headphones"}])

    assert error.value.status_code == 400
    assert error.value.safe_message is None
    assert groq_http_status_message(error.value) == "Groq returned HTTP 400"
    assert body not in str(error.value)


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
