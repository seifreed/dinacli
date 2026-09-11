"""Public composition root for the default Dinahosting client."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Self

from .client import ApiClient
from .configuration import settings_from_config, settings_from_environment
from .settings import DEFAULT_ENDPOINT, ClientSettings
from .transport import HttpTransport


class DinaClient(ApiClient):
    """Create an API client with the default HTTP transport."""

    def __init__(
        self,
        user: str,
        password: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 20.0,
    ) -> None:
        settings = ClientSettings(user, password, endpoint, timeout)
        super().__init__(settings, HttpTransport(settings.endpoint, settings.timeout))

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Self:
        """Build a client from DINA_USER and DINA_PASSWORD environment variables."""
        return cls._from_settings(settings_from_environment(environ))

    @classmethod
    def from_config(
        cls, path: str | Path, environ: Mapping[str, str] | None = None
    ) -> Self:
        """Build a client from a TOML file, overridden by DINA_* variables."""
        return cls._from_settings(settings_from_config(path, environ))

    @classmethod
    def _from_settings(cls, settings: ClientSettings) -> Self:
        return cls(
            settings.user,
            settings.password,
            endpoint=settings.endpoint,
            timeout=settings.timeout,
        )
