"""MCP tools for editing project.godot (input actions, autoloads, main scene)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from godotllminteraction.mcp.context import McpContext


def _error_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


# --- Event descriptor models -------------------------------------------------


class Modifiers(BaseModel):
    """Modifier key flags shared by InputEventKey and InputEventMouseButton."""

    alt_pressed: bool = False
    shift_pressed: bool = False
    ctrl_pressed: bool = False
    meta_pressed: bool = False


class InputEventKeyDescriptor(BaseModel):
    """Descriptor for a keyboard InputEventKey in project.godot."""

    modifiers: Modifiers = Field(default_factory=Modifiers)
    keycode: int = 0
    physical_keycode: int = 0
    key_label: int = 0
    unicode: int = 0
    location: int = 0
    echo: bool = False
    pressed: bool = False

    def serialize(self) -> str:
        m = self.modifiers
        return (
            "Object(InputEventKey,"
            '"resource_local_to_scene":false,'
            '"resource_name":"",'
            '"device":-1,'
            '"window_id":0,'
            f'"alt_pressed":{str(m.alt_pressed).lower()},'
            f'"shift_pressed":{str(m.shift_pressed).lower()},'
            f'"ctrl_pressed":{str(m.ctrl_pressed).lower()},'
            f'"meta_pressed":{str(m.meta_pressed).lower()},'
            f'"pressed":{str(self.pressed).lower()},'
            f'"keycode":{self.keycode},'
            f'"physical_keycode":{self.physical_keycode},'
            f'"key_label":{self.key_label},'
            f'"unicode":{self.unicode},'
            f'"location":{self.location},'
            f'"echo":{str(self.echo).lower()},'
            '"script":null)'
        )

    def summary(self) -> str:
        m = self.modifiers
        mod_strs = []
        if m.ctrl_pressed:
            mod_strs.append("ctrl")
        if m.alt_pressed:
            mod_strs.append("alt")
        if m.shift_pressed:
            mod_strs.append("shift")
        if m.meta_pressed:
            mod_strs.append("meta")
        prefix = "+".join(mod_strs) + "+" if mod_strs else ""
        return (
            f"{prefix}physical_keycode={self.physical_keycode}, unicode={self.unicode}"
        )


class InputEventMouseButtonDescriptor(BaseModel):
    """Descriptor for an InputEventMouseButton in project.godot."""

    modifiers: Modifiers = Field(default_factory=Modifiers)
    button_index: int = 0
    pressed: bool = False
    factor: float = 1.0
    canceled: bool = False
    double_click: bool = False

    def serialize(self) -> str:
        m = self.modifiers
        return (
            "Object(InputEventMouseButton,"
            '"resource_local_to_scene":false,'
            '"resource_name":"",'
            '"device":-1,'
            '"window_id":0,'
            f'"alt_pressed":{str(m.alt_pressed).lower()},'
            f'"shift_pressed":{str(m.shift_pressed).lower()},'
            f'"ctrl_pressed":{str(m.ctrl_pressed).lower()},'
            f'"meta_pressed":{str(m.meta_pressed).lower()},'
            f'"button_index":{self.button_index},'
            '"button_mask":0,'
            '"position":Vector2(0, 0),'
            '"global_position":Vector2(0, 0),'
            f'"factor":{self.factor},'
            f'"pressed":{str(self.pressed).lower()},'
            f'"canceled":{str(self.canceled).lower()},'
            f'"double_click":{str(self.double_click).lower()},'
            '"script":null)'
        )

    def summary(self) -> str:
        return f"button_index={self.button_index}"


class InputEventJoypadButtonDescriptor(BaseModel):
    """Descriptor for an InputEventJoypadButton in project.godot."""

    button_index: int = 0
    pressure: float = 0.0
    pressed: bool = False
    device: int = -1

    def serialize(self) -> str:
        return (
            "Object(InputEventJoypadButton,"
            '"resource_local_to_scene":false,'
            '"resource_name":"",'
            f'"device":{self.device},'
            f'"button_index":{self.button_index},'
            f'"pressure":{self.pressure},'
            f'"pressed":{str(self.pressed).lower()},'
            '"script":null)'
        )

    def summary(self) -> str:
        return f"button_index={self.button_index}, device={self.device}"


InputEventDescriptor = Union[
    InputEventKeyDescriptor,
    InputEventMouseButtonDescriptor,
    InputEventJoypadButtonDescriptor,
]


# --- Binding string parsing -------------------------------------------------

_MODIFIER_MAP = {
    "ctrl": "ctrl_pressed",
    "control": "ctrl_pressed",
    "alt": "alt_pressed",
    "shift": "shift_pressed",
    "meta": "meta_pressed",
    "cmd": "meta_pressed",
    "command": "meta_pressed",
}

# Prefix → event type detection
_EVENT_TYPE_PREFIXES = {
    "mouse:": "InputEventMouseButton",
    "joy:": "InputEventJoypadButton",
}


def _load_global_enums(version: str | None):
    """Import the global_enums module for the given Godot version."""
    import importlib

    if version is None:
        version = "4.7.0"
    parts = version.lstrip("v").split(".")
    if len(parts) == 2:
        parts.append("0")
    suffix = f"v{parts[0]}_{parts[1]}_{parts[2]}"
    try:
        return importlib.import_module(
            f"godotllminteraction.specifications.{suffix}.global_enums"
        )
    except ImportError as exc:
        raise ValueError(
            f"Global enums for version {version!r} not found: {exc}"
        ) from exc


def _parse_binding(binding: str, enums) -> InputEventDescriptor:
    """Parse a binding string into an InputEventDescriptor.

    Binding string formats:
        "A"                    → InputEventKeyDescriptor, physical_keycode=KEY_A
        "ctrl+alt+A"           → InputEventKeyDescriptor with modifiers
        "Space"                → InputEventKeyDescriptor, physical_keycode=KEY_SPACE
        "mouse:left"           → InputEventMouseButtonDescriptor, button_index=MOUSE_BUTTON_LEFT
        "joy:a"                → InputEventJoypadButtonDescriptor, button_index=JOY_BUTTON_A
    """
    binding = binding.strip()
    if not binding:
        raise ValueError("Empty binding string")

    # Split on '+' to extract modifiers + final token
    parts = [p.strip() for p in binding.split("+")]
    if not parts:
        raise ValueError(f"Cannot parse binding: {binding!r}")

    modifiers = Modifiers()

    final_token = parts[-1]

    for mod_part in parts[:-1]:
        mod_lower = mod_part.lower()
        if mod_lower in _MODIFIER_MAP:
            setattr(modifiers, _MODIFIER_MAP[mod_lower], True)
        else:
            raise ValueError(
                f"Unknown modifier {mod_part!r} in binding {binding!r}; "
                f"valid modifiers: {', '.join(sorted(_MODIFIER_MAP))}"
            )

    # Check for explicit type prefix on the final token
    event_type = "InputEventKey"  # default: keyboard
    for prefix, etype in _EVENT_TYPE_PREFIXES.items():
        if final_token.lower().startswith(prefix):
            event_type = etype
            final_token = final_token[len(prefix) :].strip()
            break

    if event_type == "InputEventKey":
        return _parse_key_binding(final_token, modifiers, enums)
    elif event_type == "InputEventMouseButton":
        return _parse_mouse_binding(final_token, modifiers, enums)
    elif event_type == "InputEventJoypadButton":
        return _parse_joy_binding(final_token, enums)
    else:
        raise ValueError(f"Unsupported event type: {event_type}")


def _key_name_to_enum_name(token: str) -> str:
    """Convert a user-friendly key name to the KEY_* enum member name.

    "A" → "KEY_A", "Space" → "KEY_SPACE", "Left" → "KEY_LEFT",
    "F1" → "KEY_F1", "Kp_Enter" → "KEY_KP_ENTER"
    """
    # Already a full KEY_ name
    if token.upper().startswith("KEY_"):
        return token.upper()
    return "KEY_" + token.upper()


def _parse_key_binding(
    token: str, modifiers: Modifiers, enums
) -> InputEventKeyDescriptor:
    enum_name = _key_name_to_enum_name(token)
    try:
        keycode = enums.Key[enum_name].value
    except KeyError:
        raise ValueError(
            f"Unknown key {token!r} (looked up as {enum_name}); "
            f"use Godot key names like A, Space, Left, F1, etc."
        )

    unicode_val = 0
    if 65 <= keycode <= 90:  # A-Z
        unicode_val = keycode + 32  # lowercase a-z
    elif 48 <= keycode <= 57:  # 0-9
        unicode_val = keycode
    elif keycode == 32:  # Space
        unicode_val = 32

    return InputEventKeyDescriptor(
        modifiers=modifiers,
        physical_keycode=keycode,
        unicode=unicode_val,
    )


def _mouse_name_to_enum_name(token: str) -> str:
    """Convert a mouse button name to the MOUSE_BUTTON_* enum member name."""
    if token.upper().startswith("MOUSE_BUTTON_"):
        return token.upper()
    return "MOUSE_BUTTON_" + token.upper()


def _parse_mouse_binding(
    token: str, modifiers: Modifiers, enums
) -> InputEventMouseButtonDescriptor:
    enum_name = _mouse_name_to_enum_name(token)
    try:
        button_index = enums.MouseButton[enum_name].value
    except KeyError:
        raise ValueError(
            f"Unknown mouse button {token!r} (looked up as {enum_name}); "
            f"use: left, right, middle, wheel_up, wheel_down, etc."
        )

    return InputEventMouseButtonDescriptor(
        modifiers=modifiers,
        button_index=button_index,
    )


def _joy_name_to_enum_name(token: str) -> str:
    """Convert a joy button name to the JOY_BUTTON_* enum member name."""
    if token.upper().startswith("JOY_BUTTON_"):
        return token.upper()
    return "JOY_BUTTON_" + token.upper()


def _parse_joy_binding(token: str, enums) -> InputEventJoypadButtonDescriptor:
    enum_name = _joy_name_to_enum_name(token)
    try:
        button_index = enums.JoyButton[enum_name].value
    except KeyError:
        raise ValueError(
            f"Unknown joy button {token!r} (looked up as {enum_name}); "
            f"use: a, b, x, y, back, guide, start, etc."
        )

    return InputEventJoypadButtonDescriptor(button_index=button_index)


# --- Action block building --------------------------------------------------


def _build_action_block(
    action_name: str, events: list[InputEventDescriptor], deadzone: float
) -> str:
    """Build the full action block string for project.godot's [input] section."""
    event_strs = ", ".join(e.serialize() for e in events)
    return f'{action_name}={{\n"deadzone": {deadzone},\n"events": [{event_strs}]\n}}'


