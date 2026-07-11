"""YAML bulk-operations files: the batch frontend over operations.py.

An ops file reuses the same Operation models (single source of truth) and
adds two conveniences the core doesn't need:

- `ref:` on add_ext_resource / create_sub_resource registers a symbolic
  handle for the allocated id;
- `{ext_resource: <ref>}` / `{sub_resource: <ref>}` anywhere in a later
  op's values resolves to the corresponding ExtResource("id")/SubResource("id")
  literal. Since ids are allocated when their op runs, resolution happens
  op-by-op during apply.

pyyaml is imported here only; the rest of the tscn package stays dependency-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from godotllminteraction.tscn.exceptions import OperationError, TscnError
from godotllminteraction.tscn.operations import (
    ApplyResult,
    Operation,
    OpResult,
    apply_operation,
)
from godotllminteraction.tscn.scene import NodeEntry, Scene, SceneHeader
from godotllminteraction.tscn.specs import SpecProvider
from godotllminteraction.tscn.values import GInt, GString

_OPERATION_ADAPTER: TypeAdapter = TypeAdapter(Operation)


class CreateSpec(BaseModel):
    """Start from a brand-new scene instead of editing an existing file."""

    root_name: str = Field(description="Name of the new scene's root node.")
    root_type: str = Field(description="Godot class of the root node, e.g. 'Node2D'.")


class OpsFile(BaseModel):
    version: Literal[1] = 1
    scene: str | None = Field(
        None, description="Scene file to edit; mutually exclusive with 'create'."
    )
    output: str | None = Field(
        None, description="Where to write the result; default is in-place."
    )
    create: CreateSpec | None = Field(
        None, description="Start from a brand-new scene instead of editing a file."
    )
    strict: bool = Field(
        True, description="Whether spec-validation errors abort the batch."
    )
    operations: list[dict] = Field(
        default_factory=list,
        # Raw dicts, not Operation models: `ref:` handles and {ext_resource: ...}
        # placeholders must be stripped/resolved per-op during apply.
        description="The operations, in order; see operations.Operation for the shapes.",
    )


class OpsFileError(TscnError):
    """The ops file itself is malformed (bad YAML, bad op shape, bad ref)."""


def load_ops_file(path: Path) -> OpsFile:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise OpsFileError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise OpsFileError(f"{path}: expected a mapping at the top level")
    try:
        return OpsFile.model_validate(data)
    except ValidationError as exc:
        raise OpsFileError(f"{path}: {exc}") from exc


def initial_scene(ops_file: OpsFile) -> Scene:
    """The scene a `create:` ops file starts from."""
    if ops_file.create is None:
        raise OpsFileError("ops file has neither 'scene' nor 'create'")
    # No uid= in the header: scene uids are Godot's to assign; the editor
    # adds one the first time the scene is saved.
    header: dict = {"format": GInt(value=3)}
    scene = Scene(header=SceneHeader(attributes=header))
    scene.nodes.append(
        NodeEntry(
            attributes={
                "name": GString(value=ops_file.create.root_name),
                "type": GString(value=ops_file.create.root_type),
            }
        )
    )
    return scene


def _resolve_ref_placeholders(value: object, refs: dict[str, str]) -> object:
    """Replace {ext_resource: ref} / {sub_resource: ref} placeholders with
    the corresponding Godot literal, recursively through dicts and lists."""
    if isinstance(value, dict):
        if set(value) == {"ext_resource"} or set(value) == {"sub_resource"}:
            kind, ref_name = next(iter(value.items()))
            if not isinstance(ref_name, str):
                raise OpsFileError(
                    f"{kind} placeholder must name a ref, got {ref_name!r}"
                )
            if ref_name not in refs:
                raise OpsFileError(
                    f"unknown ref {ref_name!r}; declare it with 'ref: {ref_name}' "
                    "on an earlier add_ext_resource/create_sub_resource operation"
                )
            call = "ExtResource" if kind == "ext_resource" else "SubResource"
            return f'{call}("{refs[ref_name]}")'
        return {k: _resolve_ref_placeholders(v, refs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_ref_placeholders(item, refs) for item in value]
    return value


def apply_ops_file(
    ops_file: OpsFile,
    scene: Scene,
    *,
    provider: SpecProvider | None = None,
) -> ApplyResult:
    """Apply an ops file to `scene` (all-or-nothing, input never mutated)."""
    working = scene.model_copy(deep=True)
    refs: dict[str, str] = {}
    results: list[OpResult] = []
    for position, raw in enumerate(ops_file.operations, start=1):
        if not isinstance(raw, dict):
            raise OpsFileError(f"operation {position}: expected a mapping, got {raw!r}")
        spec = dict(raw)
        ref_name = spec.pop("ref", None)
        spec = _resolve_ref_placeholders(spec, refs)
        try:
            operation = _OPERATION_ADAPTER.validate_python(spec)
        except ValidationError as exc:
            raise OpsFileError(f"operation {position}: {exc}") from exc
        try:
            result = apply_operation(
                working, operation, provider=provider, strict=ops_file.strict
            )
        except OperationError as exc:
            raise OperationError(
                f"operation {position} ({operation.op}): {exc}"
            ) from exc
        results.append(result)
        if ref_name is not None:
            allocated = result.allocated_ids.get("id")
            if allocated is None:
                raise OpsFileError(
                    f"operation {position}: 'ref' is only valid on "
                    "add_ext_resource/create_sub_resource"
                )
            refs[str(ref_name)] = allocated
    return ApplyResult(scene=working, results=results)
