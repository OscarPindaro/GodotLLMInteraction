"""Bridge between the tscn library and a generated Godot API specification.

A `SpecProvider` is built by scanning any version's generated pydantic
modules for models named `{GodotName}v{major}_{minor}[_{patch}]`. Nothing
here (or in validation.py) is specific to one Godot version: supporting a
new version means running `gli specifications generate-all --version vX_Y_Z`
and constructing a provider from the new modules.

`resolve_class` is deliberately the single seam for class-name resolution so
a future resolver for user-defined `class_name` scripts can be slotted in.
"""

from __future__ import annotations

import re
from functools import cache, lru_cache
from types import ModuleType
from typing import ForwardRef

from pydantic import BaseModel

_VERSION_SUFFIX_RE = re.compile(r"v\d+(?:_\d+){1,2}$")


def _scan_versioned_models(module: ModuleType) -> dict[str, type[BaseModel]]:
    """Godot name -> model for every version-suffixed model defined in `module`.

    Models merely imported into the module (classes.py imports the builtin
    models it references) are excluded by the __module__ check.
    """
    found: dict[str, type[BaseModel]] = {}
    for attr, obj in vars(module).items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj.__module__ == module.__name__
        ):
            match = _VERSION_SUFFIX_RE.search(attr)
            if match and match.start() > 0:
                found[attr[: match.start()]] = obj
    return found


# How many scalars each builtin flattens to in the constructor form Godot
# writes to .tscn files (Rect2(x, y, w, h), Transform2D(6 floats), ...).
# This is a property of the *serialization format*, not of the API version —
# the generated models can't provide it because their `members` include
# derived accessors (Color.r8/h/s/v, Rect2.end) that aren't constructor
# arguments. Unknown builtins fall back to counting model scalar leaves.
_SERIALIZED_SCALAR_WIDTHS = {
    "Vector2": 2,
    "Vector2i": 2,
    "Vector3": 3,
    "Vector3i": 3,
    "Vector4": 4,
    "Vector4i": 4,
    "Rect2": 4,
    "Rect2i": 4,
    "Color": 4,
    "Quaternion": 4,
    "Plane": 4,
    "AABB": 6,
    "Transform2D": 6,
    "Basis": 9,
    "Transform3D": 12,
    "Projection": 16,
}


@lru_cache(maxsize=None)
def _scalar_leaf_count(model: type[BaseModel]) -> int:
    total = 0
    for field in model.model_fields.values():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            total += _scalar_leaf_count(annotation)
        else:
            total += 1
    return total


class SpecProvider:
    """Read-only view over one Godot version's generated specification."""

    def __init__(
        self,
        classes_module: ModuleType,
        builtins_module: ModuleType | None = None,
        signals_table: dict[str, dict] | None = None,
    ) -> None:
        self._classes = _scan_versioned_models(classes_module)
        self._builtins = (
            _scan_versioned_models(builtins_module) if builtins_module else {}
        )
        self._godot_name_by_model = {
            model: name
            for name, model in [*self._classes.items(), *self._builtins.items()]
        }
        self._signals = signals_table or {}

    def resolve_class(self, name: str) -> type[BaseModel] | None:
        """The engine-class model for a Godot class name, or None if unknown."""
        return self._classes.get(name)

    def resolve_builtin(self, name: str) -> type[BaseModel] | None:
        return self._builtins.get(name)

    def godot_name_of(self, model: type[BaseModel]) -> str | None:
        return self._godot_name_by_model.get(model)

    def is_subclass(self, child: str, parent: str) -> bool | None:
        """Whether Godot class `child` inherits from `parent`; None if either
        name is unknown. Inheritance is mirrored in the generated models'
        Python subclassing, so this is plain issubclass()."""
        child_model = self.resolve_class(child)
        parent_model = self.resolve_class(parent)
        if child_model is None or parent_model is None:
            return None
        return issubclass(child_model, parent_model)

    def scalar_width(self, builtin_model: type[BaseModel]) -> int:
        godot_name = self.godot_name_of(builtin_model)
        if godot_name in _SERIALIZED_SCALAR_WIDTHS:
            return _SERIALIZED_SCALAR_WIDTHS[godot_name]
        return _scalar_leaf_count(builtin_model)

    def resolve_annotation(self, annotation: object) -> object:
        """Resolve a generated model's field annotation to a concrete type.

        The generated modules use `from __future__ import annotations`, so
        cross-class references arrive as unresolved ForwardRef('Texture2Dv4_7_0')
        — mapped back to the model through the version-stripped name.
        """
        name: str | None = None
        if isinstance(annotation, ForwardRef):
            name = annotation.__forward_arg__
        elif isinstance(annotation, str):
            name = annotation
        if name is None:
            return annotation
        match = _VERSION_SUFFIX_RE.search(name)
        if match and match.start() > 0:
            name = name[: match.start()]
        return self.resolve_class(name) or self.resolve_builtin(name) or annotation

    def signals_of(self, class_name: str) -> dict[str, object] | None:
        """All signals (own + inherited) of a class; None if the class is unknown."""
        model = self.resolve_class(class_name)
        if model is None:
            return None
        signals: dict[str, object] = {}
        for base in reversed(model.__mro__):
            base_name = self._godot_name_by_model.get(base)
            if base_name is not None:
                signals.update(self._signals.get(base_name, {}))
        return signals


@cache
def default_provider() -> SpecProvider:
    """Provider for the checked-in v4_7_0 specification."""
    from godotllminteraction.specifications.v4_7_0 import (
        builtin_classes,
        classes,
        signals,
    )

    return SpecProvider(classes, builtin_classes, signals.SIGNALS)
