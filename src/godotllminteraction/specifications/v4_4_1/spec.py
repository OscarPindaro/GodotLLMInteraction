"""Auto-generated spec for Godot v4_4_1. Do not edit by hand."""

from __future__ import annotations

from functools import cached_property
from typing import List

from pydantic import BaseModel, Field

from godotllminteraction.specifications.shared.spec import (
    BuiltinClassMemberOffsets,
    BuiltinClassSizeType,
    BuiltinClassesList,
    ClassesList,
    GlobalConstantsList,
    GlobalEnumsList,
    Header,
    NativeStructuresList,
    SingletonsList,
    UtilityFunctionsList,
)


class Specification4_4_1(BaseModel):
    """Full Godot v4_4_1 GDExtension API dump, mirroring the top-level sections of extension_api.json."""

    header: Header = Field(description="Engine version and build metadata")
    builtin_class_sizes: List[BuiltinClassSizeType] = Field(
        description="Byte sizes of builtin classes, per build configuration"
    )
    builtin_class_member_offsets: List[BuiltinClassMemberOffsets] = Field(
        description="Member offsets within builtin classes, per build configuration"
    )
    global_constants: GlobalConstantsList = Field(
        description="Engine-wide global constants"
    )
    global_enums: GlobalEnumsList = Field(description="Engine-wide global enums")
    utility_functions: UtilityFunctionsList = Field(
        description="Global utility functions (math, random, general)"
    )
    builtin_classes: BuiltinClassesList = Field(
        description="Builtin variant types such as Vector2, Color, Array"
    )
    classes: ClassesList = Field(
        description="Engine class hierarchy such as Object, Node, Resource"
    )
    singletons: SingletonsList = Field(
        description="Globally accessible singleton instances"
    )
    native_structures: NativeStructuresList = Field(
        description="Native C++ structs exposed to extensions"
    )

    @cached_property
    def class_names(self):
        return [cls.name for cls in self.classes]

    @cached_property
    def builtin_class_names(self):
        return [cls.name for cls in self.builtin_classes]
