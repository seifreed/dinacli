"""Command-line interface for the Dinahosting API client."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from importlib.metadata import version
from math import isfinite
from typing import Any, NoReturn, TextIO

from .bootstrap import DinaClient
from .commands import COMMANDS
from .models import CommandSpec, DinaError, DinaResponse


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the dinacli command-line interface."""
    parser = _parser()
    namespace = parser.parse_args(arguments)
    try:
        handler: Callable[[argparse.Namespace], int] = namespace.handler
        return handler(namespace)
    except (DinaError, TypeError, ValueError) as error:
        if namespace.output == "json":
            _write_json({"error": str(error)}, sys.stderr)
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute documented Dinahosting API commands."
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('dinacli')}"
    )
    parser.add_argument("--config", help="TOML file with a [dina] section")
    parser.add_argument("--user", help="Dinahosting API user")
    parser.add_argument("--password", help="Dinahosting API password")
    parser.add_argument("--endpoint", help="API endpoint URL")
    parser.add_argument("--timeout", help="Request timeout in seconds")
    parser.add_argument(
        "--output",
        choices=("json",),
        help="Emit output as JSON, including errors on stderr",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    commands = actions.add_parser("commands", help="List documented API commands")
    commands.set_defaults(handler=_list_commands)

    describe = actions.add_parser("describe", help="Show a command's parameters")
    describe.add_argument("command", help="Exact documented API command name")
    describe.set_defaults(handler=_describe_command)

    call = actions.add_parser("call", help="Execute a documented API command")
    call.add_argument("command", help="Exact documented API command name")
    call.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Parameter; VALUE is JSON when valid, otherwise text. Repeatable.",
    )
    call.add_argument(
        "--simulate", action="store_true", help="Send the API SIMULATE parameter"
    )
    call.set_defaults(handler=_call_command)
    return parser


def _list_commands(arguments: argparse.Namespace) -> int:
    commands = sorted(COMMANDS)
    if arguments.output == "json":
        _write_json(commands)
    else:
        print("\n".join(commands))
    return 0


def _describe_command(arguments: argparse.Namespace) -> int:
    spec = _command_spec(arguments.command)
    _write_json(
        {
            "command": spec.name,
            "optional": sorted(spec.optional),
            "required": sorted(spec.required),
        }
    )
    return 0


def _call_command(arguments: argparse.Namespace) -> int:
    spec = _command_spec(arguments.command)
    parameters = _parameters(arguments.param)
    if arguments.simulate:
        parameters["simulate"] = True
    response = _client(arguments).api[spec.name](**parameters)
    _write_response(response)
    return 0


def _command_spec(command: str) -> CommandSpec:
    if command not in COMMANDS:
        raise ValueError(f"Unknown command: {command}")
    return COMMANDS[command]


def _parameters(values: Sequence[str]) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for value in values:
        name, separator, raw_value = value.partition("=")
        if not separator or not name:
            raise ValueError("Parameters must use NAME=VALUE")
        if name in parameters:
            raise ValueError(f"Parameter specified more than once: {name}")
        try:
            parameters[name] = json.loads(
                raw_value,
                parse_constant=_invalid_json_constant,
                parse_float=_finite_json_number,
            )
        except json.JSONDecodeError:
            parameters[name] = raw_value
    return parameters


def _invalid_json_constant(value: str) -> NoReturn:
    raise json.JSONDecodeError("Invalid JSON constant", value, 0)


def _finite_json_number(value: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise json.JSONDecodeError("JSON number is not finite", value, 0)
    return number


def _client(arguments: argparse.Namespace) -> DinaClient:
    environment = dict(os.environ)
    for option, variable in (
        ("user", "DINA_USER"),
        ("password", "DINA_PASSWORD"),
        ("endpoint", "DINA_ENDPOINT"),
        ("timeout", "DINA_TIMEOUT"),
    ):
        value = getattr(arguments, option)
        if value is not None:
            environment[variable] = value
    if arguments.config:
        return DinaClient.from_config(arguments.config, environment)
    return DinaClient.from_environment(environment)


def _write_response(response: DinaResponse) -> None:
    _write_json(
        {
            "code": response.code,
            "command": response.command,
            "data": response.data,
            "message": response.message,
            "transaction_id": response.transaction_id,
        }
    )


def _write_json(value: object, stream: TextIO | None = None) -> None:
    print(json.dumps(value, indent=2, sort_keys=True), file=stream)
