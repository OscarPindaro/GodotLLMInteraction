"""Spec-backed validation of scenes, node properties, and connections.

Philosophy: errors are reserved for things the specification proves wrong
(unknown class, unknown property on a script-less engine node, value of the
wrong shape). Anything the spec can't see — properties exported by an
attached script, instanced-scene overrides, metadata — degrades to a warning
or is accepted, so valid scenes never fail on the tool's blind spots.
"""

from __future__ import annotations

from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

from godotllminteraction.tscn.scene import (
    NodeEntry,
    Scene,
    SubResourceEntry,
)
from godotllminteraction.tscn.specs import SpecProvider, default_provider
from godotllminteraction.tscn.values import (
    GArray,
    GBool,
    GCall,
    GFloat,
    GInt,
    GNodePath,
    GNull,
    GString,
    GStringName,
    GodotValue,
    format_value,
    is_ext_resource_ref,
    resource_ref_id,
)


class Issue(BaseModel):
    severity: Literal["error", "warning"]
    message: str
    node_path: str | None = None
    property: str | None = None

    def __str__(self) -> str:
        where = ""
        if self.node_path is not None:
            where = f" [{self.node_path}]"
            if self.property is not None:
                where = f" [{self.node_path}.{self.property}]"
        elif self.property is not None:
            where = f" [{self.property}]"
        return f"{self.severity}{where}: {self.message}"


class ValidationReport(BaseModel):
    issues: list[Issue] = []

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(
        self, message: str, *, node_path: str | None = None, property: str | None = None
    ) -> None:
        self.issues.append(
            Issue(
                severity="error",
                message=message,
                node_path=node_path,
                property=property,
            )
        )

    def warning(
        self, message: str, *, node_path: str | None = None, property: str | None = None
    ) -> None:
        self.issues.append(
            Issue(
                severity="warning",
                message=message,
                node_path=node_path,
                property=property,
            )
        )

    def merge(self, other: ValidationReport) -> None:
        self.issues.extend(other.issues)


def _describe(value: GodotValue) -> str:
    text = format_value(value, canonical=True)
    return text if len(text) <= 60 else text[:57] + "..."


def _value_matches_annotation(
    value: GodotValue,
    annotation: object,
    scene: Scene,
    provider: SpecProvider,
) -> str | None:
    """None if `value` fits `annotation`, else a human-readable mismatch reason."""
    annotation = provider.resolve_annotation(annotation)
    if annotation is Any or annotation is None:
        return None

    origin = get_origin(annotation)
    if origin is list:
        return _list_value_matches(value, get_args(annotation)[0], scene, provider)

    if annotation is bool:
        return (
            None
            if isinstance(value, GBool)
            else f"expected bool, got {_describe(value)}"
        )
    if annotation is int:
        return (
            None if isinstance(value, GInt) else f"expected int, got {_describe(value)}"
        )
    if annotation is float:
        if isinstance(value, (GFloat, GInt)):
            return None
        return f"expected float, got {_describe(value)}"
    if annotation is str:
        if isinstance(value, (GString, GStringName, GNodePath)):
            return None
        return f"expected a string/StringName/NodePath, got {_describe(value)}"

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        godot_name = provider.godot_name_of(annotation)
        if provider.resolve_builtin(godot_name or "") is annotation:
            return _builtin_value_matches(value, annotation, godot_name, provider)
        return _resource_value_matches(value, godot_name, scene, provider)

    return None  # unknown annotation shape: give the value the benefit of the doubt


def _builtin_value_matches(
    value: GodotValue,
    model: type[BaseModel],
    godot_name: str | None,
    provider: SpecProvider,
) -> str | None:
    if not isinstance(value, GCall) or value.name != godot_name:
        return f"expected {godot_name}(...), got {_describe(value)}"
    expected_args = provider.scalar_width(model)
    if len(value.args) != expected_args:
        return (
            f"{godot_name}(...) expects {expected_args} scalar arguments, "
            f"got {len(value.args)}"
        )
    for arg in value.args:
        if not isinstance(arg, (GInt, GFloat)):
            return f"{godot_name}(...) arguments must be numbers, got {_describe(arg)}"
    return None


