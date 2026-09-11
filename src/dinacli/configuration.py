"""Configuration sources for Dinahosting clients."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .models import DinaConfigurationError
from .settings import DEFAULT_ENDPOINT, ClientSettings


def settings_from_environment(
    environ: Mapping[str, str] | None = None,
) -> ClientSettings:
    """Load settings from DINA_* environment variables."""
    values = os.environ if environ is None else environ
    return ClientSettings(
        _required(values, "DINA_USER"),
        _required(values, "DINA_PASSWORD"),
        endpoint=values.get("DINA_ENDPOINT", DEFAULT_ENDPOINT),
        timeout=_timeout(values.get("DINA_TIMEOUT", "20")),
    )


def settings_from_config(
    path: str | Path, environ: Mapping[str, str] | None = None
) -> ClientSettings:
    """Load TOML settings, overridden by DINA_* environment variables."""
    values = _read_config(path)
    environment = os.environ if environ is None else environ
    return ClientSettings(
        _environment_or_config(environment, values, "DINA_USER", "user"),
        _environment_or_config(environment, values, "DINA_PASSWORD", "password"),
        endpoint=environment.get(
            "DINA_ENDPOINT", values.get("endpoint", DEFAULT_ENDPOINT)
        ),
        timeout=_timeout(environment.get("DINA_TIMEOUT", values.get("timeout", 20))),
    )


def _read_config(path: str | Path) -> Mapping[str, Any]:
    try:
        with Path(path).open("rb") as file:
            document = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise DinaConfigurationError("Could not read the configuration file") from error
    settings = document.get("dina")
    if not isinstance(settings, dict):
        raise DinaConfigurationError("The configuration file requires a [dina] table")
    return settings


def _required(values: Mapping[str, Any], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise DinaConfigurationError(f"{name} is required")
    return value


def _environment_or_config(
    environment: Mapping[str, str],
    config: Mapping[str, Any],
    environment_name: str,
    config_name: str,
) -> str:
    if environment_name in environment:
        return environment[environment_name]
    return _required(config, config_name)


def _timeout(value: Any) -> float:
    if isinstance(value, bool):
        raise DinaConfigurationError("Timeout must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise DinaConfigurationError("Timeout must be numeric") from error
