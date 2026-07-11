"""Core library for reading, editing, and writing Godot .tscn scene files.

Frontend-free: importable as a plain Python API. The `gli` CLI (and any
future MCP server) are thin layers over what is exported here.

Typical use:

    from godotllminteraction import tscn

    scene = tscn.load_scene(Path("scenes/door.tscn"))
    result = tscn.apply_operations(
        scene, [tscn.AddNode(path="Hinge", type="Sprite2D")]
    )
    tscn.save_scene(result.scene, Path("scenes/door.tscn"))
"""

from __future__ import annotations

from pathlib import Path

from godotllminteraction.tscn.exceptions import (
    OperationError,
    ParseError,
    SceneValidationError,
    TscnError,
)
from godotllminteraction.tscn.godot_check import (
    GodotCheckResult,
    GodotNotFoundError,
    check_scene,
    find_godot,
)
from godotllminteraction.tscn.operations import (
    AddExtResource,
    OpType,
    AddNode,
    ApplyResult,
    AttachScript,
    ConnectSignal,
    CreateSubResource,
    DeleteNode,
    DetachScript,
    DisconnectSignal,
    MoveNode,
    Operation,
    OpResult,
    RenameNode,
    UpdateProperties,
    apply_operation,
    apply_operations,
)
from godotllminteraction.tscn.parser import parse_scene
from godotllminteraction.tscn.paths import ResPath, ScenePath
from godotllminteraction.tscn.scene import Scene
from godotllminteraction.tscn.specs import SpecProvider, default_provider
from godotllminteraction.tscn.tree import TreeNode, build_tree, render_tree
from godotllminteraction.tscn.validation import (
    Issue,
    ValidationReport,
    validate_scene,
)
from godotllminteraction.tscn.writer import dump_scene
from godotllminteraction.tscn.yaml_ops import (
    OpsFile,
    OpsFileError,
    apply_ops_file,
    initial_scene,
    load_ops_file,
)


def load_scene(path: Path) -> Scene:
    return parse_scene(Path(path).read_text())


def save_scene(scene: Scene, path: Path) -> None:
    Path(path).write_text(dump_scene(scene))


__all__ = [
    "AddExtResource",
    "AddNode",
    "ApplyResult",
    "AttachScript",
    "ConnectSignal",
    "CreateSubResource",
    "DeleteNode",
    "DetachScript",
    "DisconnectSignal",
    "GodotCheckResult",
    "GodotNotFoundError",
    "Issue",
    "MoveNode",
    "OpResult",
    "Operation",
    "OpType",
    "OperationError",
    "OpsFile",
    "OpsFileError",
    "ParseError",
    "ResPath",
    "RenameNode",
    "Scene",
    "ScenePath",
    "SceneValidationError",
    "SpecProvider",
    "TreeNode",
    "TscnError",
    "UpdateProperties",
    "ValidationReport",
    "apply_operation",
    "apply_operations",
    "apply_ops_file",
    "build_tree",
    "check_scene",
    "default_provider",
    "dump_scene",
    "find_godot",
    "initial_scene",
    "load_ops_file",
    "load_scene",
    "parse_scene",
    "render_tree",
    "save_scene",
    "validate_scene",
]
