"""MCP tools for tscn scene editing operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from godotllminteraction import tscn as tscn_lib
from godotllminteraction.mcp.context import McpContext
from godotllminteraction.tscn.exceptions import OperationError, TscnError
from godotllminteraction.tscn.godot_check import GodotNotFoundError


def _error_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def _apply_result_json(result: tscn_lib.ApplyResult, output_path: Path) -> str:
    new_text = tscn_lib.dump_scene(result.scene)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(new_text)
    return json.dumps(
        {
            "ok": True,
            "changed": result.changed,
            "output": str(output_path),
            "operations": [
                {
                    "op": r.op,
                    "changed": r.changed,
                    "affected_paths": r.affected_paths,
                    "allocated_ids": r.allocated_ids,
                    "issues": [i.model_dump() for i in r.report.issues],
                }
                for r in result.results
            ],
        }
    )


def _run_op(
    scene_path: str,
    operation: tscn_lib.Operation,
    output: str | None,
    *,
    strict: bool = True,
) -> str:
    p = Path(scene_path)
    if not p.exists():
        return _error_json(f"Scene file not found: {scene_path}")
    try:
        scene = tscn_lib.load_scene(p)
    except TscnError as exc:
        return _error_json(str(exc))
    try:
        result = tscn_lib.apply_operations(scene, [operation], strict=strict)
    except OperationError as exc:
        return _error_json(str(exc))
    out = Path(output) if output else p
    return _apply_result_json(result, out)


def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def add_node(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[
            str, Field(description="Scene path of the new node, e.g. 'Player/Sprite'.")
        ],
        type: Annotated[
            str | None, Field(description="Godot class name, e.g. 'Sprite2D'.")
        ] = None,
        instance: Annotated[
            str | None,
            Field(description='ExtResource("id") literal for an instanced scene.'),
        ] = None,
        properties: Annotated[
            dict[str, str] | None,
            Field(description="Key-value props in Godot literal syntax."),
        ] = None,
        groups: Annotated[
            list[str] | None, Field(description="Node group names.")
        ] = None,
        index: Annotated[
            int | None, Field(description="Position among siblings.")
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Add a node to a Godot scene."""
        op = tscn_lib.AddNode(
            path=path,
            type=type,
            instance=instance,
            properties=properties or {},
            groups=groups,
            index=index,
        )
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def delete_node(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node to delete.")],
        recursive: Annotated[
            bool, Field(description="Also delete descendants.")
        ] = True,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Delete a node (and by default its whole subtree)."""
        op = tscn_lib.DeleteNode(path=path, recursive=recursive)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def update_properties(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node.")],
        properties: Annotated[
            dict[str, str] | None,
            Field(description="Key-value props in Godot literal syntax."),
        ] = None,
        remove: Annotated[
            list[str] | None, Field(description="Property names to drop.")
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Set and/or remove properties on an existing node."""
        op = tscn_lib.UpdateProperties(
            path=path,
            properties=properties or {},
            remove=remove or [],
        )
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def rename_node(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node to rename.")],
        new_name: Annotated[
            str, Field(description="The node's new name (single segment).")
        ],
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Rename a node; descendants, connections, and NodePath values are rewritten."""
        op = tscn_lib.RenameNode(path=path, new_name=new_name)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def move_node(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node to move.")],
        new_parent: Annotated[
            str, Field(description="Scene path of the new parent ('.' for root).")
        ],
        index: Annotated[
            int | None, Field(description="Position among new siblings.")
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Reparent a node; descendants, connections, and NodePath values are rewritten."""
        op = tscn_lib.MoveNode(path=path, new_parent=new_parent, index=index)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def attach_script(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node.")],
        script_path: Annotated[
            str, Field(description="res:// path of the .gd script.")
        ],
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Attach a script to a node, reusing or adding the Script ext_resource."""
        op = tscn_lib.AttachScript(path=path, script_path=script_path)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def detach_script(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        path: Annotated[str, Field(description="Scene path of the node.")],
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Remove a node's script (and the Script ext_resource if unreferenced)."""
        op = tscn_lib.DetachScript(path=path)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def add_ext_resource(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        type: Annotated[
            str, Field(description="Godot resource class, e.g. 'Texture2D'.")
        ],
        res_path: Annotated[
            str, Field(description="res:// path of the external file.")
        ],
        id: Annotated[
            str | None,
            Field(description="Scene-local resource id; leave unset for generated."),
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Declare an external resource the scene can reference."""
        op = tscn_lib.AddExtResource(type=type, path=res_path, id=id)
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def create_sub_resource(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        type: Annotated[
            str, Field(description="Godot Resource subclass, e.g. 'RectangleShape2D'.")
        ],
        properties: Annotated[
            dict[str, str] | None,
            Field(description="Key-value props in Godot literal syntax."),
        ] = None,
        id: Annotated[
            str | None,
            Field(description="Scene-local resource id; leave unset for generated."),
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Embed a resource inside the scene file."""
        op = tscn_lib.CreateSubResource(type=type, id=id, properties=properties or {})
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def connect_signal(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        from_node: Annotated[
            str, Field(description="Scene path of the node emitting the signal.")
        ],
        to: Annotated[
            str, Field(description="Scene path of the node whose method is called.")
        ],
        signal: Annotated[str, Field(description="Signal name.")],
        method: Annotated[
            str, Field(description="Receiving method name on the target's script.")
        ],
        flags: Annotated[
            int | None, Field(description="Godot ConnectFlags bitmask.")
        ] = None,
        binds: Annotated[
            str | None, Field(description="Extra bound arguments, e.g. '[1, \"two\"]'.")
        ] = None,
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Add a connection wiring a signal to a method on another node."""
        op = tscn_lib.ConnectSignal(
            **{"from": from_node, "to": to, "signal": signal, "method": method},
            flags=flags,
            binds=binds,
        )
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def disconnect_signal(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        from_node: Annotated[
            str, Field(description="Scene path of the emitting node.")
        ],
        to: Annotated[str, Field(description="Scene path of the target node.")],
        signal: Annotated[str, Field(description="Signal name.")],
        method: Annotated[str, Field(description="Receiving method name.")],
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Remove a matching signal connection."""
        op = tscn_lib.DisconnectSignal(
            **{"from": from_node, "to": to, "signal": signal, "method": method},
        )
        return _run_op(scene_path, op, output, strict=strict)

    @server.tool()
    async def apply_ops_file(
        ops_file_path: Annotated[
            str, Field(description="Path to a YAML operations file.")
        ],
        scene_path: Annotated[
            str | None,
            Field(description="Scene file to edit; overrides ops file's 'scene' key."),
        ] = None,
        output: Annotated[
            str | None,
            Field(description="Output path; overrides ops file's 'output' key."),
        ] = None,
        strict: Annotated[
            bool | None, Field(description="Override ops file's strict setting.")
        ] = None,
    ) -> str:
        """Apply a YAML operations file to a scene (all-or-nothing, idempotent)."""
        ops_p = Path(ops_file_path)
        if not ops_p.exists():
            return _error_json(f"Ops file not found: {ops_file_path}")
        try:
            ops = tscn_lib.load_ops_file(ops_p)
        except TscnError as exc:
            return _error_json(str(exc))
        if strict is not None:
            ops.strict = strict
        input_path = scene_path or (ops.scene if ops.scene else None)
        try:
            if input_path is not None:
                ip = Path(input_path)
                if not ip.exists():
                    return _error_json(f"Scene file not found: {input_path}")
                scene = tscn_lib.load_scene(ip)
            else:
                scene = tscn_lib.initial_scene(ops)
        except TscnError as exc:
            return _error_json(str(exc))
        try:
            result = tscn_lib.apply_ops_file(ops, scene)
        except TscnError as exc:
            return _error_json(str(exc))
        out_str = output or ops.output or input_path
        if out_str is None:
            return _error_json("No output destination: pass output.")
        return _apply_result_json(result, Path(out_str))

    @server.tool()
    async def tree(
        scene_path: Annotated[
            str, Field(description="Path to the .tscn file to inspect.")
        ],
        detail: Annotated[
            str,
            Field(description="Detail level: 'nodes', 'resources', or 'properties'."),
        ] = "nodes",
    ) -> str:
        """Print the scene tree as JSON."""
        if detail not in ("nodes", "resources", "properties"):
            return _error_json(
                f"Invalid detail {detail!r}; expected nodes, resources, or properties."
            )
        p = Path(scene_path)
        if not p.exists():
            return _error_json(f"Scene file not found: {scene_path}")
        try:
            scene = tscn_lib.load_scene(p)
        except TscnError as exc:
            return _error_json(str(exc))
        built = tscn_lib.build_tree(scene, detail)  # type: ignore[arg-type]
        if built is None:
            return _error_json("Scene has no root node.")
        return json.dumps(built.model_dump(), indent=2)

    @server.tool()
    async def validate(
        target: Annotated[
            str, Field(description="A .tscn file path or 'project.godot'.")
        ],
        project: Annotated[
            str, Field(description="Project directory containing project.godot.")
        ] = ".",
        godot: Annotated[
            str | None, Field(description="Path to the Godot executable.")
        ] = None,
    ) -> str:
        """Validate a Godot scene or the whole project using the Godot editor."""
        try:
            result = tscn_lib.check_scene(
                target, project_dir=Path(project), godot=godot
            )
        except GodotNotFoundError as exc:
            return _error_json(str(exc))
        return json.dumps(result.model_dump(), indent=2)

    @server.tool()
    async def set_godot_version(
        version: Annotated[str, Field(description="Godot version, e.g. '4.7.0'.")],
    ) -> str:
        """Set the default Godot version for subsequent operations."""
        ctx.godot_version = version
        return json.dumps({"ok": True, "version": version})

    @server.tool()
    async def set_project(
        project_path: Annotated[
            str, Field(description="Absolute path to the Godot project directory.")
        ],
    ) -> str:
        """Set the working project path for KB operations."""
        ctx.project_path = project_path
        return json.dumps({"ok": True, "project_path": project_path})
