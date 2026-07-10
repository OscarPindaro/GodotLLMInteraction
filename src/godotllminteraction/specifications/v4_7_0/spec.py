from pydantic import BaseModel, Field
from typing import List, Optional, Union
from functools import cached_property
from enum import Enum


# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums-v4-7-0) ===
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


# === GENERATED: UtilityFunctionCategoryEnum (run: gli specifications sync-enums-v4-7-0) ===
class UtilityFunctionCategoryEnum(str, Enum):
    GENERAL = "general"
    MATH = "math"
    RANDOM = "random"


UtilityFunctionCategory = Union[UtilityFunctionCategoryEnum, str]
# === END GENERATED: UtilityFunctionCategoryEnum ===


# === GENERATED: BuiltinClassOperatorNameEnum (run: gli specifications sync-enums-v4-7-0) ===
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


# === GENERATED: GodotArgumentMetaEnum (run: gli specifications sync-enums-v4-7-0) ===
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


# === GENERATED: ClassApiTypeEnum (run: gli specifications sync-enums-v4-7-0) ===
class ClassApiTypeEnum(str, Enum):
    CORE = "core"
    EDITOR = "editor"


ClassApiType = Union[ClassApiTypeEnum, str]
# === END GENERATED: ClassApiTypeEnum ===


class Header(BaseModel):
    version_major: int = Field(
        default=4, description="Major version number of the Godot engine"
    )
    version_minor: int = Field(
        default=7, description="Minor version number of the Godot engine"
    )
    version_patch: int = Field(
        default=0, description="Patch version number of the Godot engine"
    )
    version_status: str = Field(
        default="stable", description="Release status of the Godot engine"
    )
    version_build: str = Field(
        default="official", description="Build type of the Godot engine"
    )
    version_full_name: str = Field(
        default="Godot Engine v4.7.stable.official",
        description="Full human-readable version string",
    )
    precision: str = Field(
        default="single", description="Floating point precision used by the engine"
    )


class ClassSize(BaseModel):
    name: str
    size: int


class BuiltinClassSizeType(BaseModel):
    """API extension in general has multiple class sizes, depending on the build_configuration field"""

    build_configuration: str = Field(
        default="float_32", description="Floating point precision used by the engine"
    )
    sizes: list[ClassSize] = Field(default=[], description="List of class sizes")


class ClassMember(BaseModel):
    member: str = Field(description="Name of the attribute, e.g. 'x' for Vector2.x")
    offset: int = Field(
        description="Byte offset of the member within the containing struct"
    )
    meta: str = Field(
        description="Underlying primitive type of the member, e.g. 'float', 'int'"
    )


class ClassMemeberOffset(BaseModel):
    name: str = Field(
        description="Name of the builtin class the members belong to, e.g. 'Vector2'"
    )
    members: List[ClassMember] = Field(description="Member offsets of the class")

    @cached_property
    def n_members(self):
        return len(self.members)

    @cached_property
    def member_names(self):
        return [member.member for member in self.members]


class BuiltinClassMemberOffsets(BaseModel):
    """API extension in general has multiple member offsets, depending on the build_configuration field.
    build_configuration should be one of float_32, float_64, double_32, double_64.
    """

    build_configuration: str = Field(
        default="float_32", description="Floating point precision used by the engine"
    )
    classes: list[ClassMemeberOffset] = Field(
        default=[], description="Per-class member offsets for this build configuration"
    )


class GlobalConstant(BaseModel):
    name: str = Field(description="Name of the global constant")
    value: int = Field(description="Integer value of the constant")
    is_bitfield: bool = Field(description="Whether the constant is a bitfield flag")


GlobalConstantsList = List[GlobalConstant]


class GodotEnumValues(BaseModel):
    name: str = Field(description="Name of the enum value")
    value: int = Field(description="Integer value assigned to the enum member")


class GodotEnum(BaseModel):
    name: str = Field(description="Name of the enum")
    is_bitfield: bool = Field(description="Whether the enum is a bitfield (flags) enum")
    values: List[GodotEnumValues] = Field(
        description="List of values belonging to the enum"
    )


class UtilityFunctionArgument(BaseModel):
    name: str = Field(description="Parameter name")
    type: str = Field(description="Godot variant type name of the parameter")