def _resource_value_matches(
    value: GodotValue,
    expected_class: str | None,
    scene: Scene,
    provider: SpecProvider,
) -> str | None:
    if isinstance(value, GNull):
        return None
    if not isinstance(value, GCall) or value.name not in ("ExtResource", "SubResource"):
        return f"expected an ExtResource/SubResource reference to a {expected_class}, got {_describe(value)}"

    ref_id = resource_ref_id(value)
    if is_ext_resource_ref(value):
        entry = scene.ext_resource(ref_id)
        if entry is None:
            return f'ExtResource("{ref_id}") does not match any [ext_resource] in the scene'
        declared = entry.type
    else:
        sub_entry = scene.sub_resource(ref_id)
        if sub_entry is None:
            return f'SubResource("{ref_id}") does not match any [sub_resource] in the scene'
        declared = sub_entry.type

    if declared is None or expected_class is None:
        return None
    fits = provider.is_subclass(declared, expected_class)
    if fits is False:
        # A type="Resource" entry with a script attached legitimately stands
        # in for any script-defined resource class; don't second-guess it.
        if declared == "Resource":
            return None
        return f"resource {ref_id!r} is a {declared}, which is not a {expected_class}"
    return None


def _list_value_matches(
    value: GodotValue,
    element_annotation: object,
    scene: Scene,
    provider: SpecProvider,
) -> str | None:
    element_annotation = provider.resolve_annotation(element_annotation)
    if isinstance(value, GArray):
        for item in value.items:
            reason = _value_matches_annotation(
                item, element_annotation, scene, provider
            )
            if reason is not None:
                return f"array element: {reason}"
        return None
    if isinstance(value, GCall) and value.name == "PackedByteArray":
        # Godot 4.3+ serializes byte arrays as a single base64 string.
        if len(value.args) == 1 and isinstance(value.args[0], GString):
            return None
    if isinstance(value, GCall) and value.name.startswith("Packed"):
        # Flat Packed*Array literal: PackedVector2Array(10, 0, 0, 20) is two
        # Vector2 elements. Argument count must divide by the element width.
        if isinstance(element_annotation, type) and issubclass(
            element_annotation, BaseModel
        ):
            width = provider.scalar_width(element_annotation)
        else:
            width = 1
        if width > 1 and len(value.args) % width != 0:
            return (
                f"{value.name}(...) has {len(value.args)} scalar arguments, "
                f"not a multiple of the element width {width}"
            )
        if element_annotation is str:
            wrong = next(
                (a for a in value.args if not isinstance(a, (GString, GStringName))),
                None,
            )
        else:
            wrong = next(
                (a for a in value.args if not isinstance(a, (GInt, GFloat))), None
            )
        if wrong is not None:
            return f"{value.name}(...) element {_describe(wrong)} has the wrong type"
        return None
    return f"expected an array, got {_describe(value)}"


def _node_has_script(node: NodeEntry) -> bool:
    return "script" in node.properties or node.is_instance


# Properties Godot serializes but does not list in extension_api.json's
# `properties` (they're exposed through methods only). Files written by the
# editor legitimately contain them, so they're accepted on any class rather
# than treated as typos. Extend as new gaps are found.
_SERIALIZATION_ONLY_PROPERTIES = {
    "libraries",  # AnimationMixer/AnimationPlayer animation libraries dict
}


def _field_annotation(model: type[BaseModel], key: str) -> object | Literal["missing"]:
    """The annotation for a Godot property name, honoring the generator's
    keyword-safe renaming ('from' is generated as 'from_')."""
    for candidate in (key, f"{key}_"):
        field = model.model_fields.get(candidate)
        if field is not None:
            return field.annotation
    return "missing"


def validate_properties(
    *,
    scene: Scene,
    model: type[BaseModel] | None,
    properties: dict[str, GodotValue],
    has_script: bool,
    node_path: str | None,
    provider: SpecProvider,
) -> ValidationReport:
    report = ValidationReport()
    for key, value in properties.items():
        if "/" in key or key.startswith("_") or key in _SERIALIZATION_ONLY_PROPERTIES:
            # metadata/*, theme_override_*/..., tracks/N/... are dynamic
            # property paths; _data and friends are internal serialization
            # properties exposed via _set/_get. Neither is in the flat spec
            # model, both are legitimate. Accepted.
            continue
        if model is None:
            continue
        annotation = _field_annotation(model, key)
        if annotation == "missing":
            if key == "script":
                continue  # every Object accepts a script; specs omit it
            if has_script:
                report.warning(
                    f"property {key!r} is not in the {provider.godot_name_of(model)} "
                    "spec; assuming it is exported by the attached script",
                    node_path=node_path,
                    property=key,
                )
            else:
                report.error(
                    f"unknown property {key!r} for class {provider.godot_name_of(model)}",
                    node_path=node_path,
                    property=key,
                )
            continue
        reason = _value_matches_annotation(value, annotation, scene, provider)
        if reason is not None:
            report.error(reason, node_path=node_path, property=key)
    return report


