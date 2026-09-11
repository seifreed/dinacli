from __future__ import annotations

import base64
import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs

import pytest

from dinacli import (
    COMMANDS,
    DinaApiError,
    DinaClient,
    DinaConfigurationError,
    DinaConnectionError,
    DinaProtocolError,
)
from dinacli.api import Command, CommandGroup
from dinacli.cli import _parameters, main
from dinacli.models import response_from_payload


def require(actual: object, expected: object) -> None:
    if actual != expected:
        pytest.fail(f"Unexpected value: {actual!r}")


def test_require_rejects_unexpected_values() -> None:
    with pytest.raises(pytest.fail.Exception):
        require("actual", "expected")


@contextmanager
def api_server() -> Iterator[tuple[str, dict[str, str]]]:
    received: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            received["authorization"] = self.headers["Authorization"]
            received["body"] = self.rfile.read(length).decode()
            if self.path == "/bad-json":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"not json")
                return
            if self.path == "/bad-encoding":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(bytes([255]))
                return
            if self.path == "/bad-constant":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"responseCode":1000,"data":NaN}')
                return
            if self.path == "/duplicate-key":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"responseCode":1000,"responseCode":2200}')
                return
            if self.path == "/large-number":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"responseCode":1000,"data":1e10000}')
                return
            if self.path == "/large-integer":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"responseCode":' + b"1" * 5000 + b"}")
                return
            if self.path == "/unavailable":
                self.send_response(503)
                self.end_headers()
                return
            response = {
                "responseCode": 1000,
                "command": parse_qs(received["body"])["command"][0],
                "data": {"ok": True},
            }
            if self.path == "/api-error":
                response = {"responseCode": 2200, "message": "Authentication error."}
            if self.path == "/invalid":
                response = {"responseCode": "1000"}
            if self.path == "/float":
                response["data"] = {"value": 1.5}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_call_sends_basic_auth_and_parameters() -> None:
    with api_server() as (endpoint, received):
        response = DinaClient(
            "user", "password", endpoint=f"{endpoint}/success?origin=test"
        ).call(
            "System_GetRequestTypes",
            item=["one", "two"],
            contact={"admin": {"email": "admin@example.test"}},
            enabled=True,
            empty=None,
            count=1,
        )

    require(response.code, 1000)
    require(response.data, {"ok": True})
    require(
        received["authorization"],
        "Basic " + base64.b64encode(b"user:password").decode(),
    )
    require(
        parse_qs(received["body"], keep_blank_values=True),
        {
            "command": ["System_GetRequestTypes"],
            "responseType": ["Json"],
            "item[0]": ["one"],
            "item[1]": ["two"],
            "contact[admin][email]": ["admin@example.test"],
            "enabled": ["true"],
            "empty": [""],
            "count": ["1"],
        },
    )


def test_call_rejects_cyclic_parameters() -> None:
    cyclic_mapping: dict[str, object] = {}
    cyclic_mapping["self"] = cyclic_mapping
    cyclic_sequence: list[object] = []
    cyclic_sequence.append(cyclic_sequence)

    for value in (cyclic_mapping, cyclic_sequence):
        with pytest.raises(ValueError, match="cyclic data"):
            DinaClient("user", "password", endpoint="http://127.0.0.1:1").call(
                "Test", payload=value
            )


def test_api_and_protocol_errors() -> None:
    with api_server() as (endpoint, _):
        client = DinaClient("user", "password", endpoint=f"{endpoint}/api-error")
        with pytest.raises(DinaApiError) as error:
            client.call("Test")
        require(error.value.response.code, 2200)

        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/bad-json").call("Test")
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/bad-encoding").call(
                "Test"
            )
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/bad-constant").call(
                "Test"
            )
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/duplicate-key").call(
                "Test"
            )
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/large-number").call(
                "Test"
            )
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/large-integer").call(
                "Test"
            )
        require(
            DinaClient("user", "password", endpoint=f"{endpoint}/float")
            .call("Test")
            .data,
            {"value": 1.5},
        )
        with pytest.raises(DinaProtocolError):
            DinaClient("user", "password", endpoint=f"{endpoint}/invalid").call("Test")
        with pytest.raises(DinaConnectionError):
            DinaClient("user", "password", endpoint=f"{endpoint}/unavailable").call(
                "Test"
            )
    with pytest.raises(DinaConnectionError):
        DinaClient("user", "password", endpoint="http://127.0.0.1:1/offline").call(
            "Test"
        )


