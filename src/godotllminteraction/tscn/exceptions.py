from __future__ import annotations


class TscnError(Exception):
    """Base for every error raised by the tscn package."""


class ParseError(TscnError):
    """A .tscn file or a Godot value literal could not be parsed."""

    def __init__(self, message: str, *, line: int | None = None) -> None:
        self.line = line
        super().__init__(f"line {line}: {message}" if line is not None else message)


class OperationError(TscnError):
    """An operation could not be applied to the scene (conflict, missing target, ...)."""


class SceneValidationError(TscnError):
    """A scene or operation failed spec validation in strict mode."""
