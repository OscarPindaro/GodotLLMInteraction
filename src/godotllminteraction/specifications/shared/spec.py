"""Shared pydantic models for Godot extension_api.json, common to all 4.x versions.

Version-specific enums (GodotTypeNameEnum, etc.) and the Specification class
are defined in each version's ``spec.py`` module. This module provides the
reusable sub-models that every version's Specification composes.

Type aliases like ``GodotTypeName`` are ``str`` here — each version's
``spec.py`` redefines them as ``Union[GodotTypeNameEnum, str]`` for
documentation and IDE support, but pydantic validation accepts any string
either way.
"""

from __future__ import annotations

from functools import cached_property
from typing import List, Optional

from pydantic import BaseModel, Field

# --- Type aliases (overridden per-version with generated enums) -------------

GodotTypeName = str
UtilityFunctionReturnType = GodotTypeName
UtilityFunctionCategory = str
BuiltinClassOperatorName = str
GodotArgumentMeta = str
ClassApiType = str


# --- Shared model classes ---------------------------------------------------


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
