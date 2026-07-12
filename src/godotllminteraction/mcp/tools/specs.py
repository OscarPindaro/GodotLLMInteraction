"""MCP tools for querying Godot API specifications."""

from __future__ import annotations

import importlib
import json
import re
from typing import Annotated

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
            ann_str = str(ann) if ann is not None else "None"
            properties.append(
                {"name": name, "type": ann_str, "description": field.description or ""}
            )
        signals = provider.signals_of(class_name) or {}
        signals_list = [
            {"name": sig_name, "info": str(sig_info)}
            for sig_name, sig_info in signals.items()
        ]
        inheritance: list[str] = []
        for base in model.__mro__:
            godot_name = provider.godot_name_of(base)
            if godot_name is not None:
                inheritance.append(godot_name)
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
