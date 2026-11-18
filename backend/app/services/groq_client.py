"""Minimal, provider-specific HTTP client for Groq chat completions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

import httpx

from app.core.config import Settings, get_settings

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_COMPLETION_TOKENS = 2048
MAX_RESPONSE_BODY_BYTES = 64 * 1024
MAX_ERROR_RESPONSE_BYTES = 8 * 1024
MAX_SAFE_FAILED_GENERATION_LENGTH = 1000
_GENERIC_ERROR_MESSAGE = "Groq rejected the request."
_SAFE_ERROR_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_SAFE_ERROR_PARAMETER = re.compile(r"[A-Za-z0-9_.\[\]-]{1,128}\Z")
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)
_API_TOKEN_PATTERN = re.compile(r"\b(?:gsk_|sk-)[A-Za-z0-9_-]{16,}\b", re.IGNORECASE)
_OPAQUE_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9])")
_CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:api[_ -]?key|client[_ -]?secret|access[_ -]?token|"
    r"refresh[_ -]?token|key|password|passwd|token|secret|credentials?|"
    r"authorization|proxy-authorization|x-api-key)\b"
    r"\s*(?:[:=]\s*['\"]?[^\s,;'\"]+|\bis\s+"
    r"(?!(?:invalid|incorrect|missing|expired|revoked|unset|malformed|unknown|"
    r"unavailable|not|required|valid|disabled|configured|provided)\b)"
    r"['\"]?[^\s,;'\"]+)",
    re.IGNORECASE,
)
_SENSITIVE_FIELD_PATTERN = re.compile(
    r"""["']?(?:api[_ -]?key|client[_ -]?secret|access[_ -]?token|"""
    r"""refresh[_ -]?token|password|passwd|token|secret|credentials?|"""
    r"""authorization|proxy-authorization|x-api-key|cookie|set-cookie)\b"""
    r"""["']?\s*[:=]\s*["']?[^"' \t\r\n,;}]+""",
    re.IGNORECASE,
)
_REQUEST_HEADER_PATTERN = re.compile(
    r"\b(?:authorization|proxy-authorization|content-type|x-api-key|api-key|"
    r"cookie|set-cookie|user-agent|host|accept)\s*:|\bx-[a-z0-9-]+\s*:",
    re.IGNORECASE,
)
_HEADER_BLOCK_PATTERN = re.compile(r"\bheaders?\s*[:=]", re.IGNORECASE)
_HEADER_REFERENCE_PATTERN = re.compile(
    r"\b(?:authorization|proxy-authorization|x-api-key|cookie|set-cookie)\s+header\b",
    re.IGNORECASE,
)
_REQUEST_ECHO_PATTERN = re.compile(
    r"\b(?:echoed\s+prompt|request\s+(?:headers?|body|prompt))\s*[:=]",
    re.IGNORECASE,
)
_PROMPT_CONTENT_PATTERN = re.compile(
    r"\b(?:prompt|shopper\s+message|user\s+message|request\s+body)\b",
    re.IGNORECASE,
)
_ARBITRARY_HEADER_PATTERN = re.compile(
    r"(?m)^[ \t]*[A-Za-z][A-Za-z0-9-]{0,127}[ \t]*:[ \t]*\S"
)
_ERROR_CODE_MESSAGES: Final[dict[str, str]] = {
    "context_length_exceeded": "Groq rejected the request for exceeding model context limits.",
    "insufficient_quota": "Groq reported insufficient account quota.",
    "invalid_api_key": "Groq authentication failed.",
    "invalid_request": "Groq rejected the request as invalid.",
    "invalid_value": "Groq rejected a request parameter value.",
    "json_validate_failed": "Groq failed to validate the request JSON.",
    "model_decommissioned": "Groq reported that the requested model is decommissioned.",
    "model_not_found": "Groq could not find the requested model.",
    "rate_limit_exceeded": "Groq rate limit was reached.",
    "unsupported_parameter": "Groq rejected an unsupported request parameter.",
}
_ERROR_TYPE_MESSAGES: Final[dict[str, str]] = {
    "authentication_error": "Groq authentication failed.",
    "invalid_request_error": "Groq rejected the request as invalid.",
    "not_found_error": "Groq could not find the requested resource.",
    "permission_error": "Groq denied access to the requested resource.",
    "rate_limit_error": "Groq rate limit was reached.",
    "server_error": "Groq reported a server error.",
}
_ERROR_STATUS_MESSAGES: Final[dict[int, str]] = {
    400: "Groq rejected the request.",
    401: "Groq authentication failed.",
    403: "Groq denied access to the requested resource.",
    404: "Groq could not find the requested resource.",
    429: "Groq rate limit was reached.",
}
_REQUEST_FIELD_MESSAGES: Final[dict[str, str]] = {
    "model": "Groq rejected the selected model.",
    "messages": "Groq rejected the messages field.",
    "temperature": "Groq rejected the temperature parameter.",
    "max_tokens": "Groq rejected the max_tokens parameter.",
    "max_completion_tokens": "Groq rejected the max_completion_tokens parameter.",
    "response_format": "Groq rejected the response_format parameter.",
    "reasoning_format": "Groq rejected the reasoning_format parameter.",
    "reasoning_effort": "Groq rejected the reasoning_effort parameter.",
}
_SAFE_PROVIDER_MESSAGE_CLASSIFICATIONS: Final[dict[str, str]] = {
    "failed to validate json.": "Failed to validate JSON.",
}


