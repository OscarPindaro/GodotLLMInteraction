"""Stable path resolution for project-wide resources.

This module is intentionally kept at the top level of the package so it has
minimal probability of being moved. Other modules import from here rather
than computing paths relative to their own ``__file__``, which would break
if the importing module is relocated.
"""

from __future__ import annotations

from pathlib import Path

# src/godotllminteraction/paths.py -> src/godotllminteraction -> src -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

GODOT_VERSIONS_FILE: Path = _REPO_ROOT / "godot-versions.txt"
