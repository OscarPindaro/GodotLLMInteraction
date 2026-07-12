"""Agent installer — configure gli MCP server in coding agents.

Adapted from semble (MIT-licensed) installer, using typer + rich instead of
questionary, and stdlib json instead of tree-sitter for config editing.
"""

from __future__ import annotations

from godotllminteraction.installer.installer import run

__all__ = ["run"]
