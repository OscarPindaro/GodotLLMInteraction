"""MCP tools for tscn scene editing operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from godotllminteraction import tscn as tscn_lib
from godotllminteraction.mcp.context import McpContext
from godotllminteraction.tscn.exceptions import (
    OperationError,
    SceneValidationError,
    TscnError,
)
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
    return _run_ops(scene_path, [operation], output, strict=strict)


def _run_ops(
    scene_path: str,
    operations: list[tscn_lib.Operation],
    output: str | None,
    *,
    strict: bool = True,
    resolver: tscn_lib.ClassResolver | None = None,
) -> str:
    p = Path(scene_path)
    if not p.exists():
        return _error_json(f"Scene file not found: {scene_path}")
    try:
        scene = tscn_lib.load_scene(p)
    except TscnError as exc:
        return _error_json(str(exc))
    try:
        result = tscn_lib.apply_operations(
            scene, operations, strict=strict, resolver=resolver
        )
    except (OperationError, SceneValidationError) as exc:
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
            str | None,
            Field(
                description="Godot class name, e.g. 'Sprite2D'. If the name "
                "is a script-defined class_name found in the project, the "
                "node is created with the script's base type and the script "
                "is auto-attached."
            ),
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
        """Add a node to a Godot scene. Script-defined class_name types are
        automatically resolved to (base_type, script)."""
        effective_type = type
        script_to_attach: str | None = None
        if type is not None and instance is None:
            provider = tscn_lib.default_provider()
            if provider.resolve_class(type) is None:
                project = tscn_lib.find_project_path(Path(scene_path))
                if project is not None:
                    resolver = tscn_lib.ClassResolver(project)
                    info = resolver.resolve(type)
                    if info is not None:
                        effective_type = info.base_type
                        script_to_attach = info.script_path

        ops: list[tscn_lib.Operation] = [
            tscn_lib.AddNode(
                path=path,
                type=effective_type,
                instance=instance,
                properties=properties or {},
                groups=groups,
                index=index,
            )
        ]
        if script_to_attach is not None:
            ops.append(tscn_lib.AttachScript(path=path, script_path=script_to_attach))
        return _run_ops(scene_path, ops, output, strict=strict)

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
    async def add_sprite_image(
        scene_path: Annotated[str, Field(description="Path to the .tscn file.")],
        texture: Annotated[
            str,
            Field(
                description="res:// path to a Texture2D resource (PNG, SVG, "
                "CompressedTexture2D, or a custom .tres texture). For custom "
                "types, also pass texture_type."
            ),
        ],
        cell: Annotated[
            tuple[int, int],
            Field(description="(col, row) grid coordinate of the tile, 0-based."),
        ],
        node: Annotated[
            str | None,
            Field(
                description="Target node. None (default): create/reuse the "
                "resource only, no node wiring or creation (used to "
                "pre-create AtlasTexture frames for add_animation). A bare "
                "name with no '/' ('Sprite2D') is looked up by name anywhere "
                "in the tree (error if ambiguous); a path ('Chest/Sprite2D') "
                "is explicit. Missing nodes are auto-created as Sprite2D "
                "(parent must already exist for path references). Append "
                "'.property' to wire something other than 'texture', e.g. "
                "'Chest.closed_texture' — atlas mode only. If the node name "
                "matches a script-defined class_name, the node is created "
                "with the script's base type and the script auto-attached."
            ),
        ] = None,
        mode: Annotated[
            str,
            Field(
                description="'region' (default): sets region_enabled + "
                "region_rect directly on the node's own texture; no extra "
                "resource; not shareable across sprites. 'atlas': "
                "creates/reuses an AtlasTexture sub_resource (deduped by "
                "atlas+region); shareable, and required for animation frames. "
                "'full': sets the whole texture directly on the node, no "
                "region (for non-atlas textures)."
            ),
        ] = "region",
        id: Annotated[
            str | None,
            Field(
                description="AtlasTexture sub_resource id (atlas mode only; "
                "ignored in region/full mode). Pass a readable id ('knight', "
                "'door_open') so repeated calls with the same cell cleanly "
                "dedupe to the same resource; leave unset for a generated id."
            ),
        ] = None,
        tile_width: Annotated[int, Field(description="Tile width in pixels.")] = 16,
        tile_height: Annotated[int, Field(description="Tile height in pixels.")] = 16,
        margin: Annotated[
            int, Field(description="Pixel offset before the grid starts.")
        ] = 0,
        spacing: Annotated[int, Field(description="Pixel gap between tiles.")] = 0,
        texture_filter: Annotated[
            int | str | None,
            Field(
                description="0=nearest, 1=linear, 2=nearest_with_mipmaps, "
                "3=linear_with_mipmaps, 4=nearest_with_mipmaps_anisotropic, "
                "5=linear_with_mipmaps_anisotropic. Accepts the int or the "
                "name (case-insensitive). If omitted (default), texture_filter "
                "is not set (uses project default). Only applied when 'node' "
                "is set."
            ),
        ] = None,
        texture_type: Annotated[
            str,
            Field(
                description="ext_resource type for the texture; override "
                "for custom .tres texture classes (defaults to 'Texture2D')."
            ),
        ] = "Texture2D",
        output: Annotated[
            str | None, Field(description="Output path; defaults to in-place.")
        ] = None,
        strict: Annotated[
            bool, Field(description="Whether spec-validation errors abort.")
        ] = True,
    ) -> str:
        """Set up a sprite from a texture atlas cell (region_rect, AtlasTexture, or full texture), optionally wiring/auto-creating a node."""
        op = tscn_lib.AddSpriteImage(
            texture=texture,
            cell=cell,
            node=node,
            mode=mode,
            id=id,
            tile_width=tile_width,
            tile_height=tile_height,
            margin=margin,
            spacing=spacing,
            texture_filter=texture_filter,
            texture_type=texture_type,
        )

        # If the node will be auto-created and its name matches a script-defined
        # class_name, pre-create it with the script attached so custom properties
        # pass validation.
        pre_ops: list[tscn_lib.Operation] = []
        resolver: tscn_lib.ClassResolver | None = None
        if node is not None:
            node_ref = node.split(".")[0]
            bare_name = node_ref.split("/")[-1]
            project = tscn_lib.find_project_path(Path(scene_path))
            if project is not None:
                resolver = tscn_lib.ClassResolver(project)
                scene = tscn_lib.load_scene(Path(scene_path))
                if "/" in node_ref:
                    existing = scene.node(node_ref)
                else:
                    existing = next(
                        (n for n in scene.nodes if n.name == node_ref), None
                    )
                if existing is None:
                    info = resolver.resolve(bare_name)
                    if info is not None:
                        pre_ops.append(
                            tscn_lib.AddNode(path=node_ref, type=info.base_type)
                        )
                        pre_ops.append(
                            tscn_lib.AttachScript(
                                path=node_ref, script_path=info.script_path
                            )
                        )

        return _run_ops(
            scene_path, pre_ops + [op], output, strict=strict, resolver=resolver
        )

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
    async def create_scene(
        scene_path: Annotated[
            str, Field(description="Output .tscn file path to create.")
        ],
        tree: Annotated[
            str | None,
            Field(
                description="Tree-format text. Each line: Name (Type) [key: value, unique]. "
                "Indent with box-drawing (├── └── │) or ASCII (|-- `-- | - _). "
                "Type is a built-in Godot class or a project class_name. "
                "'unique' sets unique_name_in_owner. Mutually exclusive with json_spec."
            ),
        ] = None,
        json_spec: Annotated[
            dict | None,
            Field(
                description="JSON scene spec: {root: {name, type, properties, unique, children: [...]}}. "
                "Mutually exclusive with tree."
            ),
        ] = None,
        project_path: Annotated[
            str | None,
            Field(
                description="Godot project dir for class_name resolution. "
                "Defaults to the set project path, or auto-detected from scene_path."
            ),
        ] = None,
        overwrite: Annotated[
            bool,
            Field(
                description="If False (default), errors when the file already exists."
            ),
        ] = False,
        validate: Annotated[
            bool,
            Field(
                description="If True, runs Godot --check-only after writing. "
                "If Godot is not found, the scene is still created and validation "
                "status is reported in the response."
            ),
        ] = False,
        strict: Annotated[
            bool,
            Field(
                description="If True (default), spec-validation errors abort the operation."
            ),
        ] = True,
    ) -> str:
        """Create a complete .tscn scene from a tree or JSON description.

        Tree format — one node per line, indentation determines parent:
          Root (Node2D)
          ├── Player (CharacterBody2D) [unique]
          │   └── Camera (Camera2D)
          └── Label (Label) [text: "Hello", position: Vector2(0, 0)]

        - Name is required; (Type) defaults to Node if omitted.
        - Type can be a built-in Godot class or a project class_name
          (resolved via .gd file scanning — script auto-attached).
        - [key: value, ...] sets properties (Godot literal syntax).
        - 'unique' keyword in brackets sets unique_name_in_owner.
        - Properties can span a continuation line starting with '['.

        JSON format: {root: {name, type, properties, unique, children: [...]}}.

        Returns: {ok, output, validation}.
        """
        if tree is None and json_spec is None:
            return _error_json("Exactly one of 'tree' or 'json_spec' must be provided.")
        if tree is not None and json_spec is not None:
            return _error_json("Provide 'tree' OR 'json_spec', not both.")

        out = Path(scene_path)
        if out.exists() and not overwrite:
            return _error_json(
                f"File already exists: {scene_path}. Pass overwrite=True to replace."
            )

        # Resolve project path for class_name lookup.
        effective_project = project_path or ctx.project_path
        resolver = None
        if effective_project is not None:
            resolver = tscn_lib.ClassResolver(Path(effective_project))
        else:
            detected = tscn_lib.find_project_path(out.parent)
            if detected is not None:
                resolver = tscn_lib.ClassResolver(detected)

        try:
            if tree is not None:
                spec = tscn_lib.parse_tree(tree)
            else:
                spec = tscn_lib.parse_json(json_spec)
            scene = tscn_lib.build_scene(spec, class_resolver=resolver, strict=strict)
        except (tscn_lib.TscnError, tscn_lib.SceneBuilderError) as exc:
            return _error_json(str(exc))

        text = tscn_lib.dump_scene(scene)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

        validation = None
        if validate:
            try:
                godot = tscn_lib.find_godot()
                project_dir = (
                    Path(effective_project)
                    if effective_project
                    else (tscn_lib.find_project_path(out.parent) or out.parent)
                )
                result = tscn_lib.check_scene(
                    out.name, project_dir=project_dir, godot=godot
                )
                validation = result.model_dump()
            except tscn_lib.GodotNotFoundError as exc:
                validation = {"ok": False, "error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                validation = {"ok": False, "error": str(exc)}

        return json.dumps(
            {
                "ok": True,
                "output": str(out),
                "validation": validation,
            },
            indent=2,
        )

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
