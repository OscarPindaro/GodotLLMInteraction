"""Typed, deterministic, idempotent editing operations over a Scene.

Every operation describes a *desired state*. Applying an operation whose
state already holds is a recorded no-op (`OpResult.changed` is False), never
an error; errors are reserved for genuine conflicts (same path, different
type; missing parent; reparent cycle; ...). Combined with the writer's
canonical spacing this yields two tested invariants:

- determinism: the same operation on the same scene always produces the
  identical file (generated resource ids are hash-derived, never random);
- reversibility: add followed by delete restores the original bytes, and
  applying the same operation list twice is byte-identical to applying it
  once.

Operations happen in memory: `apply_operations` deep-copies the input scene,
applies every operation to the copy, and returns the edited copy in
`ApplyResult.scene`. Writing that scene to the filesystem is the caller's
last step (`tscn.save_scene`, or the `gli tscn apply` command, which writes
the file only after the whole batch succeeded). The deep copy just
guarantees a failed batch can never leave a half-edited scene object behind.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from godotllminteraction.tscn.exceptions import OperationError
from godotllminteraction.tscn.paths import ScenePath
from godotllminteraction.tscn.scene import (
    ConnectionEntry,
    ExtResourceEntry,
    NodeEntry,
    Scene,
    SubResourceEntry,
    normalize_path,
)
from godotllminteraction.tscn.specs import SpecProvider, default_provider
from godotllminteraction.tscn.validation import (
    ValidationReport,
    validate_connection_signal,
    validate_properties,
)
from godotllminteraction.tscn.values import (
    GArray,
    GBool,
    GCall,
    GDict,
    GFloat,
    GInt,
    GNodePath,
    GString,
    GodotValue,
    ext_resource_ref,
    format_value,
    parse_value,
    values_equal,
)

PropertyInput = Union[str, int, float, bool]
"""Property values in operations are Godot literal strings ('Vector2(1, 2)',
'"text"', 'ExtResource("1_x")') or plain numbers/booleans."""


def _to_value(value: PropertyInput) -> GodotValue:
    if isinstance(value, bool):
        return GBool(value=value)
    if isinstance(value, int):
        return GInt(value=value)
    if isinstance(value, float):
        return GFloat(value=value)
    return parse_value(value)


# --- Operation models --------------------------------------------------------

_PATH_DESCRIPTION = (
    "Scene path of the node, mirroring tscn's parent= convention: "
    "'.' is the root, 'Player' a child of the root, 'Player/Sprite' deeper."
)
_PROPERTIES_DESCRIPTION = (
    "Property values in Godot literal syntax as strings "
    "('Vector2(1, 2)', '\"text\"', 'ExtResource(\"1_x\")'), "
    "or plain numbers/booleans."
)


class OpType(StrEnum):
    ADD_NODE = "add_node"
    DELETE_NODE = "delete_node"
    UPDATE_PROPERTIES = "update_properties"
    RENAME_NODE = "rename_node"
    MOVE_NODE = "move_node"
    ATTACH_SCRIPT = "attach_script"
    DETACH_SCRIPT = "detach_script"
    ADD_EXT_RESOURCE = "add_ext_resource"
    CREATE_SUB_RESOURCE = "create_sub_resource"
    CONNECT_SIGNAL = "connect_signal"
    DISCONNECT_SIGNAL = "disconnect_signal"


class AddNode(BaseModel):
    """Add a node to the scene tree (or confirm an identical one exists)."""

    op: Literal[OpType.ADD_NODE] = OpType.ADD_NODE
    path: str = Field(
        description="Scene path of the new node; every segment but the last must already exist."
    )
    type: str | None = Field(
        None,
        description="Godot class of the node (e.g. 'Sprite2D'). Exactly one of 'type' or 'instance' must be given.",
    )
    instance: str | None = Field(
        None,
        description="For instanced-scene nodes: an 'ExtResource(\"id\")' literal pointing at a PackedScene ext_resource, instead of 'type'.",
    )
    properties: dict[str, PropertyInput] = Field(
        default_factory=dict, description=_PROPERTIES_DESCRIPTION
    )
    groups: list[str] | None = Field(
        None, description="Node group names, as in the editor's Groups dock."
    )
    index: int | None = Field(
        None,
        description="Position among siblings (the node heading's index= attribute). "
        "Leave unset to let tree order decide; mainly relevant when mixing with "
        "inherited/instanced children.",
    )
    # No unique_id field: it's Godot's own bookkeeping (assigned by the editor
    # on save, Godot 4.6+) — the tool never assigns one for new nodes and
    # never touches existing ones.


class DeleteNode(BaseModel):
    """Delete a node (and, by default, its whole subtree).

    Also drops [connection]s into the deleted subtree, and any sub_resource
    that becomes unreferenced as a direct result (transitively — deleting the
    last node referencing a SpriteFrames also drops the AtlasTextures it
    alone referenced). Resources that were already orphaned beforehand, for
    unrelated reasons, are left untouched.
    """

    op: Literal[OpType.DELETE_NODE] = OpType.DELETE_NODE
    path: str = Field(description=_PATH_DESCRIPTION)
    recursive: bool = Field(
        True,
        description="Also delete all descendants. With false, deleting a node that has children is an error.",
    )


class UpdateProperties(BaseModel):
    """Set and/or remove one or more properties on an existing node."""

    op: Literal[OpType.UPDATE_PROPERTIES] = OpType.UPDATE_PROPERTIES
    path: str = Field(description=_PATH_DESCRIPTION)
    properties: dict[str, PropertyInput] = Field(
        default_factory=dict, description=_PROPERTIES_DESCRIPTION
    )
    remove: list[str] = Field(
        default_factory=list,
        description="Property names to drop from the node (reverting them to their class defaults).",
    )


class RenameNode(BaseModel):
    """Rename a node; descendant paths, connections, and NodePath property
    values that point at the subtree are rewritten."""

    op: Literal[OpType.RENAME_NODE] = OpType.RENAME_NODE
    path: str = Field(description=_PATH_DESCRIPTION)
    new_name: str = Field(
        description="The node's new name (a single segment, not a path)."
    )


class MoveNode(BaseModel):
    """Reparent a node; descendant paths, connections, and NodePath property
    values that point at the subtree are rewritten."""

    op: Literal[OpType.MOVE_NODE] = OpType.MOVE_NODE
    path: str = Field(description=_PATH_DESCRIPTION)
    new_parent: str = Field(
        description="Scene path of the new parent ('.' for the root)."
    )
    index: int | None = Field(
        None,
        description="Position among the new siblings (the node heading's index= attribute); unset keeps natural order.",
    )


class AttachScript(BaseModel):
    """Attach a script to a node, reusing or adding the Script ext_resource."""

    op: Literal[OpType.ATTACH_SCRIPT] = OpType.ATTACH_SCRIPT
    path: str = Field(description=_PATH_DESCRIPTION)
    script_path: str = Field(description="res:// path of the .gd script file.")


class DetachScript(BaseModel):
    """Remove a node's script; the Script ext_resource is dropped too if nothing else references it."""

    op: Literal[OpType.DETACH_SCRIPT] = OpType.DETACH_SCRIPT
    path: str = Field(description=_PATH_DESCRIPTION)