class UtilityFunction(BaseModel):
    name: str = Field(description="Name of the utility function, e.g. 'sin'")
    return_type: Optional[UtilityFunctionReturnType] = Field(
        default=None,
        description="Return type name; absent for void-like functions such as print/push_error",
    )
    category: UtilityFunctionCategory = Field(
        description="Grouping of the function: 'math', 'general', or 'random'"
    )
    is_vararg: bool = Field(
        description="Whether the function accepts a variable number of arguments"
    )
    hash: int = Field(
        description="Godot's hash of the function signature, used for binary API compatibility checks"
    )
    arguments: List[UtilityFunctionArgument] = Field(
        default=[],
        description="Parameters of the function; empty when the function takes none",
    )


UtilityFunctionsList = List[UtilityFunction]


class BuiltinClassOperator(BaseModel):
    name: BuiltinClassOperatorName = Field(
        description="Operator symbol or keyword, e.g. '==', 'unary-', 'and'"
    )
    right_type: Optional[GodotTypeName] = Field(
        default=None,
        description="Type of the right-hand operand; absent for unary operators",
    )
    return_type: GodotTypeName = Field(
        description="Result type of applying the operator"
    )


class BuiltinClassArgument(BaseModel):
    name: str = Field(description="Parameter name")
    type: GodotTypeName = Field(description="Godot type name of the parameter")
    default_value: Optional[str] = Field(
        default=None,
        description="Stringified default value expression, if the parameter is optional",
    )


class BuiltinClassConstructor(BaseModel):
    index: int = Field(
        description="Position of this overload among the class's constructors"
    )
    arguments: List[BuiltinClassArgument] = Field(
        default=[],
        description="Parameters of this constructor overload; empty for the default constructor",
    )


class BuiltinClassMethod(BaseModel):
    name: str = Field(description="Name of the method")
    return_type: Optional[GodotTypeName] = Field(
        default=None, description="Return type of the method; absent for void methods"
    )
    is_vararg: bool = Field(
        description="Whether the method accepts a variable number of arguments"
    )
    is_const: bool = Field(
        description="Whether the method leaves the instance unmodified"
    )
    is_static: bool = Field(
        description="Whether the method is a static/class-level method"
    )
    hash: int = Field(
        description="Godot's hash of the method signature, used for binary API compatibility checks"
    )
    hash_compatibility: Optional[List[int]] = Field(
        default=None,
        description="Older signature hashes still accepted for ABI compatibility",
    )
    arguments: List[BuiltinClassArgument] = Field(
        default=[],
        description="Parameters of the method; empty when the method takes none",
    )


class BuiltinClassConstant(BaseModel):
    name: str = Field(description="Name of the constant")
    type: GodotTypeName = Field(description="Type of the constant")
    value: str = Field(
        description="Stringified expression producing the constant's value, e.g. 'Vector2(0, 0)'"
    )


class BuiltinClassEnum(BaseModel):
    name: str = Field(description="Name of the enum nested in the builtin class")
    values: List[GodotEnumValues] = Field(
        description="List of values belonging to the enum"
    )


class BuiltinClassMember(BaseModel):
    name: str = Field(description="Name of the member field, e.g. 'x' for Vector2.x")
    type: GodotTypeName = Field(description="Type of the member field")


class BuiltinClass(BaseModel):
    name: str = Field(description="Name of the builtin class, e.g. 'Vector2'")
    is_keyed: bool = Field(
        description="Whether the type supports keyed indexing, like a dictionary"
    )
    indexing_return_type: Optional[GodotTypeName] = Field(
        default=None,
        description="Element type returned by the `[]` operator; absent if the type isn't indexable",
    )
    operators: List[BuiltinClassOperator] = Field(
        default=[], description="Operators supported by the type"
    )
    constructors: List[BuiltinClassConstructor] = Field(
        default=[], description="Available constructor overloads"
    )
    has_destructor: bool = Field(
        description="Whether the type has an explicit destructor"
    )
    methods: List[BuiltinClassMethod] = Field(
        default=[], description="Methods defined on the type"
    )
    members: List[BuiltinClassMember] = Field(
        default=[], description="Data members (fields) of the type"
    )
    constants: List[BuiltinClassConstant] = Field(
        default=[], description="Named constants defined on the type"
    )
    enums: List[BuiltinClassEnum] = Field(
        default=[], description="Enums nested in the type"
    )

    @cached_property
    def operator_names(self):
        return [op.name for op in self.operators]


BuiltinClassesList = List[BuiltinClass]


class Singleton(BaseModel):
    name: str = Field(
        description="Name of the singleton/autoload accessor, e.g. 'Performance'"
    )
    type: str = Field(
        description="Name of the class this singleton is an instance of (matches `name` in practice)"
    )


