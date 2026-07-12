"""Config file editing — JSON merge/remove for MCP server entries.

Uses stdlib json (no comment preservation). Handles nested key paths
(e.g. "mcp.servers" for VS Code) and marked-section replacement for
instructions blocks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GLI_START = "<!-- GLI_START -->"
GLI_END = "<!-- GLI_END -->"

_INSTRUCTIONS_MD = """\
<!-- GLI_START -->
## gli — Godot LLM Interaction

gli provides MCP tools for editing Godot .tscn scene files, querying Godot
API specifications, inspecting images/tilemaps, and managing a per-project
question-linked knowledge base.

### Available MCP tools

- **add_node / delete_node / update_properties / rename_node / move_node** — scene tree editing
- **attach_script / detach_script** — script management
- **add_ext_resource / create_sub_resource** — resource management
- **connect_signal / disconnect_signal** — signal connections
- **apply_ops_file** — batch YAML operations
- **tree** — scene tree inspection
- **validate** — Godot editor validation
- **image_info / tile_grid / tile_region** — image utilities
- **get_godot_spec** — Godot API spec queries
- **set_godot_version / set_project** — session state
- **kb_search / kb_register / kb_list / kb_remove** — knowledge base

### CLI fallback

All tools are also available via the `gli` CLI (e.g. `gli tscn add-node`).
<!-- GLI_END -->
"""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _resolve_nested(
    data: dict[str, Any], key_path: str, *, create: bool = False
) -> dict[str, Any]:
    parts = key_path.split(".")
    current: Any = data
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return {}
        if part not in current:
            if create:
                current[part] = {}
            else:
                return {}
        current = current[part]
    if not isinstance(current, dict):
        return {}
    last = parts[-1]
    if create and last not in current:
        current[last] = {}
    return current.get(last, {}) if isinstance(current.get(last), dict) else {}


def _set_nested(data: dict[str, Any], key_path: str, value: dict[str, Any]) -> None:
    parts = key_path.split(".")
    current: Any = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def merge_mcp_server(
    config_path: Path,
    mcp_key: str,
    server_name: str,
    server_config: dict[str, Any],
) -> bool:
    """Add or update an MCP server entry. Returns True if changed."""
    data = _load_json(config_path)
    servers = _resolve_nested(data, mcp_key, create=True)
    if servers.get(server_name) == server_config:
        return False
    servers[server_name] = server_config
    _set_nested(data, mcp_key, servers)
    _save_json(config_path, data)
    return True


def remove_mcp_server(
    config_path: Path,
    mcp_key: str,
    server_name: str,
) -> bool:
    """Remove an MCP server entry. Returns True if changed."""
    data = _load_json(config_path)
    servers = _resolve_nested(data, mcp_key)
    if server_name not in servers:
        return False
    del servers[server_name]
    _set_nested(data, mcp_key, servers)
    _save_json(config_path, data)
    return True


def add_instructions(path: Path) -> bool:
    """Add or replace the GLI instructions block in a markdown file."""
    existing = path.read_text() if path.exists() else ""
    if GLI_START in existing:
        start = existing.index(GLI_START)
        end = existing.index(GLI_END) + len(GLI_END)
        new = existing[:start] + _INSTRUCTIONS_MD + existing[end:]
    else:
        new = (
            existing.rstrip() + "\n\n" + _INSTRUCTIONS_MD
            if existing
            else _INSTRUCTIONS_MD
        )
    if new == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)
    return True


def remove_instructions(path: Path) -> bool:
    """Remove the GLI instructions block from a markdown file."""
    if not path.exists():
        return False
    existing = path.read_text()
    if GLI_START not in existing:
        return False
    start = existing.index(GLI_START)
    end = existing.index(GLI_END) + len(GLI_END)
    new = (existing[:start] + existing[end:]).rstrip()
    path.write_text(new)
    return True