def test_configuration_sources_and_validation(tmp_path: Path) -> None:
    user = "environment-user"
    secret = "test-" + "secret"
    with api_server() as (endpoint, received):
        config = tmp_path / "dina.toml"
        config.write_text(
            "\n".join(
                [
                    "[dina]",
                    "user = 'config-user'",
                    f"password = '{secret}'",
                    f"endpoint = '{endpoint}/success'",
                    "timeout = 3",
                ]
            )
        )
        environment_values = {
            "DINA_USER": user,
            f"DINA_{'PASSWORD'}": secret,
            "DINA_ENDPOINT": f"{endpoint}/success",
            "DINA_TIMEOUT": "3",
        }
        file_configured = DinaClient.from_config(config, {})
        configured = DinaClient.from_config(config, environment_values)
        environment = DinaClient.from_environment(environment_values)
        file_configured.call("System_GetRequestTypes")
        configured.call("System_GetRequestTypes")
        environment.call("System_GetRequestTypes")
        require(
            received["authorization"],
            "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode(),
        )

    with pytest.raises(DinaConfigurationError):
        DinaClient.from_environment({})
    with pytest.raises(DinaConfigurationError):
        DinaClient.from_config(tmp_path / "missing.toml")
    config = tmp_path / "dina.toml"
    config.write_text("[other]\nuser = 'user'\n")
    with pytest.raises(DinaConfigurationError):
        DinaClient.from_config(config)
    with pytest.raises(DinaConfigurationError):
        DinaClient.from_environment(
            {"DINA_USER": user, f"DINA_{'PASSWORD'}": secret, "DINA_TIMEOUT": "bad"}
        )
    with pytest.raises(DinaConfigurationError):
        DinaClient("", "password")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", timeout=0)
    for timeout in (math.inf, math.nan):
        with pytest.raises(DinaConfigurationError):
            DinaClient("user", "password", timeout=timeout)
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="file:///tmp/dina")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="http://example.test")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="https:///missing-host")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="https://host:not-a-port")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="https://host:")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="https://[invalid")
    with pytest.raises(DinaConfigurationError):
        DinaClient("user", "password", endpoint="https://example.test:0")
    config.write_text("[dina]\nuser = 'user'\npassword = 'password'\ntimeout = true\n")
    with pytest.raises(DinaConfigurationError):
        DinaClient.from_config(config, {})
    config.write_text(f"[dina]\nendpoint = '{endpoint}'\n")
    environment_only = DinaClient.from_config(
        config,
        {"DINA_USER": user, f"DINA_{'PASSWORD'}": secret},
    )
    require(environment_only.api.names(), tuple(COMMANDS))
    with pytest.raises(ValueError):
        environment.call("")


def test_documented_commands_are_available_by_namespace() -> None:
    with api_server() as (endpoint, received):
        client = DinaClient("user", "password", endpoint=f"{endpoint}/success")
        command = client.api.domain.zone.add_type_a
        system_response = client.api.system.get_api_version()
        response = command(
            domain="example.test", hostname="www", ip="192.0.2.10", simulate=True
        )

    require(len(COMMANDS), 485)
    require(system_response.code, 1000)
    require(response.code, 1000)
    require(
        parse_qs(received["body"]),
        {
            "command": ["Domain_Zone_AddTypeA"],
            "responseType": ["Json"],
            "domain": ["example.test"],
            "hostname": ["www"],
            "ip": ["192.0.2.10"],
            "SIMULATE": ["true"],
        },
    )
    require(client.api["System_GetApiVersion"].name, "System_GetApiVersion")
    require(command.required, frozenset({"domain", "hostname", "ip"}))
    require(command.optional, frozenset())
    require(client.api.billing.period.multihosting.required, frozenset({"action"}))
    require(len(client.api.names()), 485)
    require(
        client.api.domain_verification.get_pending.name, "DomainVerification_GetPending"
    )
    require(client.api.import_.get_status.name, "Import_GetStatus")
    require(
        client.api.hosting.import_.list.name,
        "Hosting_Import_List",
    )
    require("domain" in dir(client.api), True)
    require("import_" in dir(client.api), True)
    require("zone" in dir(client.api.domain), True)
    with pytest.raises(TypeError):
        client.api.domain.zone.add_type_a(domain="example.test", hostname="www")
    with pytest.raises(TypeError):
        client.api.system.get_api_version(unexpected=True)
    missing = "missing"
    with pytest.raises(AttributeError):
        getattr(client.api.domain, missing)


def test_response_protocol_requires_documented_scalar_types() -> None:
    for payload in (
        {"responseCode": True},
        {"responseCode": 1000, "command": None},
        {"responseCode": 1000, "message": 7},
        {"responseCode": 1000, "trId": []},
    ):
        with pytest.raises(DinaProtocolError):
            response_from_payload(payload, "Test")


