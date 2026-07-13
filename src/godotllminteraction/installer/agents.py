"""Agent target definitions — where each coding agent stores MCP config.

Adapted from semble (MIT). Each target knows:
- its config file path(s)
- the JSON key path where MCP servers live
- whether the config uses a "type" field for stdio servers
- how to detect the agent is installed
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentTarget:
    id: str
    name: str
    config_paths: list[Path]
    mcp_key: str  # JSON key under which mcpServers live
    bare_config: bool  # True if no "type" field (e.g. Windsurf)
    detect_paths: list[Path] = field(default_factory=list)
    instructions_file: Path | None = None
    instructions_format: str = "markdown"  # "markdown" or "json"


def _home() -> Path:
    return Path.home()


def _xdg_config() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg)
    return _home() / ".config"


def _windsurf_config_paths() -> list[Path]:
    h = _home()
    paths = [h / ".codeium" / "windsurf" / "mcp_config.json"]
    if sys.platform == "darwin":
        paths = [h / "Library" / "Application Support" / "Windsurf" / "mcp_config.json"]
    return paths


def _windsurf_detect_paths() -> list[Path]:
    h = _home()
    paths = [h / ".codeium" / "windsurf"]
    if sys.platform == "darwin":
        paths = [h / "Library" / "Application Support" / "Windsurf"]
    return paths


def _vscode_settings() -> list[Path]:
    base = _xdg_config() / "Code" / "User"
    candidates = [base / "settings.json"]
    if sys.platform == "darwin":
        candidates = [
            _home()
            / "Library"
            / "Application Support"
            / "Code"
            / "User"
            / "settings.json",
        ]
    return candidates


def _detect(path: Path) -> bool:
    return path.exists()


def all_targets() -> list[AgentTarget]:
    cfg = _xdg_config()
    h = _home()

    return [
        AgentTarget(
            id="windsurf",
            name="Windsurf / Devin Desktop",
            config_paths=_windsurf_config_paths(),
            mcp_key="mcpServers",
            bare_config=True,
            detect_paths=_windsurf_detect_paths(),
        ),
        AgentTarget(
            id="claude",
            name="Claude Code",
            config_paths=[
                h / ".claude.json",
                h / ".claude" / "claude_desktop_config.json",
            ],
            mcp_key="mcpServers",
            bare_config=False,
            detect_paths=[h / ".claude"],
        ),
        AgentTarget(
            id="cursor",
            name="Cursor",
            config_paths=[
                _home() / ".cursor" / "mcp.json",
                cfg / "Cursor" / "mcp.json",
            ],
            mcp_key="mcpServers",
            bare_config=False,
            detect_paths=[_home() / ".cursor", cfg / "Cursor"],
        ),
        AgentTarget(
            id="vscode",
            name="VS Code",
            config_paths=_vscode_settings(),
            mcp_key="mcp.servers",
            bare_config=False,
            detect_paths=[cfg / "Code"],
        ),
        AgentTarget(
            id="zed",
            name="Zed",
            config_paths=[cfg / "zed" / "settings.json"],
            mcp_key="context_servers",
            bare_config=False,
            detect_paths=[cfg / "zed"],
        ),
        AgentTarget(
            id="codex",
            name="Codex",
            config_paths=[cfg / "codex" / "config.json"],
            mcp_key="mcp_servers",
            bare_config=False,
            detect_paths=[cfg / "codex"],
        ),
        AgentTarget(
            id="gemini",
            name="Gemini CLI",
            config_paths=[cfg / "gemini" / "mcp.json"],
            mcp_key="mcpServers",
            bare_config=False,
            detect_paths=[cfg / "gemini"],
        ),
    ]


def detect_installed(targets: list[AgentTarget] | None = None) -> list[AgentTarget]:
    targets = targets or all_targets()
    return [t for t in targets if any(_detect(p) for p in t.detect_paths)]
