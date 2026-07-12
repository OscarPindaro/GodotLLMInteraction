from __future__ import annotations

import math

import pytest

from godotllminteraction.tscn.exceptions import ParseError
from godotllminteraction.tscn.values import (
    GArray,
    GBool,
    GCall,
    GDict,
    GFloat,
    GInt,
    GNodePath,
    GNull,
    GString,
    GStringName,
    ext_resource_ref,
    format_value,
    is_ext_resource_ref,
    is_sub_resource_ref,
    parse_value,
    resource_ref_id,
    sub_resource_ref,
    values_equal,
)

pytestmark = [pytest.mark.tscn]


def roundtrip(text: str) -> str:
    return format_value(parse_value(text))


class TestScalars:
    def test_bool(self):
        assert parse_value("true") == GBool(value=True)
        assert parse_value("false") == GBool(value=False)
        assert roundtrip("true") == "true"

    def test_null(self):
        assert parse_value("null") == GNull()
        assert roundtrip("null") == "null"

    def test_int(self):
        assert parse_value("42") == GInt(value=42)
        assert parse_value("-5") == GInt(value=-5)
        assert roundtrip("725077531") == "725077531"

    def test_float_simple(self):
        value = parse_value("1.5")
        assert isinstance(value, GFloat)
        assert value.value == 1.5
        assert roundtrip("1.5") == "1.5"

    def test_float_exponent_preserves_raw_spelling(self):
        assert roundtrip("-5.72205e-06") == "-5.72205e-06"
        assert roundtrip("1.19209e-07") == "1.19209e-07"
        assert roundtrip("1e+20") == "1e+20"

    def test_float_trailing_zero_spelling_preserved(self):
        assert roundtrip("299.0") == "299.0"
        assert roundtrip("1.0") == "1.0"

    def test_float_special_values(self):
        assert math.isinf(parse_value("inf").value)
        assert parse_value("-inf").value == -math.inf
        assert math.isnan(parse_value("nan").value)
        assert roundtrip("inf") == "inf"
        assert roundtrip("-inf") == "-inf"

    def test_programmatic_float_formats_shortest(self):
        assert format_value(GFloat(value=1.0)) == "1.0"
        assert format_value(GFloat(value=0.1)) == "0.1"


class TestStrings:
    def test_plain(self):
        assert parse_value('"hello"') == GString(value="hello")
        assert roundtrip('"hello"') == '"hello"'

    def test_escaped_quote_and_backslash(self):
        assert parse_value('"a \\"b\\" c"').value == 'a "b" c'
        assert parse_value('"back\\\\slash"').value == "back\\slash"
        assert roundtrip('"a \\"b\\" c"') == '"a \\"b\\" c"'

    def test_literal_newline_and_tab_inside_string(self):
        text = '"line one\nline two\ttabbed"'
        assert parse_value(text).value == "line one\nline two\ttabbed"
        assert roundtrip(text) == text

    def test_decoded_escape_keeps_raw_spelling(self):
        # \n is decoded, but the canonical writer emits literal newlines, so
        # the original spelling must be kept for byte round-trips.
        assert parse_value('"a\\nb"').value == "a\nb"
        assert roundtrip('"a\\nb"') == '"a\\nb"'

    def test_unicode_escape(self):
        assert parse_value('"\\u00e9"').value == "é"

    def test_programmatic_string_escapes_only_quote_and_backslash(self):
        assert format_value(GString(value='say "hi"\nnow')) == '"say \\"hi\\"\nnow"'

    def test_unterminated_string_raises(self):
        with pytest.raises(ParseError):
            parse_value('"never ends')

    def test_string_name(self):
        assert parse_value('&"default"') == GStringName(value="default")
        assert roundtrip('&"default"') == '&"default"'
        assert format_value(GStringName(value="x")) == '&"x"'


class TestNodePaths:
    def test_node_path_call_form(self):
        value = parse_value('NodePath("../PlateArea")')
        assert value == GNodePath(value="../PlateArea")
        assert roundtrip('NodePath("../PlateArea")') == 'NodePath("../PlateArea")'

    def test_node_path_caret_shorthand_preserves_spelling(self):
        value = parse_value('^"Player/Sprite"')
        assert isinstance(value, GNodePath)
        assert value.value == "Player/Sprite"
        assert roundtrip('^"Player/Sprite"') == '^"Player/Sprite"'

    def test_programmatic_node_path_uses_call_form(self):
        assert format_value(GNodePath(value="A/B")) == 'NodePath("A/B")'