def _request_field_error_message(
    error: Mapping[str, Any],
    *,
    status_code: int,
    error_type: str | None,
) -> str | None:
    if status_code != 400:
        return None

    param = error.get("param")
    if isinstance(param, str):
        safe_message = _REQUEST_FIELD_MESSAGES.get(param.strip().casefold())
        if safe_message is not None:
            return safe_message
    elif param is not None:
        return None
    if error_type != "invalid_request_error":
        return None

    message = error.get("message")
    if not isinstance(message, str) or len(message) > 2048:
        return None

    field_qualifier = r"(?:request\s+)?(?:parameter|field|argument)"
    rejection = (
        r"(?:unsupported|invalid|unknown|unrecognized|rejected|"
        r"not\s+allowed|not\s+supported)"
    )
    mentioned_fields = [
        field
        for field in _REQUEST_FIELD_MESSAGES
        if re.search(rf"\b{re.escape(field)}\b", message, re.IGNORECASE)
    ]
    incompatible = re.search(
        r"\b(?:incompatible|mutually\s+exclusive)\b"
        r"|\b(?:cannot|can't|must\s+not)\s+(?:be\s+)?(?:used\s+together|combined)\b"
        r"|\b(?:cannot|can't)\s+combine\b",
        message,
        re.IGNORECASE,
    )
    if incompatible and len(mentioned_fields) >= 2:
        return "Groq rejected an incompatible combination of request parameters."

    for field, safe_message in _REQUEST_FIELD_MESSAGES.items():
        field_pattern = rf"['`\"]?\b{re.escape(field)}\b['`\"]?"
        patterns = (
            rf"\b{rejection}\s+{field_qualifier}\s*[:=]?\s*{field_pattern}",
            rf"\b{field_qualifier}\s*[:=]?\s*{field_pattern}\s+(?:is\s+)?{rejection}\b",
            rf"\b{field_pattern}\s+{field_qualifier}\s+(?:is\s+)?{rejection}\b",
            rf"\b(?:invalid|unsupported)\s+(?:value|setting)\s+for\s+"
            rf"(?:(?:the|a)\s+)?{field_qualifier}\s*[:=]?\s*{field_pattern}",
            rf"\b(?:invalid|unsupported)\s+(?:value|setting)\s+for\s+"
            rf"(?:the\s+)?{field_pattern}",
            rf"\b{field_pattern}\s+(?:(?:is|was)\s+)?{rejection}\b",
            rf"\bmodel\s+(?:does\s+not|doesn't)\s+support\s+(?:the\s+)?"
            rf"{field_pattern}(?:\s+{field_qualifier})?",
            rf"\bmodel\s+(?:does\s+not|doesn't)\s+support\s+(?:the\s+)?"
            rf"(?:a\s+)?{field_qualifier}\s*[:=]?\s*{field_pattern}",
        )
        if any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns):
            return safe_message
    if re.search(
        r"\bmodel\b.{0,40}\b(?:not\s+found|does\s+not\s+exist|unavailable|not\s+available)\b",
        message,
        re.IGNORECASE,
    ):
        return _REQUEST_FIELD_MESSAGES["model"]
    return None


