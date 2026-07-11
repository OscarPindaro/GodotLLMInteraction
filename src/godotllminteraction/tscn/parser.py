"""Parser for the .tscn text format.

Token-level scanning is shared with the value grammar: section attribute
values and property values are read in place by `values.ValueReader`, so a
property value may span multiple lines (dicts, arrays of dicts) without any
special handling here.
"""

from __future__ import annotations

import re

from godotllminteraction.tscn.exceptions import ParseError
from godotllminteraction.tscn.scene import (
    ConnectionEntry,
    ExtResourceEntry,
    GenericSection,
    NodeEntry,
    Scene,
    SceneHeader,
    SubResourceEntry,
)
from godotllminteraction.tscn.values import GodotValue, ValueReader

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Property keys are written unquoted and may contain slashes and dots
# (e.g. metadata/_edit_group_, tracks/0/path); anything up to whitespace/'='.
_PROPERTY_KEY_RE = re.compile(r"[^\s=\[\]]+")
_HSPACE_RE = re.compile(r"[ \t]*")


def parse_scene(text: str) -> Scene:
    """Parse the full text of a .tscn file into a Scene."""
    reader = ValueReader(text)
    reader.skip_ws()

    scene = Scene()
    saw_header = False
    while not reader.at_end():
        name, attributes = _read_section_header(reader)
        properties = _read_properties(reader)

        if not saw_header:
            if name != "gd_scene":
                raise reader.error(
                    f"expected [gd_scene ...] as the first section, found [{name} ...]"
                )
            if properties:
                raise reader.error("[gd_scene ...] cannot have property lines")
            scene.header = SceneHeader(attributes=attributes)
            saw_header = True
            continue

        match name:
            case "gd_scene":
                raise reader.error("duplicate [gd_scene ...] section")
            case "ext_resource":
                if properties:
                    raise reader.error("[ext_resource ...] cannot have property lines")
                scene.ext_resources.append(ExtResourceEntry(attributes=attributes))
            case "sub_resource":
                scene.sub_resources.append(
                    SubResourceEntry(attributes=attributes, properties=properties)
                )
            case "node":
                scene.nodes.append(
                    NodeEntry(attributes=attributes, properties=properties)
                )
            case "connection":
                if properties:
                    raise reader.error("[connection ...] cannot have property lines")
                scene.connections.append(ConnectionEntry(attributes=attributes))
            case _:
                scene.others.append(
                    GenericSection(
                        name=name, attributes=attributes, properties=properties
                    )
                )
        reader.skip_ws()

    if not saw_header:
        raise ParseError("empty file: no [gd_scene ...] section found")
    return scene


def _read_section_header(
    reader: ValueReader,
) -> tuple[str, dict[str, GodotValue]]:
    reader.skip_ws()
    reader.expect("[")
    match = _IDENT_RE.match(reader.text, reader.pos)
    if match is None:
        raise reader.error("expected a section name after '['")
    name = match.group()
    reader.pos = match.end()

    attributes: dict[str, GodotValue] = {}
    while True:
        reader.pos = _HSPACE_RE.match(reader.text, reader.pos).end()
        if reader.peek() == "]":
            reader.pos += 1
            return name, attributes
        key_match = _IDENT_RE.match(reader.text, reader.pos)
        if key_match is None:
            raise reader.error(
                f"expected an attribute name or ']' in [{name} ...], "
                f"found {reader.peek()!r}"
            )
        key = key_match.group()
        reader.pos = key_match.end()
        reader.expect("=")
        if key in attributes:
            raise reader.error(f"duplicate attribute {key!r} in [{name} ...]")
        attributes[key] = reader.read_value()


def _read_properties(reader: ValueReader) -> dict[str, GodotValue]:
    properties: dict[str, GodotValue] = {}
    while True:
        reader.skip_ws()
        if reader.at_end() or reader.peek() == "[":
            return properties
        key_match = _PROPERTY_KEY_RE.match(reader.text, reader.pos)
        if key_match is None:
            raise reader.error(
                f"expected a property line or a section, found {reader.peek()!r}"
            )
        key = key_match.group()
        reader.pos = key_match.end()
        reader.pos = _HSPACE_RE.match(reader.text, reader.pos).end()
        reader.expect("=")
        if key in properties:
            raise reader.error(f"duplicate property {key!r}")
        properties[key] = reader.read_value()
