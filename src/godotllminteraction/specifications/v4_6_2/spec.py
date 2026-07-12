"""Auto-generated spec for Godot v4_6_2. Do not edit by hand."""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from godotllminteraction.specifications.shared.spec import (
    BuiltinClass,
    BuiltinClassArgument,
    BuiltinClassConstructor,
    BuiltinClassConstant,
    BuiltinClassEnum,
    BuiltinClassMember,
    BuiltinClassMemberOffsets,
    BuiltinClassMethod,
    BuiltinClassOperator,
    BuiltinClassSizeType,
    BuiltinClassesList,
    ClassConstant,
    ClassMember,
    ClassMemeberOffset,
    ClassMethod,
    ClassMethodArgument,
    ClassMethodReturnValue,
    ClassProperty,
    ClassSignal,
    ClassSignalArgument,
    ClassSize,
    ClassesList,
    GlobalConstant,
    GlobalConstantsList,
    GlobalEnumsList,
    GodotClass,
    GodotEnum,
    GodotEnumValues,
    Header,
    NativeStructure,
    NativeStructuresList,
    Singleton,
    SingletonsList,
    UtilityFunction,
    UtilityFunctionArgument,
    UtilityFunctionsList,
)


# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums --version v4_6_2) ===
class GodotTypeNameEnum(str, Enum):
    """Name of a Godot variant/builtin type, as it shows up across return types, argument types, etc."""

    AABB = "AABB"
    ARRAY = "Array"
    BASIS = "Basis"
    CALLABLE = "Callable"
    COLOR = "Color"
    DICTIONARY = "Dictionary"
    NODE_PATH = "NodePath"
    OBJECT = "Object"
    PACKED_BYTE_ARRAY = "PackedByteArray"
    PACKED_COLOR_ARRAY = "PackedColorArray"
    PACKED_FLOAT32_ARRAY = "PackedFloat32Array"
    PACKED_FLOAT64_ARRAY = "PackedFloat64Array"
    PACKED_INT32_ARRAY = "PackedInt32Array"
    PACKED_INT64_ARRAY = "PackedInt64Array"
    PACKED_STRING_ARRAY = "PackedStringArray"
    PACKED_VECTOR2_ARRAY = "PackedVector2Array"
    PACKED_VECTOR3_ARRAY = "PackedVector3Array"
    PACKED_VECTOR4_ARRAY = "PackedVector4Array"
    PLANE = "Plane"
    PROJECTION = "Projection"
    QUATERNION = "Quaternion"
    RID = "RID"
    RECT2 = "Rect2"
    RECT2I = "Rect2i"
    SIGNAL = "Signal"
    STRING = "String"
    STRING_NAME = "StringName"
    TRANSFORM2D = "Transform2D"
    TRANSFORM3D = "Transform3D"
    VARIANT = "Variant"
    VECTOR2 = "Vector2"
    VECTOR2I = "Vector2i"
    VECTOR3 = "Vector3"
    VECTOR3I = "Vector3i"
    VECTOR4 = "Vector4"
    VECTOR4I = "Vector4i"
    BOOL = "bool"
    FLOAT = "float"
    INT = "int"


GodotTypeName = Union[GodotTypeNameEnum, str]
# === END GENERATED: GodotTypeNameEnum ===

UtilityFunctionReturnType = GodotTypeName

# === GENERATED: UtilityFunctionCategoryEnum (run: gli specifications sync-enums --version v4_6_2) ===
class UtilityFunctionCategoryEnum(str, Enum):
    GENERAL = "general"
    MATH = "math"
    RANDOM = "random"


UtilityFunctionCategory = Union[UtilityFunctionCategoryEnum, str]
# === END GENERATED: UtilityFunctionCategoryEnum ===

# === GENERATED: BuiltinClassOperatorNameEnum (run: gli specifications sync-enums --version v4_6_2) ===
class BuiltinClassOperatorNameEnum(str, Enum):
    NOT_EQUAL = "!="
    MODULO = "%"
    BIT_AND = "&"
    MULTIPLY = "*"
    POWER = "**"
    ADD = "+"
    SUBTRACT = "-"
    DIVIDE = "/"
    LESS = "<"
    SHIFT_LEFT = "<<"
    LESS_EQUAL = "<="
    EQUAL = "=="
    GREATER = ">"
    GREATER_EQUAL = ">="
    SHIFT_RIGHT = ">>"
    BIT_XOR = "^"
    AND = "and"
    IN = "in"
    NOT = "not"
    OR = "or"
    UNARY_PLUS = "unary+"
    UNARY_MINUS = "unary-"
    XOR = "xor"
    BIT_OR = "|"
    BIT_NOT = "~"


BuiltinClassOperatorName = Union[BuiltinClassOperatorNameEnum, str]
# === END GENERATED: BuiltinClassOperatorNameEnum ===

# === GENERATED: ClassApiTypeEnum (run: gli specifications sync-enums --version v4_6_2) ===
class ClassApiTypeEnum(str, Enum):
    CORE = "core"
    EDITOR = "editor"


ClassApiType = Union[ClassApiTypeEnum, str]
# === END GENERATED: ClassApiTypeEnum ===

from godotllminteraction.specifications.v4_6_0.spec import (
    GodotArgumentMetaEnum,
    GodotArgumentMeta,
)


class Specification4_6_2(BaseModel):
    """Full Godot v4_6_2 GDExtension API dump, mirroring the top-level sections of extension_api.json."""

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
