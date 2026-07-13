"""Tests for installer agent detection — target definitions, path resolution, detection logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.installer.agents import (
    AgentTarget,
    all_targets,
    detect_installed,
)

pytestmark = [pytest.mark.installer]


class TestAllTargets:
    def test_returns_seven_targets(self):
        targets = all_targets()
        assert len(targets) == 7

    def test_target_ids_are_unique(self):
        targets = all_targets()
        ids = [t.id for t in targets]
        assert len(ids) == len(set(ids))

    def test_windsurf_is_bare_config(self):
        targets = {t.id: t for t in all_targets()}
        assert targets["windsurf"].bare_config is True

    def test_non_windsurf_are_typed_config(self):
        targets = {t.id: t for t in all_targets()}
        for tid, t in targets.items():
            if tid != "windsurf":
                assert t.bare_config is False, f"{tid} should not be bare"

    def test_vscode_uses_nested_key(self):
        targets = {t.id: t for t in all_targets()}
        assert targets["vscode"].mcp_key == "mcp.servers"

    def test_zed_uses_context_servers_key(self):
        targets = {t.id: t for t in all_targets()}
        assert targets["zed"].mcp_key == "context_servers"

    def test_all_have_config_paths(self):
        for t in all_targets():
            assert len(t.config_paths) >= 1
            assert all(isinstance(p, Path) for p in t.config_paths)

    def test_all_have_detect_paths(self):
        for t in all_targets():
            assert len(t.detect_paths) >= 1


class TestDetectInstalled:
    def test_detects_agent_when_path_exists(self, tmp_path: Path):
        targets = [
            AgentTarget(
                id="test-agent",
                name="Test Agent",
                config_paths=[tmp_path / "config.json"],
                mcp_key="mcpServers",
                bare_config=False,
                detect_paths=[tmp_path],
            ),
        ]
        installed = detect_installed(targets)
        assert len(installed) == 1
        assert installed[0].id == "test-agent"

    def test_does_not_detect_when_path_missing(self, tmp_path: Path):
        targets = [
            AgentTarget(
                id="missing-agent",
                name="Missing Agent",
                config_paths=[tmp_path / "config.json"],
                mcp_key="mcpServers",
                bare_config=False,
                detect_paths=[tmp_path / "nonexistent"],
            ),
        ]
        installed = detect_installed(targets)
        assert len(installed) == 0

    def test_detects_when_any_of_multiple_paths_exists(self, tmp_path: Path):
        (tmp_path / "real").mkdir()
        targets = [
            AgentTarget(
                id="multi-agent",
                name="Multi Agent",
                config_paths=[tmp_path / "a.json", tmp_path / "b.json"],
                mcp_key="mcpServers",
                bare_config=False,
                detect_paths=[tmp_path / "fake", tmp_path / "real"],
            ),
        ]
        installed = detect_installed(targets)
        assert len(installed) == 1

    def test_default_uses_all_targets(self):
        """Without explicit targets, uses all_targets() — just verify it returns a list."""
        result = detect_installed()
        assert isinstance(result, list)


class TestWindsurfPaths:
    def test_windsurf_config_path_is_codeium(self):
        targets = all_targets()
        windsurf = next(t for t in targets if t.id == "windsurf")
        h = Path.home()
        assert (
            windsurf.config_paths[0] == h / ".codeium" / "windsurf" / "mcp_config.json"
        )
        assert windsurf.detect_paths[0] == h / ".codeium" / "windsurf"
