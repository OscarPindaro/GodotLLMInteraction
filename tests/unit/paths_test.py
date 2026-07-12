"""Test that GODOT_VERSIONS_FILE path is always resolvable.

This guards against breakage when files are moved: if someone relocates
``paths.py`` or ``godot-versions.txt``, this test will fail immediately.
"""

from __future__ import annotations

from pathlib import Path

from godotllminteraction.paths import GODOT_VERSIONS_FILE


def test_godot_versions_file_path_is_resolvable():
    """The path object should be a valid absolute Path."""
    assert isinstance(GODOT_VERSIONS_FILE, Path)
    assert GODOT_VERSIONS_FILE.is_absolute()


def test_godot_versions_file_exists():
    """The godot-versions.txt file should exist at the resolved path."""
    assert GODOT_VERSIONS_FILE.exists(), (
        f"godot-versions.txt not found at {GODOT_VERSIONS_FILE}. "
        "If files were moved, update godotllminteraction/paths.py."
    )


def test_godot_versions_file_is_in_repo_root():
    """The file should be at the repo root (parent of src/)."""
    # GODOT_VERSIONS_FILE = repo_root / "godot-versions.txt"
    # repo_root should contain pyproject.toml
    repo_root = GODOT_VERSIONS_FILE.parent
    assert (repo_root / "pyproject.toml").exists(), (
        f"Expected pyproject.toml in {repo_root} (parent of godot-versions.txt). "
        "If the project structure changed, update godotllminteraction/paths.py."
    )


def test_godot_versions_file_has_content():
    """The file should not be empty."""
    content = GODOT_VERSIONS_FILE.read_text().strip()
    assert content, f"godot-versions.txt at {GODOT_VERSIONS_FILE} is empty"
    lines = [
        line
        for line in content.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) >= 1, "godot-versions.txt should list at least one version"
