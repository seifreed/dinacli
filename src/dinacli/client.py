"""Application service for documented Dinahosting API commands."""

from __future__ import annotations

from typing import Any

from .api import Api
from .models import DinaResponse, Transport, response_from_payload
from .settings import ClientSettings


class ApiClient:
    """Execute commands through a supplied transport port."""

    def __init__(self, settings: ClientSettings, transport: Transport) -> None:
        self._settings = settings
        self._transport = transport
        self.api = Api(self)

    def call(self, command: str, /, **parameters: Any) -> DinaResponse:
        """Call a documented Dinahosting command and return its decoded response."""
        if not command:
            raise ValueError("Command is required")
        payload = self._transport.post(
            {"command": command, "responseType": "Json", **parameters},
            self._settings.user,
            self._settings.password,
        )
        return response_from_payload(payload, command)
