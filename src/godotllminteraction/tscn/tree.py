"""Scene-tree views at three levels of detail.

`build_tree` produces a serializable structure (for --json output and
programmatic use); `render_tree` turns it into indented plain-text lines.
Rich styling, if any, belongs to the CLI layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from godotllminteraction.tscn.scene import NodeEntry, Scene
from godotllminteraction.tscn.values import (
    GArray,
    GCall,
    GDict,
    GString,
    GodotValue,
    format_value,
)

TreeDetail = Literal["nodes", "resources", "properties"]


class ResourceRef(BaseModel):
    """A node property that references an ext/sub resource."""

    property: str
    kind: Literal["ext_resource", "sub_resource"]
    id: str
    type: str | None = None
    path: str | None = None  # res:// path, for ext resources


class TreeNode(BaseModel):
    name: str
    path: str
    type: str | None = None
    instance: bool = False
    resources: list[ResourceRef] = []
    properties: dict[str, str] = {}
    children: list[TreeNode] = []


def _resource_refs(scene: Scene, node: NodeEntry) -> list[ResourceRef]:
    refs: list[ResourceRef] = []

    def collect(property_name: str, value: GodotValue) -> None:
        match value:
            case GCall(name="ExtResource", args=args) if args and isinstance(
                args[0], GString
            ):
                entry = scene.ext_resource(args[0].value)
                refs.append(
                    ResourceRef(
                        property=property_name,
                        kind="ext_resource",
                        id=args[0].value,
                        type=entry.type if entry else None,
                        path=entry.path if entry else None,
                    )
                )
            case GCall(name="SubResource", args=args) if args and isinstance(
                args[0], GString
            ):
                entry = scene.sub_resource(args[0].value)
                refs.append(
                    ResourceRef(
                        property=property_name,
                        kind="sub_resource",
                        id=args[0].value,
                        type=entry.type if entry else None,
                    )
                )
            case GCall(args=args):
                for arg in args:
                    collect(property_name, arg)
            case GArray(items=items):
                for item in items:
                    collect(property_name, item)
            case GDict(entries=entries):
                for key, val in entries:
                    collect(property_name, key)
                    collect(property_name, val)
            case _:
                pass

    for key, value in node.properties.items():
        collect(key, value)
    instance = node.attributes.get("instance")
    if instance is not None:
        collect("instance", instance)
    return refs


def build_tree(scene: Scene, detail: TreeDetail = "nodes") -> TreeNode | None:
    root_entry = scene.root()
    if root_entry is None:
        return None

    def build(entry: NodeEntry) -> TreeNode:
        node = TreeNode(
            name=entry.name,
            path=entry.path(),
            type=entry.type,
            instance=entry.is_instance,
        )
        if detail in ("resources", "properties"):
            node.resources = _resource_refs(scene, entry)
        if detail == "properties":
            node.properties = {
                key: format_value(value) for key, value in entry.properties.items()
            }
        node.children = [build(child) for child in scene.children(entry.path())]
        return node

    return build(root_entry)


def render_tree(tree: TreeNode) -> str:
    lines: list[str] = []

    def label(node: TreeNode) -> str:
        if node.instance:
            return f"{node.name} (instance)"
        return f"{node.name} ({node.type})" if node.type else node.name

    def describe(ref: ResourceRef) -> str:
        target = ref.path if ref.path else ref.id
        type_name = ref.type or "?"
        return f"{ref.property} -> {type_name} {target}"

    def walk(node: TreeNode, prefix: str, is_last: bool, is_root: bool) -> None:
        if is_root:
            lines.append(label(node))
            child_prefix = ""
        else:
            connector = "└─ " if is_last else "├─ "
            lines.append(f"{prefix}{connector}{label(node)}")
            child_prefix = prefix + ("   " if is_last else "│  ")

        detail_lines = [describe(ref) for ref in node.resources]
        detail_lines.extend(
            f"{key} = {value}"
            for key, value in node.properties.items()
            if key not in {ref.property for ref in node.resources}
        )
        gutter = child_prefix + ("│  " if node.children else "   ")
        for detail_line in detail_lines:
            first_line = detail_line.splitlines()[0]
            lines.append(f"{gutter}. {first_line}")

        for i, child in enumerate(node.children):
            walk(child, child_prefix, i == len(node.children) - 1, False)

    walk(tree, "", True, True)
    return "\n".join(lines)
