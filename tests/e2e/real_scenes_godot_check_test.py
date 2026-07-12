"""E2e test: verify real .tscn scenes pass Godot's --check-only validation.

Uses the 4.4.0 Godot binary to check scenes from the open-rpg 4.4.0 project.
This validates that the scenes are not just parseable by our Python parser,
but are actually valid Godot scenes that can be loaded by the engine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.e2e._helpers import godot_binary_path

SCENES_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "open_rpg_4_4_0"

SCENE_NAMES = [
    "CombatAI.tscn",
    "gamepiece.tscn",
    "ScreenTransition.tscn",
    "Trigger.tscn",
    "ui_damage_label.tscn",
]


@pytest.mark.parametrize("scene_name", SCENE_NAMES)
def test_godot_check_only_on_real_scene(scene_name):
    """Godot --check-only should pass on each real scene."""
    binary = godot_binary_path("4.4.0")
    if binary is None:
        pytest.skip("Godot 4.4.0 binary not installed")

    scene_path = SCENES_DIR / scene_name
    if not scene_path.exists():
        pytest.skip(f"Scene fixture not found: {scene_path}")

    result = subprocess.run(
        [
            binary,
            "--headless",
            "--check-only",
            "--path",
            str(SCENES_DIR),
            "--quit",
            scene_path.name,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # --check-only returns 0 if the scene loads successfully
    assert result.returncode == 0, (
        f"Godot --check-only failed for {scene_name} (exit {result.returncode}):\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
