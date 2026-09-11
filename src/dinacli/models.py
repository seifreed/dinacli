"""Core Dinahosting response types and errors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

SUCCESS_CODES = frozenset({1000, 1001})


@dataclass(frozen=True)
class CommandSpec:
    """A documented command and its accepted parameter names."""

    name: str
    required: frozenset[str]
    optional: frozenset[str]

    @property
    def parameters(self) -> frozenset[str]:
        """Return every documented parameter accepted by the command."""
        return self.required | self.optional


class DinaError(Exception):
    """Base error raised by the client."""


class DinaConfigurationError(DinaError):
    """Credentials or configuration are missing or malformed."""


class DinaConnectionError(DinaError):
    """The API endpoint could not be reached."""


class DinaProtocolError(DinaError):
    """The API returned a response that is not valid JSON protocol data."""


@dataclass(frozen=True)
class DinaResponse:
    """A decoded response returned by the Dinahosting API."""

    command: str
    code: int
    data: Any | None
    message: str | None
    transaction_id: str | None


class DinaApiError(DinaError):
    """The API completed a request with an error response code."""

    def __init__(self, response: DinaResponse) -> None:
        self.response = response
        super().__init__(response.message or f"Dinahosting API error {response.code}")


class CommandExecutor(Protocol):
    """Application port used by the hierarchical command API."""

    def call(self, command: str, /, **parameters: Any) -> DinaResponse:
        """Execute an API command."""


class Transport(Protocol):
    """Port used by the application to submit an API request."""

    def post(self, parameters: Mapping[str, Any], user: str, password: str) -> Any:
        """Submit form parameters and return a decoded response payload."""


def response_from_payload(payload: Any, command: str) -> DinaResponse:
    """Validate a decoded payload and translate API errors."""
    if not isinstance(payload, dict) or type(payload.get("responseCode")) is not int:
        raise DinaProtocolError("The Dinahosting API returned an invalid response")
    response_command = payload.get("command", command)
    message = payload.get("message")
    transaction_id = payload.get("trId")
    if (
        not isinstance(response_command, str)
        or message is not None
        and not isinstance(message, str)
        or transaction_id is not None
        and not isinstance(transaction_id, str)
    ):
        raise DinaProtocolError("The Dinahosting API returned an invalid response")
    response = DinaResponse(
        command=response_command,
        code=payload["responseCode"],
        data=payload.get("data"),
        message=message,
        transaction_id=transaction_id,
    )
    if response.code not in SUCCESS_CODES:
        raise DinaApiError(response)
    return response
