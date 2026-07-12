"""Fixtures for e2e tests that need real Godot binaries.

Shared helper functions live in ``tests/e2e/_helpers.py`` so they can be
imported by test modules. This file only provides pytest fixtures.
"""

from __future__ import annotations

import json

import pytest

from tests.e2e._helpers import (
    dump_extension_api,
    godot_binary_path,
)


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