# --- project.godot editing --------------------------------------------------

_INPUT_SECTION_RE = re.compile(r"^\[input\]\s*$", re.MULTILINE)
_ACTION_RE_TEMPLATE = r"^{action_name}=.*?(?=\n[a-zA-Z]|\n\[|\Z)"


def _read_project_godot(project_path: Path) -> str:
    """Read project.godot, returning its full text."""
    if not project_path.exists():
        raise FileNotFoundError(f"project.godot not found at {project_path}")
    return project_path.read_text()


def _add_or_replace_action(content: str, action_name: str, action_block: str) -> str:
    """Add or replace an input action in the project.godot content.

    If the [input] section doesn't exist, it's created.
    If the action already exists, it's replaced.
    """
    # Escape the action name for regex
    escaped = re.escape(action_name)
    action_re = re.compile(
        rf"^{escaped}=\{{.*?\n\}}",
        re.MULTILINE | re.DOTALL,
    )

    # Check if [input] section exists
    input_section_match = _INPUT_SECTION_RE.search(content)

    if input_section_match:
        # Try to replace existing action
        new_content, count = action_re.subn(action_block, content)
        if count > 0:
            return new_content

        # Action doesn't exist yet — insert after the [input] header
        insert_pos = input_section_match.end()
        # Find the next non-blank line after [input]
        rest = content[insert_pos:]
        # Skip blank lines
        stripped = rest.lstrip("\n")
        insert_pos = len(content) - len(stripped)

        new_content = (
            content[:insert_pos] + action_block + "\n\n" + content[insert_pos:]
        )
        return new_content
    else:
        # No [input] section — create one at the end
        # Ensure there's a blank line before the new section
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not content.endswith("\n\n"):
            content += "\n"

        new_content = content + "[input]\n\n" + action_block + "\n"
        return new_content