class AddExtResource(BaseModel):
    """Declare an external resource (texture, script, packed scene, ...) the scene can reference."""

    op: Literal[OpType.ADD_EXT_RESOURCE] = OpType.ADD_EXT_RESOURCE
    type: str = Field(
        description="Godot resource class, e.g. 'Texture2D', 'Script', 'PackedScene'."
    )
    path: str = Field(description="res:// path of the external file.")
    id: str | None = Field(
        None,
        description='Scene-local resource id used by ExtResource("...") references. '
        "Leave unset for a generated Godot-shaped id, or choose a readable one "
        "('tile_atlas', 'player_script') — this is the right place for "
        "human/LLM-friendly names.",
    )


class CreateSubResource(BaseModel):
    """Embed a resource (shape, SpriteFrames, ...) inside the scene file."""

    op: Literal[OpType.CREATE_SUB_RESOURCE] = OpType.CREATE_SUB_RESOURCE
    type: str = Field(description="Godot Resource subclass, e.g. 'RectangleShape2D'.")
    id: str | None = Field(
        None,
        description='Scene-local resource id used by SubResource("...") references. '
        "Leave unset for a generated id, or choose a readable one.",
    )
    properties: dict[str, PropertyInput] = Field(
        default_factory=dict, description=_PROPERTIES_DESCRIPTION
    )


class ConnectSignal(BaseModel):
    """Add a [connection] wiring a signal to a method on another node.

    In scene files a connection target is always a method name on the target
    node's script — lambdas/callables exist only in code.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    op: Literal[OpType.CONNECT_SIGNAL] = OpType.CONNECT_SIGNAL
    from_: str = Field(
        alias="from", description="Scene path of the node emitting the signal."
    )
    to: str = Field(description="Scene path of the node whose method is called.")
    signal: str = Field(
        description="Signal name on the emitting node's class (e.g. 'body_entered')."
    )
    method: str = Field(
        description="Name of the receiving method on the target node's script."
    )
    flags: int | None = Field(
        None,
        description="Godot ConnectFlags bitmask (e.g. 3 = DEFERRED|PERSIST); unset for default.",
    )
    binds: str | None = Field(
        None,
        description="Extra bound arguments as a Godot array literal, e.g. '[1, \"two\"]'.",
    )


class DisconnectSignal(BaseModel):
    """Remove the [connection] matching (signal, from, to, method)."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    op: Literal[OpType.DISCONNECT_SIGNAL] = OpType.DISCONNECT_SIGNAL
    from_: str = Field(alias="from", description="Scene path of the emitting node.")
    to: str = Field(description="Scene path of the target node.")
    signal: str = Field(description="Signal name.")
    method: str = Field(description="Receiving method name.")


