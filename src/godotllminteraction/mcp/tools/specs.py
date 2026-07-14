"""MCP tools for querying Godot API specifications."""

from __future__ import annotations

import importlib
import json
import re
from typing import Annotated, Any, get_args, get_origin

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from godotllminteraction.mcp.context import McpContext
from godotllminteraction.tscn.specs import SpecProvider, default_provider

_VERSION_RE = re.compile(r"^v(\d+)_(\d+)_(\d+)$")


def _error_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def _provider_for_version(version: str | None) -> SpecProvider:
    if version is None:
        return default_provider()
    normalized = version.lstrip("v")
    parts = normalized.split(".")
    if len(parts) == 2:
        parts.append("0")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version!r}")
    suffix = f"v{parts[0]}_{parts[1]}_{parts[2]}"
    try:
        classes = importlib.import_module(
            f"godotllminteraction.specifications.{suffix}.classes"
        )
        builtins = importlib.import_module(
            f"godotllminteraction.specifications.{suffix}.builtin_classes"
        )
        signals = importlib.import_module(
            f"godotllminteraction.specifications.{suffix}.signals"
        )
    except ImportError as exc:
        raise ValueError(
            f"Specification for version {version!r} not found: {exc}"
        ) from exc
    return SpecProvider(classes, builtins, signals.SIGNALS)


def _annotation_to_godot_type(provider: SpecProvider, annotation: object) -> str:
    """Convert a pydantic field annotation to a Godot type name string."""
    if annotation is None:
        return "Variant"
    if annotation is Any:
        return "Variant"
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is str:
        return "String"

    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        inner = _annotation_to_godot_type(provider, args[0]) if args else "Variant"
        return f"Array[{inner}]"

    godot_name = provider.godot_name_of_annotation(annotation)
    if godot_name is not None:
        return godot_name
    return "Variant"


def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def get_godot_spec(
        class_name: Annotated[
            str, Field(description="Godot class name, e.g. 'Sprite2D'.")
        ],
        version: Annotated[
            str | None,
            Field(description="Godot version, e.g. '4.7.0'; defaults to set version."),
        ] = None,
    ) -> str:
        """Query a Godot class's properties, signals, and inheritance for a given version."""
        ver = version or ctx.godot_version
        try:
            provider = _provider_for_version(ver)
        except ValueError as exc:
            return _error_json(str(exc))
        model = provider.resolve_class(class_name)
        if model is None:
            return _error_json(f"Unknown class: {class_name}")
        properties: list[dict] = []
        for name, field in model.model_fields.items():
            ann = field.annotation
            type_str = _annotation_to_godot_type(provider, ann)
            properties.append(
                {"name": name, "type": type_str, "description": field.description or ""}
            )
        signals = provider.signals_of(class_name) or {}
        signals_list = [
            {
                "name": sig_name,
                "info": str(sig_info),
                "arguments": [
                    {"name": arg.name, "type": arg.type} for arg in sig_info.arguments
                ],
            }
            for sig_name, sig_info in signals.items()
        ]
        inheritance: list[str] = []
        for base in model.__mro__:
            godot_name = provider.godot_name_of(base)
            if godot_name is not None:
                inheritance.append(godot_name)
        inheritance.reverse()
        return json.dumps(
            {
                "ok": True,
                "class": class_name,
                "version": ver or "default",
                "properties": properties,
                "signals": signals_list,
                "inheritance": inheritance,
            },
            indent=2,
        )