def _contains_sensitive_value(value: str) -> bool:
    return any(
        pattern.search(value)
        for pattern in (
            _EMAIL_PATTERN,
            _BEARER_PATTERN,
            _API_TOKEN_PATTERN,
            _OPAQUE_TOKEN_PATTERN,
            _CREDENTIAL_ASSIGNMENT_PATTERN,
            _SENSITIVE_FIELD_PATTERN,
            _REQUEST_HEADER_PATTERN,
            _HEADER_BLOCK_PATTERN,
            _HEADER_REFERENCE_PATTERN,
            _REQUEST_ECHO_PATTERN,
            _PROMPT_CONTENT_PATTERN,
            _ARBITRARY_HEADER_PATTERN,
        )
    )


def _safe_error_value(value: object, *, parameter: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    pattern = _SAFE_ERROR_PARAMETER if parameter else _SAFE_ERROR_IDENTIFIER
    exposes_header = parameter and re.search(
        r"\bheaders?\b|authorization|cookie|x-api-key",
        normalized,
        re.IGNORECASE,
    )
    if (
        not pattern.fullmatch(normalized)
        or _contains_sensitive_value(normalized)
        or exposes_header
    ):
        return None
    return normalized


def _is_allowlisted_error_parameter(value: str) -> bool:
    if value in _REQUEST_FIELD_MESSAGES:
        return True
    known_fields = "|".join(re.escape(field) for field in _REQUEST_FIELD_MESSAGES)
    return bool(
        re.fullmatch(rf"body\.(?:{known_fields})", value)
        or re.fullmatch(r"messages\[\d{1,3}\]\.(?:role|content)", value)
    )


def _has_disallowed_characters(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return any(
        ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F
        for character in value
    )


def _is_unsafe_provider_message(value: object) -> bool:
    return (
        not isinstance(value, str)
        or not value.strip()
        or _has_disallowed_characters(value)
        or _contains_sensitive_value(value)
    )


def _sanitize_failed_generation(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_SAFE_FAILED_GENERATION_LENGTH:
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if any(
        (ord(character) < 0x20 and character not in "\t\n\r")
        or 0x7F <= ord(character) <= 0x9F
        for character in value
    ):
        return None

    generation = re.sub(r"\s+", " ", value).strip()
    if not generation or _contains_sensitive_value(generation):
        return None
    return generation


def _fallback_error_message(
    *,
    error_param: str | None,
    error_code: str | None,
    error_type: str | None,
    status_code: int,
) -> str | None:
    safe_message = _request_field_error_message(
        {"param": error_param} if error_param is not None else {},
        status_code=status_code,
        error_type=error_type,
    )
    if safe_message is None and error_code:
        safe_message = _ERROR_CODE_MESSAGES.get(error_code)
    if safe_message is None and error_type is not None:
        safe_message = _ERROR_TYPE_MESSAGES.get(error_type)
    if safe_message is None:
        safe_message = _ERROR_STATUS_MESSAGES.get(status_code)
    return safe_message


def _read_safe_error_details(
    response: httpx.Response,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_ERROR_RESPONSE_BYTES:
                return None, None, None, None, None
        except ValueError:
            pass

    body = bytearray()
    try:
        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > MAX_ERROR_RESPONSE_BYTES:
                return None, None, None, None, None
            body.extend(chunk)
    except httpx.RequestError:
        return None, None, None, None, None

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None, None, None, None, None

    if not isinstance(payload, Mapping):
        return None, None, None, None, None
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None, None, None, None, None

    error_type = _safe_error_value(error.get("type"))
    if error_type is not None:
        error_type = error_type.casefold()
        if error_type not in _ERROR_TYPE_MESSAGES:
            error_type = None
    error_code = _safe_error_value(error.get("code"))
    if error_code is not None:
        error_code = error_code.casefold()
        if error_code not in _ERROR_CODE_MESSAGES:
            error_code = None
    error_param = _safe_error_value(
        error.get("param", error.get("parameter")),
        parameter=True,
    )
    if error_param is not None:
        error_param = error_param.casefold()
        if not _is_allowlisted_error_parameter(error_param):
            error_param = None
    failed_generation = _sanitize_failed_generation(error.get("failed_generation"))

    provider_message = error.get("message")
    if "message" in error and _is_unsafe_provider_message(provider_message):
        safe_message = _GENERIC_ERROR_MESSAGE
    else:
        safe_message = _request_field_error_message(
            error,
            status_code=response.status_code,
            error_type=error_type,
        )
        if safe_message is None and isinstance(provider_message, str):
            safe_message = _SAFE_PROVIDER_MESSAGE_CLASSIFICATIONS.get(
                provider_message.strip().casefold()
            )
    if safe_message is None:
        safe_message = _fallback_error_message(
            error_param=error_param,
            error_code=error_code,
            error_type=error_type,
            status_code=response.status_code,
        )
    return error_type, error_code, error_param, safe_message, failed_generation


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

    def __init__(
        self,
        message: str = "Groq rate limit was reached.",
        *,
        error_type: str | None = None,
        error_code: str | None = None,
        error_param: str | None = None,
        safe_message: str | None = None,
        failed_generation: str | None = None,
    ) -> None:
        self.status_code = 429
        self.error_type = error_type
        self.error_code = error_code
        self.error_param = error_param
        self.safe_message = safe_message
        self.failed_generation = failed_generation
        super().__init__(message)


class GroqHTTPError(GroqClientError):
    """Raised for other unsuccessful Groq HTTP responses."""

    def __init__(
        self,
        status_code: int,
        *,
        error_type: str | None = None,
        error_code: str | None = None,
        error_param: str | None = None,
        safe_message: str | None = None,
        failed_generation: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.error_code = error_code
        self.error_param = error_param
        self.safe_message = safe_message
        self.failed_generation = failed_generation
        super().__init__(f"Groq returned HTTP status {status_code}.")


def groq_http_status_message(
    error: GroqHTTPError | GroqRateLimitError,
    *,
    include_failed_generation: bool = False,
) -> str:
    """Return a diagnostic without including failed-generation content.

    The keyword is retained for compatibility but does not enable generation output.
    """
    descriptions: Final[dict[int, str]] = {
        401: "unauthorized",
        403: "forbidden",
        404: "not found",
        429: "rate limited",
    }
    description = descriptions.get(error.status_code)
    if description is not None:
        diagnostic = f"Groq returned HTTP {error.status_code} ({description})"
    else:
        diagnostic = f"Groq returned HTTP {error.status_code}"

    classifications = []
    if error.error_type is not None:
        classifications.append(f"type={error.error_type}")
    if error.error_code is not None:
        classifications.append(f"code={error.error_code}")
    if error.error_param is not None:
        classifications.append(f"param={error.error_param}")
    if classifications:
        diagnostic += f" ({', '.join(classifications)})"
    if error.safe_message is not None:
        diagnostic += f": {error.safe_message}"
    return diagnostic


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
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "response_format": {"type": "json_object"},
        }
        if model == "openai/gpt-oss-20b":
            request_body["reasoning_effort"] = "low"
            request_body["include_reasoning"] = False
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        transport_error: GroqClientError | None = None
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
                    if response.status_code >= 400:
                        (
                            error_type,
                            error_code,
                            error_param,
                            safe_message,
                            failed_generation,
                        ) = (
                            _read_safe_error_details(response)
                        )
                    else:
                        (
                            error_type,
                            error_code,
                            error_param,
                            safe_message,
                            failed_generation,
                        ) = (
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                    if response.status_code == 429:
                        raise GroqRateLimitError(
                            error_type=error_type,
                            error_code=error_code,
                            error_param=error_param,
                            safe_message=safe_message,
                            failed_generation=failed_generation,
                        )
                    if not 200 <= response.status_code < 300:
                        raise GroqHTTPError(
                            response.status_code,
                            error_type=error_type,
                            error_code=error_code,
                            error_param=error_param,
                            safe_message=safe_message,
                            failed_generation=failed_generation,
                        )

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
            transport_error = GroqTimeoutError("Groq request timed out.")
        except httpx.RequestError:
            transport_error = GroqNetworkError(
                "Groq request failed due to a network error."
            )
        if transport_error is not None:
            raise transport_error

        try:
            payload = json.loads(response_body)
        except (ValueError, UnicodeDecodeError, RecursionError):
            payload = None
            invalid_json = True
        else:
            invalid_json = False
        if invalid_json:
            raise GroqInvalidResponseError("Groq returned invalid JSON.")

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise GroqInvalidResponseError("Groq returned an unexpected response shape.") from None
        if not isinstance(content, str):
            raise GroqInvalidResponseError("Groq returned non-text message content.")
        return content