Operation = Annotated[
    Union[
        AddNode,
        DeleteNode,
        UpdateProperties,
        RenameNode,
        MoveNode,
        AttachScript,
        DetachScript,
        AddExtResource,
        CreateSubResource,
        ConnectSignal,
        DisconnectSignal,
    ],
    Field(discriminator="op"),
]


class OpResult(BaseModel):
    """What one operation did (the unit of `gli tscn apply --json` output)."""

    op: OpType = Field(description="Which operation this result belongs to.")
    changed: bool = Field(
        description="False when the desired state already held and nothing was modified."
    )
    affected_paths: list[str] = Field(
        default_factory=list,
        description="Scene paths the operation touched (for renames/moves: old and new).",
    )
    allocated_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Ids allocated or resolved by the operation, e.g. {'id': '1_a4ypi'} "
        "for resource operations.",
    )
    report: ValidationReport = Field(
        default_factory=ValidationReport,
        description="Spec-validation issues; in non-strict mode errors land here instead of aborting.",
    )


class ApplyResult(BaseModel):
    scene: Scene
    results: list[OpResult] = []

    @property
    def changed(self) -> bool:
        return any(r.changed for r in self.results)


# --- Deterministic id allocation ---------------------------------------------

_SUFFIX_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _hash_suffix(*parts: str, length: int = 5) -> str:
    """Godot-shaped id suffix ('a4ypi'), derived from a hash instead of RNG."""
    digest = hashlib.sha256("\x00".join(parts).encode()).digest()
    number = int.from_bytes(digest[:8], "big")
    chars = []
    for _ in range(length):
        number, rem = divmod(number, len(_SUFFIX_ALPHABET))
        chars.append(_SUFFIX_ALPHABET[rem])
    return "".join(chars)


def _recompute_load_steps(scene: Scene) -> None:
    # load_steps is deprecated (ignored by Godot when present); it is kept
    # only if the file already had it, and never added to files without it.
    if "load_steps" not in scene.header.attributes:
        return
    steps = 1 + len(scene.ext_resources) + len(scene.sub_resources)
    if steps <= 1:
        del scene.header.attributes["load_steps"]
        return
    attributes = {"load_steps": GInt(value=steps)}
    attributes.update(
        (k, v) for k, v in scene.header.attributes.items() if k != "load_steps"
    )
    scene.header.attributes = attributes


# --- Shared helpers -----------------------------------------------------------


def _scene_path(raw: str) -> ScenePath:
    try:
        return ScenePath(raw)
    except ValueError as exc:
        raise OperationError(str(exc)) from exc


def _rewrite_tree_path(path: str, old: str, new: str) -> str | None:
    """`path` with the `old` subtree prefix replaced by `new`; None if unaffected."""
    rebased = ScenePath(path).rebase(old, new)
    return None if rebased is None else str(rebased)


def _require_node(scene: Scene, path: str, *, role: str = "node") -> NodeEntry:
    node = scene.node(path)
    if node is None:
        raise OperationError(f"{role} {normalize_path(path)!r} does not exist")
    return node


def _check_strict(report: ValidationReport, strict: bool) -> None:
    if strict and not report.ok:
        raise OperationError("; ".join(str(e) for e in report.errors))


def _sibling_conflict(scene: Scene, path: str) -> bool:
    return scene.node(path) is not None


def _validate_new_properties(
    scene: Scene,
    type_name: str | None,
    properties: dict[str, GodotValue],
    node_path: str | None,
    provider: SpecProvider,
) -> ValidationReport:
    model = provider.resolve_class(type_name) if type_name else None
    return validate_properties(
        scene=scene,
        model=model,
        properties=properties,
        has_script="script" in properties,
        node_path=node_path,
        provider=provider,
    )


