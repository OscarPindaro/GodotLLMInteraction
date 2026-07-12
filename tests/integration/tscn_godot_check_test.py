"""Ground-truth gate: Godot itself must accept what the tscn library produces.

Skipped automatically when no Godot binary is available (see conftest.py).
Scenes are checked inside the repository project so their res:// asset
references resolve; scenario outputs are written under the gitignored out/
directory, which doubles as the place to open them in the editor.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from godotllminteraction.tscn import (
    OpsFile,
    apply_ops_file,
    check_scene,
    dump_scene,
    initial_scene,
    parse_scene,
)

pytestmark = [pytest.mark.tscn]

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def imported_project(godot_binary: str) -> Path:
    """Run Godot's asset import once so res:// textures under tests/data/
    (plain PNGs, not pre-imported) are loadable by --check-only."""
    result = check_scene(
        "project.godot", project_dir=_REPO_ROOT, godot=godot_binary, timeout=600
    )
    if not result.ok:
        pytest.fail(f"godot --import failed:\n{result.output}")
    return _REPO_ROOT


_FIXTURES = sorted((_REPO_ROOT / "tests" / "data" / "scenes").glob("*.tscn"))
_SCENARIOS = sorted(
    p
    for p in (_REPO_ROOT / "tests" / "data" / "tscn_scenarios").glob("*.yaml")
    if "error" not in p.stem
)


@pytest.mark.parametrize("scene_path", _FIXTURES, ids=[p.name for p in _FIXTURES])
def test_fixture_scene_passes_godot_check(
    godot_binary: str, imported_project: Path, scene_path: Path
):
    result = check_scene(
        f"res://{scene_path.relative_to(_REPO_ROOT)}",
        project_dir=_REPO_ROOT,
        godot=godot_binary,
    )
    assert result.ok, result.output


@pytest.mark.parametrize("scenario_path", _SCENARIOS, ids=[p.stem for p in _SCENARIOS])
def test_scenario_output_passes_godot_check(
    godot_binary: str, imported_project: Path, scenario_path: Path
):
    spec = yaml.safe_load(scenario_path.read_text())
    ops_file = OpsFile.model_validate(
        {
            "create": spec.get("create"),
            "strict": spec.get("strict", True),
            "operations": spec.get("operations", []),
        }
    )
    if spec.get("initial"):
        scene = parse_scene(
            (_REPO_ROOT / "tests" / "data" / "scenes" / spec["initial"]).read_text()
        )
    else:
        scene = initial_scene(ops_file)
    result = apply_ops_file(ops_file, scene)

    out_path = _REPO_ROOT / "out" / "tscn_scenarios" / scenario_path.stem
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump_scene(result.scene))

    check = check_scene(
        f"res://{out_path.relative_to(_REPO_ROOT)}",
        project_dir=_REPO_ROOT,
        godot=godot_binary,
    )
    assert check.ok, check.output
