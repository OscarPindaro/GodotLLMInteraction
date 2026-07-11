from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.paths import ResPath, ScenePath


class TestScenePath:
    def test_root_spellings(self):
        assert ScenePath(".") == ScenePath("") == ScenePath("/") == ScenePath.root()
        assert ScenePath(".").is_root()
        assert str(ScenePath(".")) == "."

    def test_name_and_parent(self):
        path = ScenePath("Player/Body/Sprite")
        assert path.name == "Sprite"
        assert path.parent == ScenePath("Player/Body")
        assert ScenePath("Player").parent.is_root()
        assert ScenePath.root().parent.is_root()  # as in pathlib

    def test_join(self):
        assert ScenePath("Player") / "Sprite" == ScenePath("Player/Sprite")
        assert ScenePath.root() / "Player" == ScenePath("Player")
        assert str(ScenePath("A") / ScenePath("B/C")) == "A/B/C"

    def test_equality_with_strings_and_hashing(self):
        assert ScenePath("A/B") == "A/B"
        assert ScenePath("A//B/") == "A/B"
        assert len({ScenePath("A"), ScenePath("A/")}) == 1

    def test_dotdot_rejected(self):
        with pytest.raises(ValueError, match="may not contain"):
            ScenePath("../Sibling")

    def test_is_within(self):
        assert ScenePath("A/B/C").is_within("A/B")
        assert ScenePath("A/B").is_within("A/B")
        assert not ScenePath("A/Bx").is_within("A/B")
        assert ScenePath("A").is_within(".")

    def test_rebase(self):
        assert ScenePath("A/B/C").rebase("A/B", "X") == ScenePath("X/C")
        assert ScenePath("A/B").rebase("A/B", "X/Y") == ScenePath("X/Y")
        assert ScenePath("Other").rebase("A", "X") is None

    def test_node_path_to(self):
        assert ScenePath("Label").node_path_to("PlateArea") == "../PlateArea"
        assert ScenePath("A/B").node_path_to("A/C/D") == "../C/D"
        assert ScenePath("A").node_path_to("A") == "."
        assert ScenePath(".").node_path_to("A/B") == "A/B"
        assert ScenePath("A/B").node_path_to(".") == "../.."

    def test_resolve_node_path(self):
        assert ScenePath("Label").resolve_node_path("../PlateArea") == ScenePath(
            "PlateArea"
        )
        assert ScenePath("A/B").resolve_node_path(".") == ScenePath("A/B")
        assert ScenePath("A").resolve_node_path("B/C") == ScenePath("A/B/C")
        assert ScenePath("A").resolve_node_path("../../Escapes") is None
        assert ScenePath("A").resolve_node_path("/root/Absolute") is None

    def test_resolve_then_relative_roundtrip(self):
        owner = ScenePath("PlateArea/Icon")
        node_path = "../../Label"
        target = owner.resolve_node_path(node_path)
        assert owner.node_path_to(target) == node_path


class TestResPath:
    def test_str_normalization(self):
        assert str(ResPath("res://a/b.png")) == "res://a/b.png"
        assert str(ResPath("a/b.png")) == "res://a/b.png"
        assert ResPath("res://a/b.png") == "a/b.png"

    def test_parts_name_suffix(self):
        path = ResPath("res://asset/tilemap_packed.png")
        assert path.name == "tilemap_packed.png"
        assert path.stem == "tilemap_packed"
        assert path.suffix == ".png"
        assert path.parent == ResPath("res://asset")

    def test_join(self):
        assert ResPath("res://asset") / "hero.png" == ResPath("res://asset/hero.png")

    def test_to_filesystem(self):
        assert ResPath("res://a/b.png").to_filesystem("/proj") == Path("/proj/a/b.png")

    def test_from_filesystem(self, tmp_path):
        file = tmp_path / "art" / "hero.png"
        file.parent.mkdir()
        file.touch()
        assert ResPath.from_filesystem(file, tmp_path) == ResPath("res://art/hero.png")

    def test_from_filesystem_outside_project_raises(self, tmp_path):
        with pytest.raises(ValueError):
            ResPath.from_filesystem("/etc/passwd", tmp_path)

    def test_hashable(self):
        assert len({ResPath("res://a.png"), ResPath("a.png")}) == 1
