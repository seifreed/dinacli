"""HTTP infrastructure for the Dinahosting API."""

from __future__ import annotations

import base64
import json
import sys
from collections.abc import Mapping, Sequence
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from ipaddress import ip_address
from math import isfinite
from typing import Any, NoReturn
from urllib.parse import urlencode, urlsplit

from .models import DinaConfigurationError, DinaConnectionError, DinaProtocolError

_CONNECTION_TYPES: Mapping[str, type[HTTPConnection]] = {
    "http": HTTPConnection,
    "https": HTTPSConnection,
}
_MAX_JSON_INTEGER_DIGITS = sys.int_info.default_max_str_digits


class HttpTransport:
    """Send form-encoded commands through a validated HTTP endpoint."""

    def __init__(self, endpoint: str, timeout: float) -> None:
        try:
            parsed_endpoint = urlsplit(endpoint)
        except ValueError as error:
            raise DinaConfigurationError("Endpoint URL is invalid") from error
        if (
            parsed_endpoint.scheme not in _CONNECTION_TYPES
            or not parsed_endpoint.hostname
        ):
            raise DinaConfigurationError("Endpoint must be an HTTP(S) URL")
        if parsed_endpoint.scheme == "http" and not _is_loopback(
            parsed_endpoint.hostname
        ):
            raise DinaConfigurationError(
                "Endpoint must use HTTPS unless it is a loopback address"
            )
        if parsed_endpoint.netloc.rsplit("@", maxsplit=1)[-1].endswith(":"):
            raise DinaConfigurationError("Endpoint port is invalid")
        try:
            port = parsed_endpoint.port
        except ValueError as error:
            raise DinaConfigurationError("Endpoint port is invalid") from error
        if port == 0:
            raise DinaConfigurationError("Endpoint port is invalid")
        self._connection_type = _CONNECTION_TYPES[parsed_endpoint.scheme]
        self._host = parsed_endpoint.hostname
        self._port = port
        self._request_target = parsed_endpoint.path or "/"
        if parsed_endpoint.query:
            self._request_target += f"?{parsed_endpoint.query}"
        self._timeout = timeout

    def post(self, parameters: Mapping[str, Any], user: str, password: str) -> Any:
        """Send form parameters and decode the JSON response body."""
        connection = self._connection_type(
            self._host, self._port, timeout=self._timeout
        )
        try:
            connection.request(
                "POST",
                self._request_target,
                body=urlencode(_form_items(parameters)).encode(),
                headers={
                    "Accept": "application/json",
                    "Authorization": _basic_authorization(user, password),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise DinaConnectionError("The Dinahosting API returned an HTTP error")
            try:
                return _decode_json(response.read())
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                raise DinaProtocolError(
                    "The Dinahosting API returned invalid JSON"
                ) from error
        except (HTTPException, OSError, TimeoutError) as error:
            raise DinaConnectionError("Could not reach the Dinahosting API") from error
        finally:
            connection.close()


def _basic_authorization(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _decode_json(body: bytes) -> Any:
    return json.loads(
        body,
        object_pairs_hook=_json_object,
        parse_constant=_invalid_json_constant,
        parse_float=_finite_json_number,
        parse_int=_bounded_json_integer,
    )


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise json.JSONDecodeError("Duplicate JSON key", key, 0)
        value[key] = item
    return value


def _invalid_json_constant(value: str) -> NoReturn:
    raise json.JSONDecodeError("Invalid JSON constant", value, 0)


def _finite_json_number(value: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise json.JSONDecodeError("JSON number is not finite", value, 0)
    return number


def _bounded_json_integer(value: str) -> int:
    if len(value.lstrip("-")) > _MAX_JSON_INTEGER_DIGITS:
        raise json.JSONDecodeError("JSON integer is too large", value, 0)
    return int(value)


def _is_loopback(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _form_items(parameters: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Encode scalars, arrays, and structs using PHP's bracket notation."""
    items: list[tuple[str, str]] = []
    for name, value in parameters.items():
        _append_form_item(items, name, value, set())
    return items


def _append_form_item(
    items: list[tuple[str, str]], name: str, value: Any, ancestors: set[int]
) -> None:
    """Append one recursively encoded form value."""
    if isinstance(value, Mapping):
        marker = _enter_container(value, ancestors)
        try:
            for key, nested_value in value.items():
                _append_form_item(items, f"{name}[{key}]", nested_value, ancestors)
        finally:
            ancestors.remove(marker)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        marker = _enter_container(value, ancestors)
        try:
            for index, nested_value in enumerate(value):
                _append_form_item(items, f"{name}[{index}]", nested_value, ancestors)
        finally:
            ancestors.remove(marker)
    elif isinstance(value, bool):
        items.append((name, str(value).lower()))
    elif value is None:
        items.append((name, ""))
    else:
        items.append((name, str(value)))


def _enter_container(value: object, ancestors: set[int]) -> int:
    marker = id(value)
    if marker in ancestors:
        raise ValueError("Parameters cannot contain cyclic data")
    ancestors.add(marker)
    return marker
