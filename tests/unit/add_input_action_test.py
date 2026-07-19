"""Unit tests for the add_input_action MCP tool (binding parsing + serialization)."""

from __future__ import annotations


import pytest

from godotllminteraction.mcp.tools.project import (
    _add_or_replace_action,
    _build_action_block,
    _key_name_to_enum_name,
    _parse_binding,
    InputEventKeyDescriptor,
    InputEventMouseButtonDescriptor,
    InputEventJoypadButtonDescriptor,
)

pytestmark = [pytest.mark.unit]


# --- Key name conversion ----------------------------------------------------


class TestKeyNameToEnumName:
    def test_single_letter(self):
        assert _key_name_to_enum_name("A") == "KEY_A"

    def test_word(self):
        assert _key_name_to_enum_name("Space") == "KEY_SPACE"

    def test_already_prefixed(self):
        assert _key_name_to_enum_name("KEY_A") == "KEY_A"

    def test_mixed_case(self):
        assert _key_name_to_enum_name("Left") == "KEY_LEFT"

    def test_f_key(self):
        assert _key_name_to_enum_name("F1") == "KEY_F1"


# --- Binding parsing --------------------------------------------------------


@pytest.fixture
def enums():
    from godotllminteraction.specifications.v4_7_0 import global_enums as mod

    return mod


class TestParseKeyBinding:
    def test_simple_key(self, enums):
        event = _parse_binding("A", enums)
        assert isinstance(event, InputEventKeyDescriptor)
        assert event.physical_keycode == 65
        assert event.unicode == 97  # lowercase 'a'
        assert event.modifiers.ctrl_pressed is False

    def test_key_with_ctrl(self, enums):
        event = _parse_binding("ctrl+A", enums)
        assert event.modifiers.ctrl_pressed is True
        assert event.modifiers.alt_pressed is False
        assert event.physical_keycode == 65

    def test_key_with_multiple_modifiers(self, enums):
        event = _parse_binding("ctrl+alt+shift+A", enums)
        assert event.modifiers.ctrl_pressed is True
        assert event.modifiers.alt_pressed is True
        assert event.modifiers.shift_pressed is True

    def test_arrow_key(self, enums):
        event = _parse_binding("Left", enums)
        assert event.physical_keycode == 4194319
        assert event.unicode == 0  # non-printable

    def test_space_key(self, enums):
        event = _parse_binding("Space", enums)
        assert event.physical_keycode == 32
        assert event.unicode == 32

    def test_unknown_key_raises(self, enums):
        with pytest.raises(ValueError, match="Unknown key"):
            _parse_binding("NotAKey", enums)

    def test_unknown_modifier_raises(self, enums):
        with pytest.raises(ValueError, match="Unknown modifier"):
            _parse_binding("foo+A", enums)

    def test_empty_binding_raises(self, enums):
        with pytest.raises(ValueError, match="Empty binding"):
            _parse_binding("", enums)

    def test_control_alias(self, enums):
        event = _parse_binding("control+A", enums)
        assert event.modifiers.ctrl_pressed is True

    def test_cmd_alias_for_meta(self, enums):
        event = _parse_binding("cmd+A", enums)
        assert event.modifiers.meta_pressed is True

    def test_command_alias_for_meta(self, enums):
        event = _parse_binding("command+A", enums)
        assert event.modifiers.meta_pressed is True


class TestParseMouseBinding:
    def test_left(self, enums):
        event = _parse_binding("mouse:left", enums)
        assert isinstance(event, InputEventMouseButtonDescriptor)
        assert event.button_index == 1

    def test_right(self, enums):
        event = _parse_binding("mouse:right", enums)
        assert event.button_index == 2

    def test_middle(self, enums):
        event = _parse_binding("mouse:middle", enums)
        assert event.button_index == 3

    def test_with_modifier(self, enums):
        event = _parse_binding("ctrl+mouse:left", enums)
        assert event.modifiers.ctrl_pressed is True
        assert event.button_index == 1

    def test_unknown_button_raises(self, enums):
        with pytest.raises(ValueError, match="Unknown mouse button"):
            _parse_binding("mouse:foo", enums)


class TestParseJoyBinding:
    def test_a(self, enums):
        event = _parse_binding("joy:a", enums)
        assert isinstance(event, InputEventJoypadButtonDescriptor)
        assert event.button_index == 0

    def test_b(self, enums):
        event = _parse_binding("joy:b", enums)
        assert event.button_index == 1

    def test_start(self, enums):
        event = _parse_binding("joy:start", enums)
        assert event.button_index == 6

    def test_unknown_button_raises(self, enums):
        with pytest.raises(ValueError, match="Unknown joy button"):
            _parse_binding("joy:foo", enums)


# --- Serialization ----------------------------------------------------------


