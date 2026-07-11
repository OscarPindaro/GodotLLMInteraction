from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.parser import parse_scene
from godotllminteraction.tscn.writer import dump_scene

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = sorted((_REPO_ROOT / "tests" / "data" / "scenes").glob("*.tscn"))
# Secondary, non-load-bearing coverage: whatever scenes the surrounding repo
# happens to contain right now.
_REPO_SCENES = sorted(
    p
    for p in _REPO_ROOT.rglob("*.tscn")
    if ".godot" not in p.parts and "tests" not in p.parts
)


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(_REPO_ROOT)) for p in paths]


@pytest.mark.parametrize("path", _FIXTURES, ids=_ids(_FIXTURES))
class TestFixtureRoundTrip:
    def test_byte_for_byte(self, path: Path):
        text = path.read_text()
        assert dump_scene(parse_scene(text)) == text

    def test_idempotent(self, path: Path):
        once = dump_scene(parse_scene(path.read_text()))
        assert dump_scene(parse_scene(once)) == once


@pytest.mark.parametrize("path", _REPO_SCENES, ids=_ids(_REPO_SCENES))
def test_repo_scene_roundtrip(path: Path):
    text = path.read_text()
    assert dump_scene(parse_scene(text)) == text


class TestParsedStructure:
    def test_sprite_frames_fixture(self):
        scene = parse_scene(
            (_REPO_ROOT / "tests/data/scenes/sprite_frames.tscn").read_text()
        )
        assert scene.header.uid == "uid://c2test0sprites"
        assert [e.id for e in scene.ext_resources] == ["1_atlas"]
        assert [s.type for s in scene.sub_resources] == [
            "AtlasTexture",
            "AtlasTexture",
            "SpriteFrames",
        ]
        assert scene.root().name == "Actor"
        assert scene.root().path() == "."
        sprite = scene.node("AnimatedSprite2D")
        assert sprite is not None
        assert sprite.type == "AnimatedSprite2D"
        assert [n.path() for n in scene.children(".")] == [
            "AnimatedSprite2D",
            "CollisionPolygon2D",
        ]

    def test_connections_fixture(self):
        scene = parse_scene(
            (_REPO_ROOT / "tests/data/scenes/connections.tscn").read_text()
        )
        assert len(scene.connections) == 3
        first = scene.connections[0]
        assert first.signal == "body_entered"
        assert first.from_path == "Button"
        assert first.to_path == "."
        assert first.method == "_on_button_body_entered"

    def test_instances_fixture(self):
        scene = parse_scene(
            (_REPO_ROOT / "tests/data/scenes/instances.tscn").read_text()
        )
        actor = scene.node("Actor")
        assert actor.is_instance
        assert actor.type is None

    def test_subtree_and_paths(self):
        scene = parse_scene(
            (_REPO_ROOT / "tests/data/scenes/ui_and_paths.tscn").read_text()
        )
        plate_subtree = [n.path() for n in scene.subtree("PlateArea")]
        assert plate_subtree == [
            "PlateArea",
            "PlateArea/CollisionShape2D",
            "PlateArea/Icon",
        ]
        assert scene.node("PlateArea/Icon").parent == "PlateArea"

    def test_parse_error_on_non_scene_file(self):
        from godotllminteraction.tscn.exceptions import ParseError

        with pytest.raises(ParseError):
            parse_scene('[gd_resource type="Resource"]\n')
        with pytest.raises(ParseError):
            parse_scene("")
