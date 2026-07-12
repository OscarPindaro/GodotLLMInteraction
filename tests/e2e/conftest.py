"""Fixtures for e2e tests that need real Godot binaries.

Shared helper functions live in ``tests/e2e/_helpers.py`` so they can be
imported by test modules. This file only provides pytest fixtures.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.e2e._helpers import (
    dump_extension_api,
    godot_binary_path,
)

SCENES_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "scenes"


@pytest.fixture(autouse=True, scope="session")
def _clean_godot_cache():
    """Remove .godot/ cache dirs from scene fixture projects before tests.

    Ensures tests always run from a clean state (auto-import happens
    fresh each session via the check_scene helper).
    """
    if SCENES_DATA_DIR.is_dir():
        for cache_dir in SCENES_DATA_DIR.glob("*/.godot"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)
    yield
    # Clean up after tests too
    if SCENES_DATA_DIR.is_dir():
        for cache_dir in SCENES_DATA_DIR.glob("*/.godot"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)


@pytest.fixture
def godot_binary_for_version(tmp_path_factory: pytest.TempPathFactory):
    """Factory fixture: given a version string, returns the extension_api.json dict."""
    cache: dict[str, dict] = {}

    def _get(version: str) -> dict:
        if version in cache:
            return cache[version]
        binary = godot_binary_path(version)
        if binary is None:
            pytest.skip(f"Godot binary for version {version} not installed")
        out_dir = tmp_path_factory.mktemp(f"godot_{version}")
        dump_path = dump_extension_api(binary, out_dir)
        data = json.loads(dump_path.read_text())
        cache[version] = data
        return data

    return _get
