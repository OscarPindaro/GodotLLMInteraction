"""YAML-driven end-to-end scenarios.

Each tests/data/tscn_scenarios/*.tscn.yaml file describes an initial scene
(a fixture from tests/data/scenes, or `create:` for a new one), a list of
operations, and expectations on the outcome. Successful scenarios must also
pass full spec validation, and re-applying the ops must be a byte-identical
no-op (the global idempotency invariant).

Set GLI_SCENARIO_OUT_DIR (e.g. to `out/tscn_scenarios`) to also write every
produced scene to disk so it can be opened in the Godot editor.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from godotllminteraction.tscn import (
    OpsFile,
    TscnError,
    apply_ops_file,
    dump_scene,
    initial_scene,
    parse_scene,
    validate_scene,
)

_DATA = Path(__file__).resolve().parents[2] / "tests" / "data"
_SCENARIOS = sorted((_DATA / "tscn_scenarios").glob("*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("scenario_path", _SCENARIOS, ids=[p.stem for p in _SCENARIOS])
def test_scenario(scenario_path: Path):
    spec = _load(scenario_path)
    expect = spec.get("expect", {})

    ops_file = OpsFile.model_validate(
        {
            "create": spec.get("create"),
            "strict": spec.get("strict", True),
            "operations": spec.get("operations", []),
        }
    )
    if spec.get("initial"):
        scene = parse_scene((_DATA / "scenes" / spec["initial"]).read_text())
    else:
        scene = initial_scene(ops_file)

    if "error" in expect:
        with pytest.raises(TscnError) as exc_info:
            apply_ops_file(ops_file, scene)
        assert re.search(expect["error"], str(exc_info.value)), str(exc_info.value)
        return

    result = apply_ops_file(ops_file, scene)
    text = dump_scene(result.scene)

    out_dir = os.environ.get("GLI_SCENARIO_OUT_DIR")
    if out_dir:
        out_path = Path(out_dir) / scenario_path.stem  # *.tscn.yaml -> *.tscn
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)

    for path in expect.get("node_exists", []):
        assert result.scene.node(path) is not None, (
            f"expected node {path!r} in:\n{text}"
        )
    for snippet in expect.get("contains", []):
        assert snippet in text, f"expected {snippet!r} in:\n{text}"
    for snippet in expect.get("not_contains", []):
        assert snippet not in text, f"did not expect {snippet!r} in:\n{text}"

    # Every successful scenario must produce a spec-clean scene...
    report = validate_scene(result.scene)
    assert report.ok, [str(e) for e in report.errors]

    # ...that round-trips...
    assert dump_scene(parse_scene(text)) == text

    # ...and re-applying the same ops must change nothing (idempotency).
    again = apply_ops_file(ops_file, result.scene)
    assert dump_scene(again.scene) == text
    assert all(not r.changed for r in again.results)