def _referenced_ids(values: Iterable[GodotValue], kind: str) -> set[str]:
    """Every resource id referenced by a `kind` ('ExtResource'/'SubResource')
    call anywhere inside `values` (recursing through arrays/dicts/nested calls)."""
    found: set[str] = set()

    def walk(value: GodotValue) -> None:
        match value:
            case GCall(name=name, args=args):
                if name == kind and args and isinstance(args[0], GString):
                    found.add(args[0].value)
                for arg in args:
                    walk(arg)
            case GArray(items=items):
                for item in items:
                    walk(item)
            case GDict(entries=entries):
                for key, val in entries:
                    walk(key)
                    walk(val)
            case _:
                pass

    for value in values:
        walk(value)
    return found


def _resource_ids_in_use(scene: Scene, kind: str) -> set[str]:
    """Every resource id referenced by a `kind` call anywhere in the scene."""
    values: list[GodotValue] = []
    for node in scene.nodes:
        values.extend(node.attributes.values())
        values.extend(node.properties.values())
    for sub in scene.sub_resources:
        values.extend(sub.properties.values())
    for connection in scene.connections:
        values.extend(connection.attributes.values())
    return _referenced_ids(values, kind)


def _reachable_sub_resource_ids(scene: Scene) -> set[str]:
    """Sub-resource ids reachable from the node tree, transitively through
    sub-resources that reference other sub-resources (e.g. a SpriteFrames
    embedding several AtlasTextures). A sub-resource referenced only by
    another unreachable sub-resource is itself unreachable."""
    referenced_by: dict[str, set[str]] = {
        sub.id: _referenced_ids(sub.properties.values(), "SubResource")
        for sub in scene.sub_resources
        if sub.id is not None
    }

    roots: list[GodotValue] = []
    for node in scene.nodes:
        roots.extend(node.attributes.values())
        roots.extend(node.properties.values())
    for connection in scene.connections:
        roots.extend(connection.attributes.values())

    reachable: set[str] = set()
    stack = list(_referenced_ids(roots, "SubResource"))
    while stack:
        resource_id = stack.pop()
        if resource_id in reachable:
            continue
        reachable.add(resource_id)
        stack.extend(referenced_by.get(resource_id, ()))
    return reachable


def _node_insertion_index(scene: Scene, parent_path: str) -> int:
    """File position for a new child: right after its parent's subtree."""
    subtree = scene.subtree(parent_path)
    if not subtree:
        return len(scene.nodes)
    last = subtree[-1]
    return scene.nodes.index(last) + 1


# --- Operation application ----------------------------------------------------


def _apply_add_node(
    scene: Scene, op: AddNode, provider: SpecProvider, strict: bool
) -> OpResult:
    node_path = _scene_path(op.path)
    path = str(node_path)
    parent = None if node_path.is_root() else str(node_path.parent)
    name = node_path.name or None
    properties = {k: _to_value(v) for k, v in op.properties.items()}
    report = ValidationReport()

    if (op.type is None) == (op.instance is None):
        raise OperationError(
            "add_node needs exactly one of 'type' (a Godot class) or "
            "'instance' (an ExtResource reference to a PackedScene)"
        )
    instance_ref: GodotValue | None = None
    if op.instance is not None:
        instance_ref = parse_value(op.instance)
        if not (isinstance(instance_ref, GCall) and instance_ref.name == "ExtResource"):
            raise OperationError(
                f"add_node 'instance' must be an ExtResource(...) literal, "
                f"got {op.instance!r}"
            )
        ref_id = instance_ref.args[0].value if instance_ref.args else ""
        if scene.ext_resource(ref_id) is None:
            raise OperationError(
                f'instance ExtResource("{ref_id}") does not match any '
                "[ext_resource] in the scene"
            )

    existing = scene.node(path)
    if existing is not None:
        if existing.type != op.type:
            raise OperationError(
                f"node {path!r} already exists with type {existing.type!r}, "
                f"not {op.type!r}"
            )
        if op.instance is not None:
            current_instance = existing.attributes.get("instance")
            if current_instance is None or not values_equal(
                current_instance, instance_ref
            ):
                raise OperationError(
                    f"node {path!r} already exists with a different instance"
                )
        for key, value in properties.items():
            current = existing.properties.get(key)
            if current is None or not values_equal(current, value):
                raise OperationError(
                    f"node {path!r} already exists but property {key!r} differs; "
                    "use update_properties to change values"
                )
        return OpResult(op=op.op, changed=False, affected_paths=[path], report=report)

    if path == ".":
        raise OperationError(
            "add_node path must name the new node; '.' addresses the existing root"
        )

    if not scene.nodes:
        # First node of a brand-new scene: becomes the root, has no parent.
        if "/" in path:
            raise OperationError(
                f"cannot add {path!r} to an empty scene; add the root node first"
            )
        attributes: dict[str, GodotValue] = {"name": GString(value=name)}
    else:
        _require_node(scene, parent, role="parent")
        attributes = {"name": GString(value=name)}

    # Attribute order mirrors what the Godot editor writes:
    # name, type?, parent?, index?, groups?, instance?
    # (unique_id is never written here — see the class docstring above)
    if op.type is not None:
        attributes["type"] = GString(value=op.type)
    if scene.nodes:
        attributes["parent"] = GString(value=parent)
    if op.index is not None:
        attributes["index"] = GString(value=str(op.index))
    if op.groups:
        attributes["groups"] = GArray(items=tuple(GString(value=g) for g in op.groups))
    if instance_ref is not None:
        attributes["instance"] = instance_ref

    if op.type is not None and provider.resolve_class(op.type) is None:
        message = f"unknown class {op.type!r}"
        if "script" in properties:
            report.warning(
                message + "; assuming a script-defined class", node_path=path
            )
        else:
            report.error(message, node_path=path)
    if op.instance is None:
        report.merge(
            _validate_new_properties(scene, op.type, properties, path, provider)
        )
    _check_strict(report, strict)

    node = NodeEntry(attributes=attributes, properties=properties)
    scene.nodes.insert(_node_insertion_index(scene, parent or "."), node)
    return OpResult(op=op.op, changed=True, affected_paths=[path], report=report)


