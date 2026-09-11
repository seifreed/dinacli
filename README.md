<p align="center">
  <img src="https://img.shields.io/badge/dinacli-Dinahosting%20API-blue?style=for-the-badge" alt="dinacli">
</p>

<h1 align="center">dinacli</h1>

<p align="center">
  <strong>Python 3.14 client and command-line interface for the Dinahosting API</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/dinacli/"><img src="https://img.shields.io/pypi/v/dinacli?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/dinacli/"><img src="https://img.shields.io/pypi/pyversions/dinacli?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/seifreed/dinacli/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://github.com/seifreed/dinacli/stargazers"><img src="https://img.shields.io/github/stars/seifreed/dinacli?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/seifreed/dinacli/issues"><img src="https://img.shields.io/github/issues/seifreed/dinacli?style=flat-square" alt="GitHub Issues"></a>
  <a href="https://buymeacoffee.com/seifreed"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?style=flat-square&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>
</p>

---

## Overview

**dinacli** is a Python library and CLI for the Dinahosting API. It exposes the 485 documented API commands, validates their documented parameters, sends form-encoded requests through HTTPS, and returns typed responses.

### Key Features

| Feature | Description |
|---------|-------------|
| **Complete command catalogue** | Access all 485 documented Dinahosting API commands |
| **CLI + library** | Automate from `dinacli` or use `DinaClient` in Python |
| **Parameter validation** | Required and optional parameters are checked before requests are sent |
| **JSON output** | Commands, descriptions, responses, and optional errors are machine-readable |
| **Configuration sources** | Credentials and connection settings from flags, environment variables, or TOML |
| **Secure transport** | HTTPS is required for remote endpoints; HTTP is limited to loopback integration tests |
| **Typed failures** | Configuration, connection, protocol, and API errors have distinct exception types |

### Supported Interfaces

```text
CLI              commands, describe, call
Configuration    command-line flags, DINA_* environment variables, TOML
Response data    JSON output and DinaResponse objects
Python access    exact API names and hierarchical namespaces
```

---

## Installation

### From PyPI

After publication, install the package with:

```bash
python -m pip install dinacli
```

### From Source

```bash
git clone https://github.com/seifreed/dinacli.git
cd dinacli
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m pip install -e .
```

Development tooling is declared in `pyproject.toml` alongside the package metadata.

---

## Quick Start

```bash
# List every documented API command
dinacli commands

# Inspect parameters before executing a command
dinacli describe Domain_Zone_AddTypeA

# Execute a simulated request
dinacli --user mi_usuario --password mi_contrasena \
  call Domain_Zone_AddTypeA \
  --param domain=example.com \
  --param hostname=www \
  --param ip=192.0.2.10 \
  --simulate
```

---

## Usage

### Command Line Interface

```bash
# List commands as JSON
dinacli --output json commands

# Display required and optional parameters
dinacli describe Vps_PowerStatus_Restart

# Pass strings, numbers, booleans, arrays, or objects with --param
dinacli --user mi_usuario --password mi_contrasena \
  call Domain_Zone_AddTypeA \
  --param domain=example.com \
  --param hostname=www \
  --param ip=192.0.2.10 \
  --simulate
```

### Commands

| Command | Description |
|---------|-------------|
| `dinacli commands` | List the 485 documented API command names |
| `dinacli describe COMANDO` | Show a command's required and optional parameters |
| `dinacli call COMANDO` | Validate and execute a documented API command |

### Global Options

| Option | Description |
|--------|-------------|
| `--config ARCHIVO` | TOML file with a `[dina]` section |
| `--user USUARIO` | Dinahosting API user |
| `--password CLAVE` | Dinahosting API password |
| `--endpoint URL` | Override the default API endpoint |
| `--timeout SEGUNDOS` | Request timeout; defaults to 20 seconds |
| `--output json` | JSON array for `commands` and JSON errors on stderr |
| `--version` | Print the installed package version |

Global options must precede the subcommand. `call` accepts `--param NOMBRE=VALOR` repeatedly. Valid JSON values are decoded before sending; other values are sent as text. `--simulate` sends the API `SIMULATE` parameter.

### Configuration

`DINA_USER` and `DINA_PASSWORD` are required when creating a client from the environment. The optional variables are `DINA_ENDPOINT` and `DINA_TIMEOUT`.

```toml
[dina]
user = "mi_usuario"
password = "mi_contrasena"
endpoint = "https://dinahosting.com/special/api.php"
timeout = 20
```

Command-line flags take precedence over `DINA_*` variables, which take precedence over TOML values. Prefer environment variables or a protected TOML file over passing a password directly on the command line.

---

## Python Library

### Basic Usage

```python
from dinacli import DinaClient

client = DinaClient.from_environment()
domains = client.call("Services_GetDomains").data
```

### Documented Commands

```python
from dinacli import DinaClient

client = DinaClient("mi_usuario", "mi_contrasena")

client.api.domain.zone.add_type_a(
    domain="example.com",
    hostname="www",
    ip="192.0.2.10",
)

client.api["Vps_PowerStatus_Restart"](serverName="vps.example.com")
```

Every documented command validates its required and optional parameters. Successful calls return `DinaResponse`; non-success API codes raise `DinaApiError`.

---

## Requirements

- Python 3.14+
- No runtime dependencies

See [pyproject.toml](pyproject.toml) for package metadata and development tooling.

---

## Releases

CI runs the full quality and security gate on the latest Linux, Windows, and
macOS runners using Python 3.14. Push a version tag that matches the package
version to publish a release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

PyPI publishing uses GitHub Actions OIDC Trusted Publishing and does not use a
stored PyPI token. Before the first release, register a pending publisher in
PyPI with the following values:

```text
Owner:       seifreed
Repository:  dinacli
Workflow:    release.yml
Environment: pypi
```

Configure the optional `pypi` GitHub environment with required reviewers when
manual release approval is desired.

---

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Run the quality and security gates from `AGENTS.md`.
4. Commit and push the change.
5. Open a pull request.

---

## Support the Project

<a href="https://buymeacoffee.com/seifreed" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50">
</a>

---

## License

This project is licensed under the [MIT License](LICENSE).

**Repository:** [github.com/seifreed/dinacli](https://github.com/seifreed/dinacli)

---

<p align="center">
  <sub>Built for reliable Dinahosting API automation</sub>
</p>
