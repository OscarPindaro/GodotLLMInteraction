"""Session state shared across MCP tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class McpContext:
    godot_version: str | None = None
    project_path: str | None = None
