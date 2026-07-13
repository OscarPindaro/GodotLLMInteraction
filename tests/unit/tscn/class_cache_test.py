"""Unit tests for the class_cache module (ClassResolver / ClassInfo)."""

from __future__ import annotations

from pathlib import Path


from godotllminteraction.tscn.class_cache import ClassInfo, ClassResolver


def _write_gd(project: Path, rel: str, content: str, uid: str | None = None) -> Path:
    """Create a .gd file (and optional .uid companion) inside *project*."""
    gd = project / rel
    gd.parent.mkdir(parents=True, exist_ok=True)
    gd.write_text(content, encoding="utf-8")
    if uid is not None:
        gd.with_suffix(gd.suffix + ".uid").write_text(uid, encoding="utf-8")
    return gd


# --------------------------------------------------------------- basic scanning


def test_scan_finds_class_name_and_extends(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "scripts/player.gd",
        "class_name Player extends CharacterBody2D\n",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Player")
    assert info is not None
    assert info.class_name == "Player"
    assert info.base_type == "CharacterBody2D"
    assert info.script_path == "res://scripts/player.gd"


def test_scan_same_line_class_and_extends(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "gamepiece.gd",
        "class_name Gamepiece extends Path2D\n",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Gamepiece")
    assert info is not None
    assert info.base_type == "Path2D"


def test_scan_separate_line_class_and_extends(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "enemy.gd",
        "extends Node2D\nclass_name Enemy\n",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Enemy")
    assert info is not None
    assert info.base_type == "Node2D"


def test_missing_extends_defaults_to_refcounted(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "item.gd",
        "class_name Item\nvar count = 0\n",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Item")
    assert info is not None
    assert info.base_type == "RefCounted"


def test_uid_file_read(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "actor.gd",
        "class_name Actor extends Node\n",
        uid="uid://abc123xyz",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Actor")
    assert info is not None
    assert info.uid == "uid://abc123xyz"


def test_no_uid_file_returns_none(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "thing.gd",
        "class_name Thing extends Node\n",
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Thing")
    assert info is not None
    assert info.uid is None


def test_resolve_unknown_returns_none(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "x.gd",
        "class_name X extends Node\n",
    )
    resolver = ClassResolver(tmp_path)
    assert resolver.resolve("NonExistent") is None


# --------------------------------------------------------------- rescan-on-miss


def test_rescan_finds_new_file(tmp_path: Path) -> None:
    _write_gd(
        tmp_path,
        "first.gd",
        "class_name First extends Node\n",
    )
    resolver = ClassResolver(tmp_path)
    # Trigger initial scan.
    assert resolver.resolve("First") is not None
    assert resolver.resolve("Second") is None
    # Add a new file after the initial scan.
    _write_gd(
        tmp_path,
        "second.gd",
        "class_name Second extends Node2D\n",
    )
    # Rescan-on-miss should find it now.
    info = resolver.resolve("Second")
    assert info is not None
    assert info.base_type == "Node2D"


# --------------------------------------------------------------- edge cases


def test_multiple_classes_in_project(tmp_path: Path) -> None:
    _write_gd(tmp_path, "a.gd", "class_name A extends Node\n")
    _write_gd(tmp_path, "b.gd", "class_name B extends Node2D\n")
    _write_gd(tmp_path, "c.gd", "class_name C extends Resource\n")
    resolver = ClassResolver(tmp_path)
    all_classes = resolver.all_classes()
    assert {"A", "B", "C"} <= set(all_classes.keys())


def test_nested_inheritance_custom_extends_custom(tmp_path: Path) -> None:
    """A custom class extending another custom class (not just built-ins).

    class_name A extends Node
    class_name B extends A

    The resolver stores the raw extends value ("A"), not the transitive
    built-in base.  The caller (scene_builder) is responsible for chaining
    resolution if needed.
    """
    _write_gd(tmp_path, "a.gd", "class_name A extends Node\n")
    _write_gd(tmp_path, "b.gd", "class_name B extends A\n")
    resolver = ClassResolver(tmp_path)

    info_a = resolver.resolve("A")
    assert info_a is not None
    assert info_a.base_type == "Node"

    info_b = resolver.resolve("B")
    assert info_b is not None
    assert info_b.base_type == "A"
    assert info_b.script_path == "res://b.gd"


def test_file_without_class_name_is_ignored(tmp_path: Path) -> None:
    _write_gd(tmp_path, "plain.gd", "extends Node\nvar x = 1\n")
    resolver = ClassResolver(tmp_path)
    assert resolver.resolve("plain") is None
    assert resolver.all_classes() == {}


def test_class_info_model_fields() -> None:
    info = ClassInfo(
        class_name="Test",
        base_type="Node",
        script_path="res://test.gd",
        uid="uid://test",
    )
    assert info.class_name == "Test"
    assert info.base_type == "Node"
    assert info.script_path == "res://test.gd"
    assert info.uid == "uid://test"


def test_path_based_extends(tmp_path: Path) -> None:
    """Path-based extends (extends "res://...") should not crash."""
    _write_gd(
        tmp_path,
        "child.gd",
        'class_name Child extends "res://parent.gd"\n',
    )
    resolver = ClassResolver(tmp_path)
    info = resolver.resolve("Child")
    assert info is not None
    # The base_type should be the path string (stripped of quotes).
    assert "parent.gd" in info.base_type
