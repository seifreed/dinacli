"""Hierarchical access to the documented Dinahosting commands."""

from __future__ import annotations

import re
from keyword import iskeyword
from typing import Any

from .commands import COMMANDS
from .models import CommandExecutor, CommandSpec, DinaResponse

_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _python_name(name: str) -> str:
    """Convert an API command segment into a Python attribute name."""
    python_name = _WORD_BOUNDARY.sub("_", name).lower()
    return f"{python_name}_" if iskeyword(python_name) else python_name


def _path(name: str) -> tuple[str, ...]:
    """Return the Python namespace path for an API command name."""
    return tuple(_python_name(segment) for segment in name.split("_"))


class Command:
    """A callable documented Dinahosting command."""

    def __init__(self, executor: CommandExecutor, spec: CommandSpec) -> None:
        self._executor = executor
        self._spec = spec

    @property
    def name(self) -> str:
        """Return the API command name sent to Dinahosting."""
        return self._spec.name

    @property
    def required(self) -> frozenset[str]:
        """Return documented required parameters."""
        return self._spec.required

    @property
    def optional(self) -> frozenset[str]:
        """Return documented optional parameters."""
        return self._spec.optional

    def __getattr__(self, name: str) -> Any:
        """Resolve commands nested below this callable command."""
        return getattr(CommandGroup(self._executor, _path(self.name)), name)

    def __dir__(self) -> list[str]:
        """Expose both command attributes and nested documented commands."""
        group = CommandGroup(self._executor, _path(self.name))
        return sorted(set(object.__dir__(self)) | set(dir(group)))

    def __call__(self, **parameters: Any) -> DinaResponse:
        """Validate documented parameters and execute the command."""
        unknown = parameters.keys() - self._spec.parameters - {"simulate"}
        if unknown:
            raise TypeError(
                f"{self.name} does not accept: {', '.join(sorted(unknown))}"
            )
        missing = self._spec.required - parameters.keys()
        if missing:
            raise TypeError(f"{self.name} requires: {', '.join(sorted(missing))}")
        request_parameters = dict(parameters)
        if "simulate" in request_parameters:
            request_parameters["SIMULATE"] = request_parameters.pop("simulate")
        return self._executor.call(self.name, **request_parameters)


class CommandGroup:
    """A namespace that lazily resolves documented commands and subcommands."""

    def __init__(self, executor: CommandExecutor, prefix: tuple[str, ...]) -> None:
        self._executor = executor
        self._prefix = prefix

    def __getattr__(self, name: str) -> Any:
        prefix = (*self._prefix, name)
        matches = [
            spec
            for spec in COMMANDS.values()
            if _path(spec.name)[: len(prefix)] == prefix
        ]
        if not matches:
            raise AttributeError(name)
        command = next((spec for spec in matches if _path(spec.name) == prefix), None)
        if command is not None:
            return Command(self._executor, command)
        return CommandGroup(self._executor, prefix)

    def __dir__(self) -> list[str]:
        """Expose available child commands to interactive Python tooling."""
        position = len(self._prefix)
        return sorted(
            {
                _path(spec.name)[position]
                for spec in COMMANDS.values()
                if _path(spec.name)[:position] == self._prefix
                and len(_path(spec.name)) > position
            }
        )


class Api(CommandGroup):
    """Root namespace for every command in the supplied documentation."""

    def __init__(self, executor: CommandExecutor) -> None:
        super().__init__(executor, ())

    def __getitem__(self, name: str) -> Command:
        """Return a command by its exact documented API name."""
        return Command(self._executor, COMMANDS[name])

    def names(self) -> tuple[str, ...]:
        """Return every documented API command name."""
        return tuple(COMMANDS)