class TestSerializeInputEventKey:
    def test_basic_serialization(self, enums):
        event = _parse_binding("A", enums)
        s = event.serialize()
        assert s.startswith("Object(InputEventKey,")
        assert '"resource_local_to_scene":false' in s
        assert '"physical_keycode":65' in s
        assert '"unicode":97' in s
        assert '"script":null)' in s

    def test_modifier_serialization(self, enums):
        event = _parse_binding("ctrl+alt+A", enums)
        s = event.serialize()
        assert '"ctrl_pressed":true' in s
        assert '"alt_pressed":true' in s
        assert '"shift_pressed":false' in s

    def test_device_is_minus_one(self, enums):
        event = _parse_binding("A", enums)
        s = event.serialize()
        assert '"device":-1' in s


class TestSerializeInputEventMouseButton:
    def test_basic_serialization(self, enums):
        event = _parse_binding("mouse:left", enums)
        s = event.serialize()
        assert s.startswith("Object(InputEventMouseButton,")
        assert '"button_index":1' in s
        assert '"script":null)' in s

    def test_has_position_fields(self, enums):
        event = _parse_binding("mouse:left", enums)
        s = event.serialize()
        assert '"position":Vector2(0, 0)' in s
        assert '"global_position":Vector2(0, 0)' in s


class TestSerializeInputEventJoypadButton:
    def test_basic_serialization(self, enums):
        event = _parse_binding("joy:a", enums)
        s = event.serialize()
        assert s.startswith("Object(InputEventJoypadButton,")
        assert '"button_index":0' in s
        assert '"script":null)' in s


class TestSerializeEventDispatch:
    def test_key(self, enums):
        event = _parse_binding("A", enums)
        s = event.serialize()
        assert "InputEventKey" in s

    def test_mouse(self, enums):
        event = _parse_binding("mouse:left", enums)
        s = event.serialize()
        assert "InputEventMouseButton" in s

    def test_joy(self, enums):
        event = _parse_binding("joy:a", enums)
        s = event.serialize()
        assert "InputEventJoypadButton" in s


# --- Action block building --------------------------------------------------


class TestBuildActionBlock:
    def test_single_event(self, enums):
        events = [_parse_binding("A", enums)]
        block = _build_action_block("jump", events, 0.5)
        assert block.startswith("jump={\n")
        assert '"deadzone": 0.5' in block
        assert "InputEventKey" in block
        assert block.endswith("}")

    def test_multiple_events(self, enums):
        events = [_parse_binding("A", enums), _parse_binding("Left", enums)]
        block = _build_action_block("move_left", events, 0.2)
        assert block.count("Object(InputEventKey") == 2
        assert '"deadzone": 0.2' in block

    def test_mixed_event_types(self, enums):
        events = [_parse_binding("A", enums), _parse_binding("mouse:left", enums)]
        block = _build_action_block("attack", events, 0.5)
        assert "InputEventKey" in block
        assert "InputEventMouseButton" in block


# --- project.godot editing --------------------------------------------------


class TestAddOrReplaceAction:
    def test_creates_input_section_when_missing(self):
        content = 'config_version=5\n\n[application]\n\nconfig/name="Test"\n'
        block = 'move_left={\n"deadzone": 0.5,\n"events": []\n}'
        result = _add_or_replace_action(content, "move_left", block)
        assert "[input]" in result
        assert "move_left=" in result

    def test_adds_to_existing_input_section(self):
        content = (
            'config_version=5\n\n[application]\n\nconfig/name="Test"\n\n'
            "[input]\n\n"
            'jump={\n"deadzone": 0.5,\n"events": []\n}\n'
        )
        block = 'move_left={\n"deadzone": 0.5,\n"events": []\n}'
        result = _add_or_replace_action(content, "move_left", block)
        assert "jump=" in result
        assert "move_left=" in result

    def test_replaces_existing_action(self):
        content = (
            "config_version=5\n\n[input]\n\n"
            'move_left={\n"deadzone": 0.5,\n"events": [OLD]\n}\n'
        )
        block = 'move_left={\n"deadzone": 0.2,\n"events": [NEW]\n}'
        result = _add_or_replace_action(content, "move_left", block)
        assert "[NEW]" in result
        assert "[OLD]" not in result

    def test_preserves_other_sections(self):
        content = (
            'config_version=5\n\n[application]\n\nconfig/name="Test"\n\n'
            "[display]\n\nwindow/size/viewport_width=1920\n"
        )
        block = 'jump={\n"deadzone": 0.5,\n"events": []\n}'
        result = _add_or_replace_action(content, "jump", block)
        assert "[application]" in result
        assert 'config/name="Test"' in result
        assert "[display]" in result
        assert "window/size/viewport_width=1920" in result