class TestCalls:
    def test_vector2(self):
        value = parse_value("Vector2(10, 20)")
        assert value == GCall(name="Vector2", args=(GInt(value=10), GInt(value=20)))
        assert roundtrip("Vector2(10, 20)") == "Vector2(10, 20)"

    def test_color(self):
        assert roundtrip("Color(1, 0.5, 0.25, 1)") == "Color(1, 0.5, 0.25, 1)"

    def test_flat_packed_vector2_array(self):
        value = parse_value("PackedVector2Array(10, 0, 0, 20, 70, 30)")
        assert isinstance(value, GCall)
        assert len(value.args) == 6
        assert (
            roundtrip("PackedVector2Array(10, 0, 0, 20, 70, 30)")
            == "PackedVector2Array(10, 0, 0, 20, 70, 30)"
        )

    def test_packed_string_array_with_escapes(self):
        text = 'PackedStringArray("a", "b c", "d\\"e\\"")'
        assert roundtrip(text) == text

    def test_empty_call(self):
        assert parse_value("PackedStringArray()") == GCall(name="PackedStringArray")
        assert roundtrip("PackedStringArray()") == "PackedStringArray()"

    def test_ext_and_sub_resource_refs(self):
        ext = parse_value('ExtResource("1_tilemap")')
        sub = parse_value('SubResource("RectangleShape2D_c63hm")')
        assert is_ext_resource_ref(ext) and not is_sub_resource_ref(ext)
        assert is_sub_resource_ref(sub) and not is_ext_resource_ref(sub)
        assert resource_ref_id(ext) == "1_tilemap"
        assert resource_ref_id(sub) == "RectangleShape2D_c63hm"
        assert format_value(ext_resource_ref("1_tilemap")) == 'ExtResource("1_tilemap")'
        assert format_value(sub_resource_ref("Shape_x")) == 'SubResource("Shape_x")'

    def test_typed_array_with_script_element_type(self):
        # Godot 4 typed arrays: Array[ElementType]([items]) — the element
        # type can be a bare identifier or an ExtResource(...) script ref.
        text = 'Array[ExtResource("4_7r5rd")]([SubResource("Resource_q0ofn")])'
        value = parse_value(text)
        assert isinstance(value, GCall)
        assert value.name == "Array"
        assert value.type_params == 'ExtResource("4_7r5rd")'
        assert roundtrip(text) == text
        assert roundtrip("Array[int]([1, 2])") == "Array[int]([1, 2])"

    def test_bare_identifier_raises(self):
        with pytest.raises(ParseError):
            parse_value("Vector2")


class TestContainers:
    def test_empty_array_and_dict(self):
        assert parse_value("[]") == GArray()
        assert parse_value("{}") == GDict()
        assert roundtrip("[]") == "[]"
        assert roundtrip("{}") == "{}"

    def test_inline_array(self):
        assert roundtrip("[1, 2, 3]") == "[1, 2, 3]"

    def test_dict_formats_multiline_godot_style(self):
        text = '{\n"alpha": 1,\n"beta": [true, false]\n}'
        assert roundtrip(text) == text

    def test_nested_dict_in_array_multiline(self):
        text = (
            '[{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_frame_0")\n}, {\n'
            '"duration": 1.0,\n"texture": SubResource("AtlasTexture_frame_1")\n}]'
        )
        assert roundtrip(text) == text

    def test_string_name_dict_key(self):
        text = '{\n&"gamma": Vector2(0, 0)\n}'
        assert roundtrip(text) == text

    def test_deep_nesting(self):
        text = '[1, "two", Vector2(3, 4), [5, 6], {\n"k": 7\n}]'
        assert roundtrip(text) == text


class TestParseErrors:
    def test_trailing_garbage_raises(self):
        with pytest.raises(ParseError, match="trailing"):
            parse_value("1 2")

    def test_empty_input_raises(self):
        with pytest.raises(ParseError):
            parse_value("")

    def test_unclosed_array_raises(self):
        with pytest.raises(ParseError):
            parse_value("[1, 2")

    def test_error_carries_line_number(self):
        with pytest.raises(ParseError, match="line 3"):
            parse_value('[1,\n2,\n"unterminated')


class TestValuesEqual:
    def test_same_value_different_spelling(self):
        assert values_equal(parse_value("1.50"), GFloat(value=1.5))
        assert values_equal(parse_value('"a\\nb"'), GString(value="a\nb"))

    def test_different_values(self):
        assert not values_equal(GInt(value=1), GInt(value=2))
        assert not values_equal(GInt(value=1), GFloat(value=1.0))