def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def add_input_action(
        project_path: Annotated[
            str,
            Field(
                description="Absolute path to the Godot project directory (containing project.godot)."
            ),
        ],
        action_name: Annotated[
            str,
            Field(
                description="Name of the input action, e.g. 'move_left', 'jump', 'attack'."
            ),
        ],
        bindings: Annotated[
            list[str],
            Field(
                description=(
                    "List of key/mouse/joypad binding strings. "
                    "Keyboard (default): 'A', 'ctrl+alt+A', 'Space', 'Left', 'F1'. "
                    "Mouse: 'mouse:left', 'mouse:right', 'mouse:middle'. "
                    "Joypad: 'joy:a', 'joy:b', 'joy:start'. "
                    "Modifiers: ctrl, alt, shift, meta/cmd (keyboard & mouse only)."
                ),
            ),
        ],
        deadzone: Annotated[
            float,
            Field(description="Input deadzone (0.0 to 1.0, default 0.5)."),
        ] = 0.5,
        version: Annotated[
            str | None,
            Field(
                description="Godot version for keycode lookup, e.g. '4.7.0'. Defaults to set version."
            ),
        ] = None,
    ) -> str:
        """Add or replace an input action in project.godot with parsed key bindings.

        Parses simple binding strings like 'ctrl+alt+A' and builds the verbose
        Object(InputEventKey, ...) serialization that Godot expects in the [input]
        section. Supports keyboard, mouse, and joypad bindings.
        """
        ver = version or ctx.godot_version
        try:
            enums = _load_global_enums(ver)
        except ValueError as exc:
            return _error_json(str(exc))

        project_dir = Path(project_path)
        project_godot = project_dir / "project.godot"
        if not project_godot.exists():
            return _error_json(f"project.godot not found at {project_godot}")

        # Parse all bindings
        events: list[InputEventDescriptor] = []
        errors: list[str] = []
        for b in bindings:
            try:
                event = _parse_binding(b, enums)
                events.append(event)
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            return _error_json(f"Binding parse errors: {'; '.join(errors)}")

        action_block = _build_action_block(action_name, events, deadzone)

        content = project_godot.read_text()
        new_content = _add_or_replace_action(content, action_name, action_block)
        project_godot.write_text(new_content)

        return json.dumps(
            {
                "ok": True,
                "action": action_name,
                "bindings": bindings,
                "events": [
                    {"type": type(e).__name__, "summary": e.summary()} for e in events
                ],
                "deadzone": deadzone,
                "file": str(project_godot),
            },
            indent=2,
        )
