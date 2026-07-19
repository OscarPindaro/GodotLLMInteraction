"""Serializer for the .tscn text format.

Spacing is canonical and position-independent, matching what the Godot
editor writes: the header, each sub_resource block, and each node block are
separated by exactly one blank line; consecutive [ext_resource ...] lines
form one block, as do consecutive [connection ...] lines; the file ends with
a single newline. Because insertion/removal of a block cannot disturb its
neighbours' spacing, editing operations compose without whitespace drift.

Sub_resources are topologically sorted so that any SubResource("id")
reference resolves — Godot's parser is sequential and errors if a referenced
sub_resource hasn't appeared yet. The sort is stable: sub_resources with no
dependency relationship keep their original relative order.
"""

from __future__ import annotations

from godotllminteraction.tscn.scene import Scene, SubResourceEntry
from godotllminteraction.tscn.values import (
    GArray,
    GCall,
    GDict,
    GString,
    GodotValue,
    format_value,
)


def _format_section_line(name: str, attributes: dict[str, GodotValue]) -> str:
    parts = [name] + [f"{k}={format_value(v)}" for k, v in attributes.items()]
    return f"[{' '.join(parts)}]"


def _format_block(
    name: str,
    attributes: dict[str, GodotValue],
    properties: dict[str, GodotValue],
) -> str:
    lines = [_format_section_line(name, attributes)]
    lines.extend(f"{key} = {format_value(value)}" for key, value in properties.items())
    return "\n".join(lines)


def _collect_sub_resource_ids(value: GodotValue, out: set[str]) -> None:
    """Recursively collect all SubResource("id") references from a value."""
    match value:
        case GCall(name="SubResource", args=(GString(value=s),)):
            out.add(s)
        case GCall(args=args):
            for arg in args:
                _collect_sub_resource_ids(arg, out)
        case GArray(items=items):
            for item in items:
                _collect_sub_resource_ids(item, out)
        case GDict(entries=entries):
            for key, val in entries:
                _collect_sub_resource_ids(key, out)
                _collect_sub_resource_ids(val, out)


def _sub_resource_deps(sub: SubResourceEntry) -> set[str]:
    """IDs of SubResources referenced in this sub_resource's properties."""
    deps: set[str] = set()
    for value in sub.properties.values():
        _collect_sub_resource_ids(value, deps)
    return deps


def _topological_sort(subs: list[SubResourceEntry]) -> list[SubResourceEntry]:
    """Stable topological sort: referenced sub_resources come first.

    Sub_resources with no dependency relationship preserve their original
    relative order. Cycles (which shouldn't happen in valid Godot scenes)
    are broken by original order, so the sort always terminates.
    """
    id_to_index = {sub.id: i for i, sub in enumerate(subs) if sub.id is not None}
    id_to_sub = {sub.id: sub for sub in subs if sub.id is not None}

    visited: set[str] = set()
    result: list[SubResourceEntry] = []

    def visit(sub_id: str) -> None:
        if sub_id in visited or sub_id not in id_to_sub:
            return
        visited.add(sub_id)
        for dep_id in sorted(
            _sub_resource_deps(id_to_sub[sub_id]),
            key=lambda d: id_to_index.get(d, -1),
        ):
            visit(dep_id)
        result.append(id_to_sub[sub_id])

    for sub in subs:
        if sub.id is not None:
            visit(sub.id)

    # Append any sub_resources without an id (shouldn't normally happen).
    for sub in subs:
        if sub.id is None:
            result.append(sub)
    return result


def dump_scene(scene: Scene) -> str:
    blocks = [_format_section_line("gd_scene", scene.header.attributes)]
    if scene.ext_resources:
        blocks.append(
            "\n".join(
                _format_section_line("ext_resource", entry.attributes)
                for entry in scene.ext_resources
            )
        )
    for sub in _topological_sort(scene.sub_resources):
        blocks.append(_format_block("sub_resource", sub.attributes, sub.properties))
    for node in scene.nodes:
        blocks.append(_format_block("node", node.attributes, node.properties))
    if scene.connections:
        blocks.append(
            "\n".join(
                _format_section_line("connection", entry.attributes)
                for entry in scene.connections
            )
        )
    for other in scene.others:
        blocks.append(_format_block(other.name, other.attributes, other.properties))
    return "\n\n".join(blocks) + "\n"
