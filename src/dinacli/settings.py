"""Validated client configuration used by the application core."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .models import DinaConfigurationError

DEFAULT_ENDPOINT = "https://dinahosting.com/special/api.php"


@dataclass(frozen=True)
class ClientSettings:
    """Credentials and connection settings required by a client."""

    user: str
    password: str
    endpoint: str = DEFAULT_ENDPOINT
    timeout: float = 20.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.user, str)
            or not isinstance(self.password, str)
            or not self.user
            or not self.password
        ):
            raise DinaConfigurationError("A user and password are required")
        if not isinstance(self.endpoint, str) or not self.endpoint:
            raise DinaConfigurationError("An endpoint is required")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not isfinite(self.timeout)
            or self.timeout <= 0
        ):
            raise DinaConfigurationError("Timeout must be greater than zero")
