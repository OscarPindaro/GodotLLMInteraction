"""Serializer for the .tscn text format.

Spacing is canonical and position-independent, matching what the Godot
editor writes: the header, each sub_resource block, and each node block are
separated by exactly one blank line; consecutive [ext_resource ...] lines
form one block, as do consecutive [connection ...] lines; the file ends with
a single newline. Because insertion/removal of a block cannot disturb its
neighbours' spacing, editing operations compose without whitespace drift.
"""

from __future__ import annotations

from godotllminteraction.tscn.scene import Scene
from godotllminteraction.tscn.values import GodotValue, format_value


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


def dump_scene(scene: Scene) -> str:
    blocks = [_format_section_line("gd_scene", scene.header.attributes)]
    if scene.ext_resources:
        blocks.append(
            "\n".join(
                _format_section_line("ext_resource", entry.attributes)
                for entry in scene.ext_resources
            )
        )
    for sub in scene.sub_resources:
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
