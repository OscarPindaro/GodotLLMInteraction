"""E2e test: verify real .tscn scenes pass Godot's --check-only validation.

Uses the 4.5.0 Godot binary to check scenes from the open-rpg 4.5.0 project.
This validates that the scenes are not just parseable by our Python parser,
but are actually valid Godot scenes that can be loaded by the engine.

The test auto-imports the project (runs `--headless --import`) on first run
to generate the `.godot/` cache, so no manual Godot editor opening is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e._helpers import check_scene, godot_binary_path

pytestmark = [pytest.mark.tscn]

SCENES_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "open_rpg_4_5_0"

SCENE_NAMES = [
    "CombatAI.tscn",
    "gamepiece.tscn",
    "ScreenTransition.tscn",
    "Trigger.tscn",
    "ui_damage_label.tscn",
]


@pytest.mark.parametrize("scene_name", SCENE_NAMES)
def test_godot_check_only_on_real_scene_4_5_0(scene_name):
    """Godot --check-only should pass on each real scene."""
    binary = godot_binary_path("4.5.0")
    if binary is None:
        pytest.skip("Godot 4.5.0 binary not installed")

    scene_path = SCENES_DIR / scene_name
    if not scene_path.exists():
        pytest.skip(f"Scene fixture not found: {scene_path}")

    result = check_scene(binary, SCENES_DIR, scene_path.name)

    assert result.returncode == 0, (
        f"Godot --check-only failed for {scene_name} (exit {result.returncode}):\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
