"""Typed model of Godot value literals as they appear in .tscn files.

Design goals, in priority order:

1. Byte-for-byte round-trip: parsing a literal and formatting it back must
   reproduce the source exactly. Tokens whose canonical rendering can differ
   from their source spelling (floats, strings, string names, node paths)
   carry a `raw` field holding the original slice; `raw` is only set when it
   differs from the canonical rendering, so programmatically-built values and
   already-canonical parses compare equal.
2. One shared entry point: `parse_value` is used by the file parser, the YAML
   ops layer, and future CLI commands, so LLMs write plain Godot literal
   syntax (`Vector2(1, 2)`, `&"name"`, ...) everywhere.

Constructor-style literals (`Vector2(...)`, `Color(...)`, `ExtResource("id")`,
flat `PackedVector2Array(...)`, ...) are all `GCall`; `NodePath("...")` and
its `^"..."` shorthand get their own `GNodePath` type since node paths need
semantic handling during rename/move operations.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from godotllminteraction.tscn.exceptions import ParseError


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class GBool(_FrozenModel):
    kind: Literal["bool"] = "bool"
    value: bool


class GInt(_FrozenModel):
    kind: Literal["int"] = "int"
    value: int


class GFloat(_FrozenModel):
    kind: Literal["float"] = "float"
    value: float
    raw: str | None = None

    model_config = ConfigDict(frozen=True, ser_json_inf_nan="strings")


class GString(_FrozenModel):
    kind: Literal["string"] = "string"
    value: str
    raw: str | None = None


class GStringName(_FrozenModel):
    kind: Literal["string_name"] = "string_name"
    value: str
    raw: str | None = None


class GNodePath(_FrozenModel):
    kind: Literal["node_path"] = "node_path"
    value: str
    raw: str | None = None


class GNull(_FrozenModel):
    kind: Literal["null"] = "null"


class GCall(_FrozenModel):
    kind: Literal["call"] = "call"
    name: str
    args: tuple[GodotValue, ...] = ()
    # Typed containers spell an element type in brackets before the argument
    # list: Array[int]([...]), Array[ExtResource("id")]([...]),
    # Dictionary[String, int]({...}). Kept as the verbatim source slice since
    # type parameters aren't values (bare identifiers are legal there).
    type_params: str | None = None


class GArray(_FrozenModel):
    kind: Literal["array"] = "array"
    items: tuple[GodotValue, ...] = ()


class GDict(_FrozenModel):
    kind: Literal["dict"] = "dict"
    entries: tuple[tuple[GodotValue, GodotValue], ...] = ()


GodotValue = Annotated[
    Union[
        GBool,
        GInt,
        GFloat,
        GString,
        GStringName,
        GNodePath,
        GNull,
        GCall,
        GArray,
        GDict,
    ],
    Field(discriminator="kind"),
]

GCall.model_rebuild()
GArray.model_rebuild()
GDict.model_rebuild()


def is_ext_resource_ref(value: object) -> bool:
    return isinstance(value, GCall) and value.name == "ExtResource"


def is_sub_resource_ref(value: object) -> bool:
    return isinstance(value, GCall) and value.name == "SubResource"


def resource_ref_id(value: GCall) -> str:
    """The id of an ExtResource("id")/SubResource("id") reference."""
    if len(value.args) != 1 or not isinstance(value.args[0], GString):
        raise ParseError(f"{value.name}(...) must have exactly one string argument")
    return value.args[0].value


def ext_resource_ref(resource_id: str) -> GCall:
    return GCall(name="ExtResource", args=(GString(value=resource_id),))


def sub_resource_ref(resource_id: str) -> GCall:
    return GCall(name="SubResource", args=(GString(value=resource_id),))


# --- Formatting -------------------------------------------------------------

_STRING_ESCAPES = {"\\": "\\\\", '"': '\\"'}


def _escape_string(value: str) -> str:
    # Godot writes strings with String::c_escape_multiline(): only backslash
    # and double quote are escaped; newlines/tabs are emitted literally.
    return "".join(_STRING_ESCAPES.get(ch, ch) for ch in value)


def _format_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    # repr() is the shortest exact representation; Godot accepts it as-is.
    return repr(value)


def format_value(value: GodotValue, *, canonical: bool = False) -> str:
    """Render a value in Godot's .tscn literal syntax.

    With canonical=True, `raw` spellings are ignored so two semantically equal
    values format identically regardless of how they were originally written.
    """

    def fmt(v: GodotValue) -> str:
        return format_value(v, canonical=canonical)

    match value:
        case GBool():
            return "true" if value.value else "false"
        case GInt():
            return str(value.value)
        case GFloat():
            if value.raw is not None and not canonical:
                return value.raw
            return _format_float(value.value)
        case GString():
            if value.raw is not None and not canonical:
                return value.raw
            return f'"{_escape_string(value.value)}"'
        case GStringName():
            if value.raw is not None and not canonical:
                return value.raw
            return f'&"{_escape_string(value.value)}"'
        case GNodePath():
            if value.raw is not None and not canonical:
                return value.raw
            return f'NodePath("{_escape_string(value.value)}")'
        case GNull():
            return "null"
        case GCall():
            type_params = (
                f"[{value.type_params}]" if value.type_params is not None else ""
            )
            return f"{value.name}{type_params}({', '.join(fmt(a) for a in value.args)})"
        case GArray():
            return f"[{', '.join(fmt(i) for i in value.items)}]"
        case GDict():
            if not value.entries:
                return "{}"
            body = ",\n".join(f"{fmt(k)}: {fmt(v)}" for k, v in value.entries)
            return "{\n" + body + "\n}"
    raise TypeError(f"Not a GodotValue: {value!r}")


def values_equal(a: GodotValue, b: GodotValue) -> bool:
    """Semantic equality, ignoring `raw` source spellings."""
    return format_value(a, canonical=True) == format_value(b, canonical=True)


# --- Parsing ----------------------------------------------------------------

_NUMBER_RE = re.compile(
    r"[+-]?(?:\d+\.\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)"
)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WS_RE = re.compile(r"\s*")

_KEYWORD_VALUES = {
    "true": GBool(value=True),
    "false": GBool(value=False),
    "null": GNull(),
    "nan": GFloat(value=math.nan, raw="nan"),
    "inf": GFloat(value=math.inf, raw="inf"),
    "inf_neg": GFloat(value=-math.inf, raw="inf_neg"),
}

_SIMPLE_UNESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "'": "'",
    '"': '"',
    "\\": "\\",
}


class ValueReader:
    """Recursive-descent reader for Godot literals over a text buffer.

    Exposed (rather than private) because the file parser reads property
    values in place from the middle of the document text.
    """

    def __init__(self, text: str, pos: int = 0) -> None:
        self.text = text
        self.pos = pos

    def error(self, message: str) -> ParseError:
        line = self.text.count("\n", 0, self.pos) + 1
        return ParseError(message, line=line)

    def skip_ws(self) -> None:
        self.pos = _WS_RE.match(self.text, self.pos).end()

    def at_end(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, token: str) -> None:
        if not self.text.startswith(token, self.pos):
            raise self.error(f"expected {token!r}, found {self.peek()!r}")
        self.pos += len(token)

    def read_value(self) -> GodotValue:
        self.skip_ws()
        ch = self.peek()
        if ch == "":
            raise self.error("unexpected end of input while reading a value")
        if ch == '"':
            return self._read_string_value()
        if ch == "&":
            self.pos += 1
            raw_start = self.pos - 1
            value, raw = self._read_quoted()
            token = self.text[raw_start : self.pos]
            canonical = f'&"{_escape_string(value)}"'
            return GStringName(value=value, raw=None if token == canonical else token)
        if ch == "^":
            self.pos += 1
            raw_start = self.pos - 1
            value, _ = self._read_quoted()
            # ^"..." is GDScript shorthand; canonical .tscn form is
            # NodePath("..."), so the shorthand always keeps its raw spelling.
            return GNodePath(value=value, raw=self.text[raw_start : self.pos])
        if ch == "[":
            return self._read_array()
        if ch == "{":
            return self._read_dict()
        if ch in "+-.0123456789":
            keyword = self._try_signed_keyword()
            if keyword is not None:
                return keyword
            return self._read_number()
        if _IDENT_RE.match(self.text, self.pos):
            return self._read_ident_value()
        raise self.error(f"unexpected character {ch!r} while reading a value")

    def _read_string_value(self) -> GString:
        raw_start = self.pos
        value, _ = self._read_quoted()
        token = self.text[raw_start : self.pos]
        canonical = f'"{_escape_string(value)}"'
        return GString(value=value, raw=None if token == canonical else token)

    def _read_quoted(self) -> tuple[str, str]:
        """Read a double-quoted string at pos; returns (decoded, source_slice)."""
        start = self.pos
        self.expect('"')
        out: list[str] = []
        while True:
            if self.at_end():
                self.pos = start
                raise self.error("unterminated string")
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1
                return "".join(out), self.text[start : self.pos]
            if ch == "\\":
                self.pos += 1
                if self.at_end():
                    self.pos = start
                    raise self.error("unterminated escape sequence in string")
                esc = self.text[self.pos]
                if esc == "u":
                    hex_digits = self.text[self.pos + 1 : self.pos + 5]
                    if len(hex_digits) != 4:
                        raise self.error("truncated \\u escape in string")
                    try:
                        out.append(chr(int(hex_digits, 16)))
                    except ValueError:
                        raise self.error(
                            f"invalid \\u escape {hex_digits!r} in string"
                        ) from None
                    self.pos += 5
                elif esc in _SIMPLE_UNESCAPES:
                    out.append(_SIMPLE_UNESCAPES[esc])
                    self.pos += 1
                else:
                    # Unknown escape: Godot's parser keeps the character as-is.
                    out.append(esc)
                    self.pos += 1
            else:
                out.append(ch)
                self.pos += 1

    def _try_signed_keyword(self) -> GFloat | None:
        """Handle '-inf' / '+inf' (and signed nan, harmlessly)."""
        match = re.match(r"([+-])(inf_neg|inf|nan)\b", self.text[self.pos :])
        if match is None:
            return None
        sign, name = match.groups()
        base = _KEYWORD_VALUES[name].value
        token = self.text[self.pos : self.pos + match.end()]
        self.pos += match.end()
        return GFloat(value=-base if sign == "-" else base, raw=token)

    def _read_number(self) -> GInt | GFloat:
        match = _NUMBER_RE.match(self.text, self.pos)
        if match is None:
            raise self.error(
                f"invalid number at {self.text[self.pos : self.pos + 10]!r}"
            )
        token = match.group()
        self.pos = match.end()
        if any(c in token for c in ".eE"):
            value = float(token)
            return GFloat(
                value=value, raw=None if _format_float(value) == token else token
            )
        return GInt(value=int(token))

    def _read_ident_value(self) -> GodotValue:
        match = _IDENT_RE.match(self.text, self.pos)
        name = match.group()
        if name in _KEYWORD_VALUES:
            self.pos = match.end()
            return _KEYWORD_VALUES[name]
        self.pos = match.end()
        type_params = self._read_type_params() if self.peek() == "[" else None
        self.skip_ws()
        if self.peek() != "(":
            raise self.error(f"unexpected identifier {name!r} while reading a value")
        args = self._read_call_args()
        if type_params is not None:
            return GCall(name=name, args=tuple(args), type_params=type_params)
        if name == "NodePath":
            if len(args) != 1 or not isinstance(args[0], GString):
                raise self.error("NodePath(...) must have exactly one string argument")
            return GNodePath(value=args[0].value)
        return GCall(name=name, args=tuple(args))

    def _read_type_params(self) -> str:
        """Read a balanced [...] type-parameter list; returns the inner slice.

        Type parameters aren't values (bare identifiers like `int` are legal),
        so the content is captured verbatim, tracking bracket nesting and
        skipping over quoted strings.
        """
        start = self.pos
        self.expect("[")
        depth = 1
        while depth > 0:
            if self.at_end():
                self.pos = start
                raise self.error("unterminated '[' in type parameters")
            ch = self.text[self.pos]
            if ch == '"':
                self._read_quoted()
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            self.pos += 1
        return self.text[start + 1 : self.pos - 1]

    def _read_call_args(self) -> list[GodotValue]:
        self.expect("(")
        args: list[GodotValue] = []
        self.skip_ws()
        if self.peek() == ")":
            self.pos += 1
            return args
        while True:
            args.append(self.read_value())
            self.skip_ws()
            if self.peek() == ",":
                self.pos += 1
                continue
            self.expect(")")
            return args

    def _read_array(self) -> GArray:
        self.expect("[")
        items: list[GodotValue] = []
        self.skip_ws()
        if self.peek() == "]":
            self.pos += 1
            return GArray(items=())
        while True:
            items.append(self.read_value())
            self.skip_ws()
            if self.peek() == ",":
                self.pos += 1
                self.skip_ws()
                continue
            self.expect("]")
            return GArray(items=tuple(items))

    def _read_dict(self) -> GDict:
        self.expect("{")
        entries: list[tuple[GodotValue, GodotValue]] = []
        self.skip_ws()
        if self.peek() == "}":
            self.pos += 1
            return GDict(entries=())
        while True:
            key = self.read_value()
            self.skip_ws()
            self.expect(":")
            value = self.read_value()
            entries.append((key, value))
            self.skip_ws()
            if self.peek() == ",":
                self.pos += 1
                self.skip_ws()
                continue
            self.expect("}")
            return GDict(entries=tuple(entries))


def parse_value(text: str) -> GodotValue:
    """Parse a complete Godot literal; the whole string must be consumed."""
    reader = ValueReader(text)
    value = reader.read_value()
    reader.skip_ws()
    if not reader.at_end():
        raise reader.error(
            f"trailing characters after value: {text[reader.pos : reader.pos + 20]!r}"
        )
    return value