SingletonsList = List[Singleton]


class NativeStructure(BaseModel):
    name: str = Field(description="Name of the native (C++) struct, e.g. 'AudioFrame'")
    format: str = Field(
        description="Raw C++ member-list declaration, semicolon-separated (e.g. 'float left;float right'); not further parsed since it uses C types/pointers/array sizes/default values outside the GodotTypeName domain"
    )


NativeStructuresList = List[NativeStructure]


class ClassProperty(BaseModel):
    type: GodotTypeName = Field(description="Type of the property")
    name: str = Field(description="Name of the property")
    setter: Optional[str] = Field(
        default=None,
        description="Name of the setter method; absent for read-only properties",
    )
    getter: str = Field(description="Name of the getter method")
    index: Optional[int] = Field(
        default=None,
        description="Index passed to the getter/setter for indexed properties (e.g. array-backed properties)",
    )


class ClassSignalArgument(BaseModel):
    name: str = Field(description="Parameter name")
    type: GodotTypeName = Field(description="Godot type name of the parameter")


class ClassSignal(BaseModel):
    name: str = Field(description="Name of the signal")
    arguments: List[ClassSignalArgument] = Field(
        default=[],
        description="Parameters passed to the signal; empty when the signal takes none",
    )


class ClassConstant(BaseModel):
    name: str = Field(description="Name of the constant")
    value: int = Field(description="Integer value of the constant")


class ClassMethodArgument(BaseModel):
    name: str = Field(description="Parameter name")
    type: GodotTypeName = Field(description="Godot type name of the parameter")
    meta: Optional[GodotArgumentMeta] = Field(
        default=None,
        description="Native C++ type refinement of the parameter, e.g. 'int64', 'double'",
    )
    default_value: Optional[str] = Field(
        default=None,
        description="Stringified default value expression, if the parameter is optional",
    )


class ClassMethodReturnValue(BaseModel):
    type: GodotTypeName = Field(description="Return type of the method")
    meta: Optional[GodotArgumentMeta] = Field(
        default=None,
        description="Native C++ type refinement of the return value, e.g. 'int64', 'double'",
    )


class ClassMethod(BaseModel):
    name: str = Field(description="Name of the method")
    is_const: bool = Field(
        description="Whether the method leaves the instance unmodified"
    )
    is_vararg: bool = Field(
        description="Whether the method accepts a variable number of arguments"
    )
    is_static: bool = Field(
        description="Whether the method is a static/class-level method"
    )
    is_virtual: bool = Field(
        description="Whether the method is a virtual method meant to be overridden"
    )
    is_required: Optional[bool] = Field(
        default=None,
        description="Whether overriding this virtual method is required; only set when is_virtual is true",
    )
    hash: int = Field(
        description="Godot's hash of the method signature, used for binary API compatibility checks"
    )
    hash_compatibility: Optional[List[int]] = Field(
        default=None,
        description="Older signature hashes still accepted for ABI compatibility",
    )
    arguments: List[ClassMethodArgument] = Field(
        default=[],
        description="Parameters of the method; empty when the method takes none",
    )
    return_value: Optional[ClassMethodReturnValue] = Field(
        default=None, description="Return value of the method; absent for void methods"
    )


class GodotClass(BaseModel):
    name: str = Field(description="Name of the class, e.g. 'Node'")
    is_refcounted: bool = Field(
        description="Whether instances are managed via reference counting"
    )
    is_instantiable: bool = Field(
        description="Whether the class can be instantiated directly"
    )
    api_type: ClassApiType = Field(
        description="Which API surface the class belongs to: 'core' or 'editor'"
    )
    inherits: Optional[str] = Field(
        default=None,
        description="Name of the parent class; absent only for 'Object', the root of the hierarchy",
    )
    methods: List[ClassMethod] = Field(
        default=[], description="Methods defined on the class"
    )
    properties: List[ClassProperty] = Field(
        default=[], description="Properties exposed by the class"
    )
    enums: List[GodotEnum] = Field(default=[], description="Enums nested in the class")
    signals: List[ClassSignal] = Field(
        default=[], description="Signals emitted by the class"
    )
    constants: List[ClassConstant] = Field(
        default=[], description="Named constants defined on the class"
    )

    @cached_property
    def method_names(self):
        return [method.name for method in self.methods]


ClassesList = List[GodotClass]

GlobalEnumsList = List[GodotEnum]


class Specification4_7(BaseModel):
    """Full Godot 4.7 GDExtension API dump, mirroring the top-level sections of extension_api.json."""

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