def test_all_documented_commands_execute_with_every_documented_parameter() -> None:
    with api_server() as (endpoint, _):
        client = DinaClient("user", "password", endpoint=f"{endpoint}/success")
        pending: list[Command | CommandGroup] = [client.api]
        commands = {}
        while pending:
            group = pending.pop()
            for attribute in dir(group):
                option = getattr(group, attribute)
                if isinstance(option, Command):
                    commands[option.name] = option
                    pending.append(option)
                elif isinstance(option, CommandGroup):
                    pending.append(option)

        require(set(commands), set(COMMANDS))
        for name, spec in COMMANDS.items():
            command = commands[name]
            require(command.required, spec.required)
            require(command.optional, spec.optional)
            response = command(**{parameter: "test" for parameter in spec.parameters})
            require(response.command, name)
            require(response.code, 1000)


def test_cli_lists_and_describes_documented_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    require(main(["commands"]), 0)
    require(set(capsys.readouterr().out.splitlines()), set(COMMANDS))

    require(main(["--output", "json", "commands"]), 0)
    require(json.loads(capsys.readouterr().out), sorted(COMMANDS))

    require(main(["describe", "Domain_Zone_AddTypeA"]), 0)
    require(
        json.loads(capsys.readouterr().out),
        {
            "command": "Domain_Zone_AddTypeA",
            "optional": [],
            "required": ["domain", "hostname", "ip"],
        },
    )


def test_cli_treats_nonstandard_json_constants_as_text() -> None:
    require(
        _parameters(["value=NaN", "positive=Infinity", "negative=-Infinity"]),
        {"value": "NaN", "positive": "Infinity", "negative": "-Infinity"},
    )


def test_cli_calls_api_with_all_configuration_sources(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with api_server() as (endpoint, received):
        require(
            main(
                [
                    "--user",
                    "cli-user",
                    "--password",
                    "cli-password",
                    "--endpoint",
                    f"{endpoint}/success",
                    "call",
                    "Domain_Zone_AddTypeA",
                    "--param",
                    "domain=example.test",
                    "--param",
                    "hostname=www",
                    "--param",
                    "ip=192.0.2.10",
                    "--param",
                    'metadata={"priority": 1}',
                    "--simulate",
                ]
            ),
            1,
        )
        require("does not accept: metadata" in capsys.readouterr().err, True)

        config = tmp_path / "dina.toml"
        config.write_text(
            "\n".join(
                [
                    "[dina]",
                    "user = 'config-user'",
                    "password = 'config-password'",
                    f"endpoint = '{endpoint}/success'",
                    "timeout = 3",
                ]
            )
        )
        require(
            main(
                [
                    "--config",
                    str(config),
                    "--user",
                    "config-user",
                    "--password",
                    "config-password",
                    "--endpoint",
                    f"{endpoint}/success",
                    "--timeout",
                    "3",
                    "call",
                    "Domain_Zone_AddTypeA",
                    "--param",
                    "domain=example.test",
                    "--param",
                    "hostname=www",
                    "--param",
                    "ip=192.0.2.10",
                    "--simulate",
                ]
            ),
            0,
        )
        require(json.loads(capsys.readouterr().out)["code"], 1000)
        require(
            received["authorization"],
            "Basic " + base64.b64encode(b"config-user:config-password").decode(),
        )
        require(parse_qs(received["body"])["SIMULATE"], ["true"])

        require(
            main(
                [
                    "--user",
                    "cli-user",
                    "--password",
                    "cli-password",
                    "--endpoint",
                    f"{endpoint}/success",
                    "--timeout",
                    "3",
                    "call",
                    "System_GetRequestTypes",
                ]
            ),
            0,
        )
        require(json.loads(capsys.readouterr().out)["code"], 1000)

    require(main(["describe", "Unknown_Command"]), 1)
    require("Unknown command" in capsys.readouterr().err, True)
    require(main(["--output", "json", "describe", "Unknown_Command"]), 1)
    require(
        json.loads(capsys.readouterr().err),
        {"error": "Unknown command: Unknown_Command"},
    )
    require(
        main(["call", "System_GetRequestTypes", "--param", "invalid"]),
        1,
    )
    require("NAME=VALUE" in capsys.readouterr().err, True)
    require(
        main(
            [
                "call",
                "System_GetRequestTypes",
                "--param",
                "item=one",
                "--param",
                "item=two",
            ]
        ),
        1,
    )
    require("more than once" in capsys.readouterr().err, True)
