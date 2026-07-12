"""Auto-generated spec for Godot v4_6_0. Do not edit by hand."""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import List, Union

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


# === GENERATED: GodotArgumentMetaEnum (run: gli specifications sync-enums --version v4_6_0) ===
class GodotArgumentMetaEnum(str, Enum):
    """Native C++ type refinement of an argument/return value, e.g. 'int64', 'double', 'uint8'."""

    CHAR32 = "char32"
    DOUBLE = "double"
    FLOAT = "float"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    INT8 = "int8"
    REQUIRED = "required"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    UINT8 = "uint8"


GodotArgumentMeta = Union[GodotArgumentMetaEnum, str]
# === END GENERATED: GodotArgumentMetaEnum ===


class Specification4_6_0(BaseModel):
    """Full Godot v4_6_0 GDExtension API dump, mirroring the top-level sections of extension_api.json."""

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