def validate_node(
    scene: Scene,
    node: NodeEntry,
    provider: SpecProvider | None = None,
) -> ValidationReport:
    provider = provider or default_provider()
    report = ValidationReport()
    path = node.path()

    type_name = node.type
    model = None
    if node.is_instance or type_name is None:
        # Instanced node, or an override entry for a child inside an
        # instanced subtree: the real type lives in the other scene file.
        pass
    else:
        model = provider.resolve_class(type_name)
        if model is None:
            if _node_has_script(node):
                report.warning(
                    f"unknown class {type_name!r}; assuming a script-defined class",
                    node_path=path,
                )
            else:
                report.error(f"unknown class {type_name!r}", node_path=path)

    report.merge(
        validate_properties(
            scene=scene,
            model=model,
            properties=node.properties,
            has_script=_node_has_script(node),
            node_path=path,
            provider=provider,
        )
    )
    return report


def validate_sub_resource(
    scene: Scene,
    sub: SubResourceEntry,
    provider: SpecProvider | None = None,
) -> ValidationReport:
    provider = provider or default_provider()
    report = ValidationReport()
    label = f"sub_resource:{sub.id}"

    model = None
    type_name = sub.type
    if type_name is None:
        report.error("sub_resource has no type", node_path=label)
    else:
        model = provider.resolve_class(type_name)
        if model is None:
            report.error(f"unknown resource class {type_name!r}", node_path=label)
        else:
            fits = provider.is_subclass(type_name, "Resource")
            if fits is False:
                report.error(f"{type_name} is not a Resource subclass", node_path=label)

    report.merge(
        validate_properties(
            scene=scene,
            model=model,
            properties=sub.properties,
            has_script="script" in sub.properties,
            node_path=label,
            provider=provider,
        )
    )
    return report


def validate_connection_signal(
    scene: Scene,
    from_path: str,
    signal: str,
    provider: SpecProvider | None = None,
) -> ValidationReport:
    provider = provider or default_provider()
    report = ValidationReport()
    source = scene.node(from_path)
    if source is None:
        report.error(
            f"connection source {from_path!r} does not exist", node_path=from_path
        )
        return report
    if source.type is None:
        return report  # instanced/override node: signal set unknowable offline
    signals = provider.signals_of(source.type)
    if signals is None:
        return report  # unknown class was already reported by validate_node
    if signal not in signals:
        message = f"class {source.type!r} has no signal {signal!r}"
        if _node_has_script(source):
            report.warning(
                message + "; assuming it is declared by the attached script",
                node_path=from_path,
            )
        else:
            report.error(message, node_path=from_path)
    return report


def validate_scene(
    scene: Scene, provider: SpecProvider | None = None
) -> ValidationReport:
    """Validate a whole parsed scene: structure, classes, properties, connections."""
    provider = provider or default_provider()
    report = ValidationReport()

    roots = [n for n in scene.nodes if n.parent is None]
    if len(roots) != 1:
        report.error(f"scene must have exactly one root node, found {len(roots)}")

    seen_paths: set[str] = set()
    for node in scene.nodes:
        path = node.path()
        if path in seen_paths:
            report.error("duplicate node name among siblings", node_path=path)
        seen_paths.add(path)
        if (
            node.parent is not None
            and node.parent not in seen_paths
            and scene.node(node.parent) is None
        ):
            report.error(
                f"parent {node.parent!r} does not exist (or appears after its child)",
                node_path=path,
            )
        report.merge(validate_node(scene, node, provider))

    seen_ids: set[str] = set()
    for ext in scene.ext_resources:
        if ext.id is None:
            report.error("ext_resource has no id")
        elif ext.id in seen_ids:
            report.error(f"duplicate ext_resource id {ext.id!r}")
        else:
            seen_ids.add(ext.id)

    sub_ids: set[str] = set()
    for sub in scene.sub_resources:
        if sub.id is None:
            report.error("sub_resource has no id")
        elif sub.id in sub_ids:
            report.error(f"duplicate sub_resource id {sub.id!r}")
        else:
            sub_ids.add(sub.id)
        report.merge(validate_sub_resource(scene, sub, provider))

    for connection in scene.connections:
        for attr in ("signal", "from", "to", "method"):
            if attr not in connection.attributes:
                report.error(f"connection is missing the {attr!r} attribute")
        if connection.to_path is not None and scene.node(connection.to_path) is None:
            report.error(
                f"connection target {connection.to_path!r} does not exist",
                node_path=connection.to_path,
            )
        if connection.from_path is not None and connection.signal is not None:
            report.merge(
                validate_connection_signal(
                    scene, connection.from_path, connection.signal, provider
                )
            )
    return report