def _apply_delete_node(
    scene: Scene, op: DeleteNode, provider: SpecProvider, strict: bool
) -> OpResult:
    path = normalize_path(op.path)
    node = scene.node(path)
    if node is None:
        return OpResult(op=op.op, changed=False, affected_paths=[path])
    if path == ".":
        raise OperationError("cannot delete the scene root")

    subtree = scene.subtree(path)
    if len(subtree) > 1 and not op.recursive:
        raise OperationError(
            f"node {path!r} has children; pass recursive=true to delete the subtree"
        )
    removed_paths = {entry.path() for entry in subtree}
    removed_ids = {id(entry) for entry in subtree}

    reachable_before = _reachable_sub_resource_ids(scene)
    scene.nodes = [n for n in scene.nodes if id(n) not in removed_ids]
    scene.connections = [
        c
        for c in scene.connections
        if c.from_path not in removed_paths and c.to_path not in removed_paths
    ]

    # GC sub_resources whose *last* reference was in the deleted subtree.
    # Resources already orphaned before this op (for unrelated reasons) are
    # left untouched — this op only cleans up what it caused.
    reachable_after = _reachable_sub_resource_ids(scene)
    orphaned = reachable_before - reachable_after
    if orphaned:
        scene.sub_resources = [
            sub for sub in scene.sub_resources if sub.id not in orphaned
        ]
        _recompute_load_steps(scene)

    return OpResult(op=op.op, changed=True, affected_paths=sorted(removed_paths))


def _apply_update_properties(
    scene: Scene, op: UpdateProperties, provider: SpecProvider, strict: bool
) -> OpResult:
    path = normalize_path(op.path)
    node = _require_node(scene, path)
    properties = {k: _to_value(v) for k, v in op.properties.items()}

    model = provider.resolve_class(node.type) if node.type else None
    report = validate_properties(
        scene=scene,
        model=model,
        properties=properties,
        has_script="script" in node.properties
        or node.is_instance
        or "script" in properties,
        node_path=path,
        provider=provider,
    )
    _check_strict(report, strict)

    changed = False
    for key, value in properties.items():
        current = node.properties.get(key)
        if current is not None and values_equal(current, value):
            continue
        node.properties[key] = value
        changed = True
    for key in op.remove:
        if key in node.properties:
            del node.properties[key]
            changed = True
    return OpResult(op=op.op, changed=changed, affected_paths=[path], report=report)


