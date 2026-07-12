"""Tests for installer config editing — JSON merge/remove, nested keys, instructions blocks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godotllminteraction.installer.config import (
    GLI_END,
    GLI_START,
    add_instructions,
    merge_mcp_server,
    remove_instructions,
    remove_mcp_server,
)

pytestmark = [pytest.mark.installer]


class TestMergeMcpServer:
    def test_creates_new_config_file_with_server(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        server = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        changed = merge_mcp_server(cfg, "mcpServers", "gli", server)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcpServers"]["gli"] == server

    def test_merges_into_existing_config_without_clobbering(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {"other": {"command": "other-cmd"}},
                    "settings": {"foo": "bar"},
                }
            )
        )
        server = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        changed = merge_mcp_server(cfg, "mcpServers", "gli", server)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcpServers"]["gli"] == server
        assert data["mcpServers"]["other"] == {"command": "other-cmd"}
        assert data["settings"]["foo"] == "bar"

    def test_returns_false_when_already_configured(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        server = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        merge_mcp_server(cfg, "mcpServers", "gli", server)
        changed = merge_mcp_server(cfg, "mcpServers", "gli", server)
        assert changed is False

    def test_updates_existing_server_config(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        old = {"command": "old-cmd", "type": "stdio"}
        merge_mcp_server(cfg, "mcpServers", "gli", old)
        new = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        changed = merge_mcp_server(cfg, "mcpServers", "gli", new)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcpServers"]["gli"] == new

    def test_nested_key_path_creates_intermediate_dicts(self, tmp_path: Path):
        """VS Code uses 'mcp.servers' as a dotted key path."""
        cfg = tmp_path / "settings.json"
        server = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        changed = merge_mcp_server(cfg, "mcp.servers", "gli", server)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcp"]["servers"]["gli"] == server

    def test_nested_key_path_preserves_sibling_keys(self, tmp_path: Path):
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcp": {"servers": {"other": {"command": "x"}}},
                    "editor": {"fontSize": 14},
                }
            )
        )
        server = {"command": "uvx", "args": ["gli", "mcp"], "type": "stdio"}
        changed = merge_mcp_server(cfg, "mcp.servers", "gli", server)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcp"]["servers"]["gli"] == server
        assert data["mcp"]["servers"]["other"] == {"command": "x"}
        assert data["editor"]["fontSize"] == 14

    def test_corrupt_json_treated_as_empty(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text("not valid json{{{")
        server = {"command": "uvx"}
        changed = merge_mcp_server(cfg, "mcpServers", "gli", server)
        assert changed is True
        data = json.loads(cfg.read_text())
        assert data["mcpServers"]["gli"] == server


class TestRemoveMcpServer:
    def test_removes_server_and_returns_true(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gli": {"command": "uvx"},
                        "other": {"command": "x"},
                    },
                }
            )
        )
        changed = remove_mcp_server(cfg, "mcpServers", "gli")
        assert changed is True
        data = json.loads(cfg.read_text())
        assert "gli" not in data["mcpServers"]
        assert data["mcpServers"]["other"] == {"command": "x"}

    def test_returns_false_when_not_present(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"other": {}}}))
        changed = remove_mcp_server(cfg, "mcpServers", "gli")
        assert changed is False

    def test_returns_false_when_file_missing(self, tmp_path: Path):
        cfg = tmp_path / "nope.json"
        changed = remove_mcp_server(cfg, "mcpServers", "gli")
        assert changed is False

    def test_nested_key_path_removal(self, tmp_path: Path):
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcp": {"servers": {"gli": {"command": "uvx"}}},
                }
            )
        )
        changed = remove_mcp_server(cfg, "mcp.servers", "gli")
        assert changed is True
        data = json.loads(cfg.read_text())
        assert "gli" not in data["mcp"]["servers"]


class TestInstructionsBlock:
    def test_add_to_nonexistent_file(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        changed = add_instructions(md)
        assert changed is True
        content = md.read_text()
        assert GLI_START in content
        assert GLI_END in content
        assert "gli" in content

    def test_add_to_existing_content_preserves_original(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        md.write_text("# My Rules\n\nDo good things.\n")
        changed = add_instructions(md)
        assert changed is True
        content = md.read_text()
        assert "# My Rules" in content
        assert "Do good things." in content
        assert GLI_START in content

    def test_replace_existing_block(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        md.write_text(
            f"# My Rules\n\n{GLI_START}\nOLD CONTENT\n{GLI_END}\n\nMore stuff.\n"
        )
        changed = add_instructions(md)
        assert changed is True
        content = md.read_text()
        assert "OLD CONTENT" not in content
        assert "More stuff." in content
        assert GLI_START in content

    def test_idempotent_when_already_present(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        add_instructions(md)
        content_after_first = md.read_text()
        changed = add_instructions(md)
        assert changed is False
        assert md.read_text() == content_after_first

    def test_remove_block(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        md.write_text(f"# Rules\n\n{GLI_START}\nstuff\n{GLI_END}\n\nAfter.\n")
        changed = remove_instructions(md)
        assert changed is True
        content = md.read_text()
        assert GLI_START not in content
        assert GLI_END not in content
        assert "# Rules" in content
        assert "After." in content

    def test_remove_returns_false_when_no_block(self, tmp_path: Path):
        md = tmp_path / "rules.md"
        md.write_text("# Just rules\n")
        changed = remove_instructions(md)
        assert changed is False

    def test_remove_returns_false_when_file_missing(self, tmp_path: Path):
        md = tmp_path / "nope.md"
        changed = remove_instructions(md)
        assert changed is False
