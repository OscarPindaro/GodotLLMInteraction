from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.godot_check import _as_res_target

pytestmark = [pytest.mark.tscn]


class TestAsResTarget:
    def test_already_res_path_passes_through(self):
        assert (
            _as_res_target("res://scenes/door.tscn", Path("."))
            == "res://scenes/door.tscn"
        )

    def test_project_godot_passes_through(self):
        assert _as_res_target("project.godot", Path(".")) == "project.godot"

    def test_filesystem_path_relative_to_project_dir(self, tmp_path):
        (tmp_path / "scenes").mkdir()
        (tmp_path / "scenes" / "a.tscn").touch()
        assert _as_res_target("scenes/a.tscn", tmp_path) == "res://scenes/a.tscn"

    def test_absolute_filesystem_path(self, tmp_path):
        (tmp_path / "a.tscn").touch()
        absolute = str(tmp_path / "a.tscn")
        assert _as_res_target(absolute, tmp_path) == "res://a.tscn"

    def test_nonexistent_path_passes_through_as_absolute_filesystem_path(
        self, tmp_path
    ):
        result = _as_res_target("missing/a.tscn", tmp_path)
        assert result == str((tmp_path / "missing" / "a.tscn").resolve())

    def test_path_outside_project_passes_through_as_absolute_filesystem_path(
        self, tmp_path
    ):
        project = tmp_path / "project"
        project.mkdir()
        outside = tmp_path / "elsewhere.tscn"
        outside.touch()
        assert _as_res_target(str(outside), project) == str(outside.resolve())