def _rewrite_scene_paths(
    scene: Scene, old_path: str, new_path: str
) -> ValidationReport:
    """After a rename/move of the subtree at `old_path` to `new_path`, rewrite
    every reference: descendants' parent attributes, connection endpoints, and
    NodePath property values (resolved exactly through the tree; only paths
    that escape the scene are left alone, with a warning)."""
    report = ValidationReport()

    for node in scene.nodes:
        parent = node.parent
        if parent is not None:
            rewritten = _rewrite_tree_path(parent, old_path, new_path)
            if rewritten is not None:
                node.attributes["parent"] = GString(value=rewritten)

    for connection in scene.connections:
        for key in ("from", "to"):
            value = connection.attributes.get(key)
            if isinstance(value, GString):
                rewritten = _rewrite_tree_path(value.value, old_path, new_path)
                if rewritten is not None:
                    connection.attributes[key] = GString(value=rewritten)

    def rewrite_value(value: GodotValue, owner_old: str, owner_new: str) -> GodotValue:
        match value:
            case GNodePath():
                target = ScenePath(owner_old).resolve_node_path(value.value)
                if target is None:
                    report.warning(
                        f"NodePath {value.value!r} escapes the scene and cannot "
                        "be checked against this rename/move; left unchanged",
                        node_path=owner_new,
                    )
                    return value
                new_target = target.rebase(old_path, new_path) or target
                rewritten = ScenePath(owner_new).node_path_to(new_target)
                if rewritten == value.value:
                    return value
                return GNodePath(value=rewritten)
            case GCall():
                return value.model_copy(
                    update={
                        "args": tuple(
                            rewrite_value(a, owner_old, owner_new) for a in value.args
                        )
                    }
                )
            case GArray():
                return value.model_copy(
                    update={
                        "items": tuple(
                            rewrite_value(i, owner_old, owner_new) for i in value.items
                        )
                    }
                )
            case GDict():
                return value.model_copy(
                    update={
                        "entries": tuple(
                            (
                                rewrite_value(k, owner_old, owner_new),
                                rewrite_value(v, owner_old, owner_new),
                            )
                            for k, v in value.entries
                        )
                    }
                )
            case _:
                return value

    for node in scene.nodes:
        owner_new = node.path()
        owner_old = owner_new
        undone = _rewrite_tree_path(owner_new, new_path, old_path)
        if undone is not None:
            owner_old = undone
        node.properties = {
            key: rewrite_value(value, owner_old, owner_new)
            for key, value in node.properties.items()
        }
    return report


def _apply_rename_node(
    scene: Scene, op: RenameNode, provider: SpecProvider, strict: bool
) -> OpResult:
    node_path = _scene_path(op.path)
    path = str(node_path)
    node = scene.node(path)
    if node is None:
        # Desired-state reading: if the source is gone but the destination
        # exists, a previous application already did this rename.
        target = str(node_path.parent / op.new_name)
        if not node_path.is_root() and scene.node(target) is not None:
            return OpResult(op=op.op, changed=False, affected_paths=[target])
        raise OperationError(f"node {path!r} does not exist")
    if node.name == op.new_name:
        return OpResult(op=op.op, changed=False, affected_paths=[path])

    if node_path.is_root():
        node.attributes["name"] = GString(value=op.new_name)
        return OpResult(op=op.op, changed=True, affected_paths=[path])

    new_path = str(node_path.parent / op.new_name)
    if _sibling_conflict(scene, new_path):
        raise OperationError(f"cannot rename {path!r}: {new_path!r} already exists")

    node.attributes["name"] = GString(value=op.new_name)
    report = _rewrite_scene_paths(scene, path, new_path)
    return OpResult(
        op=op.op, changed=True, affected_paths=[path, new_path], report=report
    )


def _apply_move_node(
    scene: Scene, op: MoveNode, provider: SpecProvider, strict: bool
) -> OpResult:
    node_path = _scene_path(op.path)
    parent_path = _scene_path(op.new_parent)
    path = str(node_path)
    new_parent = str(parent_path)
    node = scene.node(path)
    if node is None:
        # Desired-state reading: source gone, but a same-named node already
        # sits under the destination parent -> already moved.
        target = str(parent_path / node_path.name) if node_path.name else ""
        if target and scene.node(target) is not None:
            return OpResult(op=op.op, changed=False, affected_paths=[target])
        raise OperationError(f"node {path!r} does not exist")
    if node_path.is_root():
        raise OperationError("cannot move the scene root")
    _require_node(scene, new_parent, role="new parent")

    if parent_path.is_within(node_path):
        raise OperationError(
            f"cannot move {path!r} under its own subtree {new_parent!r}"
        )

    if node.parent == new_parent:
        if op.index is None:
            return OpResult(op=op.op, changed=False, affected_paths=[path])
        current_index = node.attributes.get("index")
        if isinstance(current_index, GString) and current_index.value == str(op.index):
            return OpResult(op=op.op, changed=False, affected_paths=[path])

    new_path = str(parent_path / node.name)
    if new_path != path and _sibling_conflict(scene, new_path):
        raise OperationError(f"cannot move {path!r}: {new_path!r} already exists")

    subtree = scene.subtree(path)
    moving_ids = {id(entry) for entry in subtree}
    scene.nodes = [n for n in scene.nodes if id(n) not in moving_ids]
    node.attributes["parent"] = GString(value=new_parent)
    if op.index is not None:
        node.attributes["index"] = GString(value=str(op.index))
    insert_at = _node_insertion_index(scene, new_parent)
    scene.nodes[insert_at:insert_at] = subtree

    report = _rewrite_scene_paths(scene, path, new_path)
    return OpResult(
        op=op.op, changed=True, affected_paths=[path, new_path], report=report
    )


