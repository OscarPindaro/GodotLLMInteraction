"""Declarative scene creation: tree/JSON → ``.tscn`` in one call.

This module is a *compiler* over the existing operation system.  It parses a
human-readable tree or a JSON structure into an intermediate ``NodeSpec``
tree, resolves ``class_name`` types via :class:`ClassResolver`, and emits a
list of ``AddNode`` / ``AttachScript`` operations that are applied through the
existing idempotent :func:`apply_operations`.

No atlas/sprite handling — resources are added with dedicated commands after
the scene exists.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from godotllminteraction.tscn.class_cache import ClassResolver
from godotllminteraction.tscn.exceptions import TscnError
from godotllminteraction.tscn.operations import (
    AddNode,
    AttachScript,
    Operation,
    PropertyInput,
    UpdateProperties,
    apply_operations,
)
from godotllminteraction.tscn.scene import Scene
from godotllminteraction.tscn.specs import SpecProvider, default_provider
from godotllminteraction.tscn.writer import dump_scene
from godotllminteraction.tscn.yaml_ops import CreateSpec, OpsFile, initial_scene


# --------------------------------------------------------------------------- model


class NodeSpec(BaseModel):
    """Intermediate representation of a node in the declarative tree."""

    name: str
    type: str | None = None
    script: str | None = None
    properties: dict[str, PropertyInput] = Field(default_factory=dict)
    children: list["NodeSpec"] = Field(default_factory=list)
    unique: bool = False


# ----------------------------------------------------------- tree-format parser

# Prefix characters that introduce a tree line: box-drawing + ASCII.
_PREFIX_CHARS = set("│├└─|-_` ")


def _prefix_length(line: str) -> int:
    """Count leading tree-prefix characters (box-drawing or ASCII)."""
    count = 0
    for ch in line:
        if ch in _PREFIX_CHARS:
            count += 1
        else:
            break
    return count


def _strip_prefix(line: str) -> str:
    return line[_prefix_length(line) :].strip()


# Name (Type) [key: value, ...]
_NODE_RE = re.compile(
    r"^(?P<name>[^\s\[\](]+)"
    r"(?:\s*\((?P<type>[^)]*)\))?"
    r"(?:\s*\[(?P<props>.*)\])?"
    r"\s*$"
)


def _split_props(text: str) -> list[str]:
    """Split property list on top-level commas (ignoring commas inside parens/brackets)."""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "([{":
            depth += 1
            current.append(ch)
        elif ch in ")]}":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        items.append("".join(current))
    return items


def _parse_props(text: str) -> tuple[dict[str, PropertyInput], bool]:
    """Parse the ``[key: value, ...]`` bracket content.

    Returns ``(properties, unique_flag)``.  The literal ``unique`` keyword
    (no colon) sets the flag.
    """
    properties: dict[str, PropertyInput] = {}
    unique = False
    for raw in _split_props(text):
        item = raw.strip()
        if not item:
            continue
        if item == "unique":
            unique = True
            continue
        key, sep, value = item.partition(":")
        if not sep:
            raise TscnError(f"Invalid property {item!r}; expected 'key: value'.")
        properties[key.strip()] = value.strip()
    return properties, unique


def parse_tree(text: str) -> NodeSpec:
    """Parse a human-readable tree description into a ``NodeSpec``.

    Accepts box-drawing (``├──``, ``└──``, ``│``) and ASCII (``|--``,
    ```--``, ``|``, ``-``, ``_``) prefixes interchangeably.

    A line that starts with ``[`` (after stripping prefix) is treated as a
    continuation of the previous node's property list.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise TscnError("Empty tree: at least a root node is required.")

    root = _parse_node_line(_strip_prefix(lines[0]))
    # (depth, parent_spec) stack
    stack: list[tuple[int, NodeSpec]] = [(0, root)]
    for line in lines[1:]:
        content = _strip_prefix(line)
        # Continuation line: starts with '[' → append props to last node.
        if content.startswith("["):
            last = stack[-1][1]
            extra_props, extra_unique = _parse_props(content[1:].rstrip("]"))
            last.properties.update(extra_props)
            if extra_unique:
                last.unique = True
            continue

        depth = _prefix_length(line)
        spec = _parse_node_line(content)
        # Pop until we find a parent at shallower depth.
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            raise TscnError(f"Node {spec.name!r} at depth {depth} has no parent.")
        stack[-1][1].children.append(spec)
        stack.append((depth, spec))
    return root


def _parse_node_line(content: str) -> NodeSpec:
    match = _NODE_RE.match(content)
    if match is None:
        raise TscnError(f"Cannot parse node line: {content!r}")
    name = match.group("name")
    type_ = match.group("type") or None
    props_text = match.group("props") or ""
    properties, unique = _parse_props(props_text)
    return NodeSpec(
        name=name,
        type=type_,
        properties=properties,
        unique=unique,
    )


# ----------------------------------------------------------- JSON-format parser


def parse_json(data: dict) -> NodeSpec:
    """Parse a JSON dict (or dict-like) into a ``NodeSpec`` tree."""
    if "root" in data:
        return _node_from_json(data["root"])
    return _node_from_json(data)


def _node_from_json(d: dict) -> NodeSpec:
    children = [_node_from_json(c) for c in d.get("children", [])]
    return NodeSpec(
        name=d["name"],
        type=d.get("type"),
        script=d.get("script"),
        properties=d.get("properties", {}),
        children=children,
        unique=d.get("unique", False),
    )


# --------------------------------------------------------------- scene builder


class SceneBuilderError(TscnError):
    """Raised when the declarative spec cannot be compiled to a scene."""


def _resolve_type(
    spec: NodeSpec,
    resolver: ClassResolver | None,
    provider: SpecProvider,
) -> tuple[str, str | None]:
    """Return ``(godot_class, script_path)`` for a node spec.

    ``script_path`` is the res:// path to attach, or ``None`` if no script.
    """
    if spec.type is None:
        if spec.script is None:
            raise SceneBuilderError(f"Node {spec.name!r} has no type and no script.")
        # Type-less node with explicit script: use Node as the base.
        return "Node", spec.script

    # Built-in Godot class?
    if provider.resolve_class(spec.type) is not None:
        return spec.type, spec.script

    # User-defined class_name?
    if resolver is not None:
        info = resolver.resolve(spec.type)
        if info is not None:
            script = spec.script or info.script_path
            return info.base_type, script

    raise SceneBuilderError(
        f"Node {spec.name!r}: unknown type {spec.type!r} "
        "(not a built-in class and not found in project class cache)."
    )


def _compile(
    spec: NodeSpec,
    parent_path: str,
    resolver: ClassResolver | None,
    provider: SpecProvider,
    ops: list[Operation],
) -> None:
    """DFS pre-order: emit ops for *spec* then recurse into children."""
    if parent_path == ".":
        path = spec.name
    else:
        path = f"{parent_path}/{spec.name}"

    godot_class, script_path = _resolve_type(spec, resolver, provider)

    properties: dict[str, PropertyInput] = dict(spec.properties)
    if spec.unique:
        properties["unique_name_in_owner"] = "true"

    ops.append(AddNode(path=path, type=godot_class, properties=properties))
    if script_path is not None:
        ops.append(AttachScript(path=path, script_path=script_path))

    for child in spec.children:
        _compile(child, path, resolver, provider, ops)


def build_scene(
    spec: NodeSpec,
    *,
    class_resolver: ClassResolver | None = None,
    provider: SpecProvider | None = None,
    strict: bool = True,
) -> Scene:
    """Compile a ``NodeSpec`` tree into a complete ``Scene``."""
    provider = provider or default_provider()
    root_class, root_script = _resolve_type(spec, class_resolver, provider)

    ops_file = OpsFile(
        create=CreateSpec(root_name=spec.name, root_type=root_class),
    )
    scene = initial_scene(ops_file)

    ops: list[Operation] = []
    # Root node already exists via initial_scene; only attach script if needed.
    if root_script is not None:
        ops.append(AttachScript(path=".", script_path=root_script))

    # Root properties (including unique) need an UpdateProperties if present.
    root_props: dict[str, PropertyInput] = dict(spec.properties)
    if spec.unique:
        root_props["unique_name_in_owner"] = "true"
    if root_props:
        ops.append(UpdateProperties(path=".", properties=root_props))

    for child in spec.children:
        _compile(child, ".", class_resolver, provider, ops)

    if ops:
        result = apply_operations(scene, ops, provider=provider, strict=strict)
        return result.scene
    return scene


def create_scene(
    spec: NodeSpec,
    output_path: Path,
    *,
    class_resolver: ClassResolver | None = None,
    provider: SpecProvider | None = None,
    strict: bool = True,
) -> Scene:
    """Build a scene from *spec* and write it to *output_path*."""
    scene = build_scene(
        spec, class_resolver=class_resolver, provider=provider, strict=strict
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(dump_scene(scene))
    return scene


# --------------------------------------------------------- project path helper


def find_project_path(start: Path) -> Path | None:
    """Walk up from *start* looking for a directory containing ``project.godot``."""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    while True:
        if (p / "project.godot").is_file():
            return p
        if p.parent == p:
            return None
        p = p.parent