def _ext_resource_attributes(
    op: AddExtResource, resource_id: str
) -> dict[str, GodotValue]:
    # No uid= attribute: uids are Godot's to assign (from the asset's .uid /
    # .import metadata); the editor fills it in on the next save.
    return {
        "type": GString(value=op.type),
        "path": GString(value=op.path),
        "id": GString(value=resource_id),
    }


def _apply_add_ext_resource(
    scene: Scene, op: AddExtResource, provider: SpecProvider, strict: bool
) -> OpResult:
    for entry in scene.ext_resources:
        if entry.type == op.type and entry.path == op.path:
            if op.id is not None and entry.id != op.id:
                raise OperationError(
                    f"ext_resource for {op.path!r} already exists with id "
                    f"{entry.id!r}, not {op.id!r}"
                )
            return OpResult(
                op=op.op,
                changed=False,
                allocated_ids={"id": entry.id or ""},
            )

    if op.id is not None:
        if scene.ext_resource(op.id) is not None:
            raise OperationError(
                f"ext_resource id {op.id!r} is already taken by a different resource"
            )
        resource_id = op.id
    else:
        taken = {e.id for e in scene.ext_resources}
        ordinal = len(scene.ext_resources) + 1
        resource_id = f"{ordinal}_{_hash_suffix(op.type, op.path)}"
        while resource_id in taken:
            ordinal += 1
            resource_id = f"{ordinal}_{_hash_suffix(op.type, op.path)}"

    scene.ext_resources.append(
        ExtResourceEntry(attributes=_ext_resource_attributes(op, resource_id))
    )
    _recompute_load_steps(scene)
    return OpResult(op=op.op, changed=True, allocated_ids={"id": resource_id})


def _apply_create_sub_resource(
    scene: Scene, op: CreateSubResource, provider: SpecProvider, strict: bool
) -> OpResult:
    properties = {k: _to_value(v) for k, v in op.properties.items()}

    def same_content(entry: SubResourceEntry) -> bool:
        if entry.type != op.type or set(entry.properties) != set(properties):
            return False
        return all(values_equal(entry.properties[k], v) for k, v in properties.items())

    for entry in scene.sub_resources:
        if op.id is not None:
            if entry.id != op.id:
                continue
            if not same_content(entry):
                raise OperationError(
                    f"sub_resource id {op.id!r} already exists with different content"
                )
            return OpResult(op=op.op, changed=False, allocated_ids={"id": op.id})
        if same_content(entry):
            return OpResult(
                op=op.op, changed=False, allocated_ids={"id": entry.id or ""}
            )

    report = ValidationReport()
    model = provider.resolve_class(op.type)
    if model is None:
        report.error(f"unknown resource class {op.type!r}")
    elif provider.is_subclass(op.type, "Resource") is False:
        report.error(f"{op.type} is not a Resource subclass")
    report.merge(
        _validate_new_properties(
            scene, op.type, properties, f"sub_resource:{op.id or op.type}", provider
        )
    )
    _check_strict(report, strict)

    if op.id is not None:
        resource_id = op.id
    else:
        content_key = "\x00".join(
            f"{k}={format_value(v, canonical=True)}"
            for k, v in sorted(properties.items())
        )
        taken = {e.id for e in scene.sub_resources}
        resource_id = f"{op.type}_{_hash_suffix(op.type, content_key)}"
        bump = 0
        while resource_id in taken:
            bump += 1
            resource_id = f"{op.type}_{_hash_suffix(op.type, content_key, str(bump))}"

    scene.sub_resources.append(
        SubResourceEntry(
            attributes={
                "type": GString(value=op.type),
                "id": GString(value=resource_id),
            },
            properties=properties,
        )
    )
    _recompute_load_steps(scene)
    return OpResult(
        op=op.op, changed=True, allocated_ids={"id": resource_id}, report=report
    )


def _apply_attach_script(
    scene: Scene, op: AttachScript, provider: SpecProvider, strict: bool
) -> OpResult:
    path = normalize_path(op.path)
    node = _require_node(scene, path)

    ext_op = AddExtResource(type="Script", path=op.script_path)
    ext_result = _apply_add_ext_resource(scene, ext_op, provider, strict)
    resource_id = ext_result.allocated_ids["id"]
    reference = ext_resource_ref(resource_id)

    current = node.properties.get("script")
    if current is not None and values_equal(current, reference):
        return OpResult(
            op=op.op,
            changed=ext_result.changed,
            affected_paths=[path],
            allocated_ids=ext_result.allocated_ids,
        )
    node.properties["script"] = reference
    return OpResult(
        op=op.op,
        changed=True,
        affected_paths=[path],
        allocated_ids=ext_result.allocated_ids,
    )


def _apply_detach_script(
    scene: Scene, op: DetachScript, provider: SpecProvider, strict: bool
) -> OpResult:
    path = normalize_path(op.path)
    node = _require_node(scene, path)
    current = node.properties.get("script")
    if current is None:
        return OpResult(op=op.op, changed=False, affected_paths=[path])

    del node.properties["script"]
    if isinstance(current, GCall) and current.name == "ExtResource":
        ref_id = current.args[0].value if current.args else None
        if ref_id is not None and ref_id not in _resource_ids_in_use(
            scene, "ExtResource"
        ):
            scene.ext_resources = [e for e in scene.ext_resources if e.id != ref_id]
            _recompute_load_steps(scene)
    return OpResult(op=op.op, changed=True, affected_paths=[path])


def _connection_key(attributes: dict[str, GodotValue]) -> tuple:
    def get(key: str) -> str | None:
        value = attributes.get(key)
        return value.value if isinstance(value, GString) else None

    return (get("signal"), get("from"), get("to"), get("method"))


def _apply_connect_signal(
    scene: Scene, op: ConnectSignal, provider: SpecProvider, strict: bool
) -> OpResult:
    from_path = normalize_path(op.from_)
    to_path = normalize_path(op.to)
    _require_node(scene, from_path, role="connection source")
    _require_node(scene, to_path, role="connection target")

    report = validate_connection_signal(scene, from_path, op.signal, provider)
    _check_strict(report, strict)

    key = (op.signal, from_path, to_path, op.method)
    for connection in scene.connections:
        if _connection_key(connection.attributes) == key:
            return OpResult(
                op=op.op, changed=False, affected_paths=[from_path], report=report
            )

    attributes: dict[str, GodotValue] = {
        "signal": GString(value=op.signal),
        "from": GString(value=from_path),
        "to": GString(value=to_path),
        "method": GString(value=op.method),
    }
    if op.flags is not None:
        attributes["flags"] = GInt(value=op.flags)
    if op.binds is not None:
        attributes["binds"] = parse_value(op.binds)
    scene.connections.append(ConnectionEntry(attributes=attributes))
    return OpResult(op=op.op, changed=True, affected_paths=[from_path], report=report)


def _apply_disconnect_signal(
    scene: Scene, op: DisconnectSignal, provider: SpecProvider, strict: bool
) -> OpResult:
    key = (
        op.signal,
        normalize_path(op.from_),
        normalize_path(op.to),
        op.method,
    )
    kept = [c for c in scene.connections if _connection_key(c.attributes) != key]
    changed = len(kept) != len(scene.connections)
    scene.connections = kept
    return OpResult(op=op.op, changed=changed, affected_paths=[key[1]])


_APPLIERS = {
    "add_node": _apply_add_node,
    "delete_node": _apply_delete_node,
    "update_properties": _apply_update_properties,
    "rename_node": _apply_rename_node,
    "move_node": _apply_move_node,
    "attach_script": _apply_attach_script,
    "detach_script": _apply_detach_script,
    "add_ext_resource": _apply_add_ext_resource,
    "create_sub_resource": _apply_create_sub_resource,
    "connect_signal": _apply_connect_signal,
    "disconnect_signal": _apply_disconnect_signal,
}


def apply_operation(
    scene: Scene,
    operation: Operation,
    *,
    provider: SpecProvider | None = None,
    strict: bool = True,
) -> OpResult:
    """Apply one operation, mutating `scene` in place."""
    provider = provider or default_provider()
    try:
        return _APPLIERS[operation.op](scene, operation, provider, strict)
    except ValueError as exc:
        # e.g. a malformed scene path ('..' segments) or a bad literal
        raise OperationError(str(exc)) from exc


def apply_operations(
    scene: Scene,
    operations: list[Operation],
    *,
    provider: SpecProvider | None = None,
    strict: bool = True,
) -> ApplyResult:
    """Apply operations in order, all-or-nothing.

    Works on a deep copy: the input scene is never mutated, and a failing
    operation raises OperationError (tagged with its position) without any
    partial result escaping.
    """
    provider = provider or default_provider()
    working = scene.model_copy(deep=True)
    results: list[OpResult] = []
    for position, operation in enumerate(operations, start=1):
        try:
            results.append(
                apply_operation(working, operation, provider=provider, strict=strict)
            )
        except OperationError as exc:
            raise OperationError(
                f"operation {position} ({operation.op}): {exc}"
            ) from exc
    return ApplyResult(scene=working, results=results)
