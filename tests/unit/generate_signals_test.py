from __future__ import annotations

import pytest

from godotllminteraction.cli.specifications import render_signals_source

pytestmark = [pytest.mark.specs]


def _fake_data(classes=None) -> dict:
    return {"builtin_classes": [], "classes": classes or []}


CAMERA_SERVER_CLASS = {
    "name": "CameraServer",
    "signals": [
        {
            "name": "camera_feed_added",
            "arguments": [{"name": "id", "type": "int"}],
        },
    ],
}

FILESYSTEM_CLASS = {
    "name": "EditorFileSystem",
    "inherits": "Object",
    "signals": [
        {"name": "filesystem_changed"},
        {
            "name": "sources_changed",
            "arguments": [{"name": "exist", "type": "bool"}],
        },
        {
            "name": "resources_reimported",
            "arguments": [{"name": "resources", "type": "PackedStringArray"}],
        },
    ],
}

NO_SIGNALS_CLASS = {"name": "Object", "properties": [{"name": "x", "type": "int"}]}


class TestRenderSignals:
    def test_is_deterministic(self):
        data = _fake_data([FILESYSTEM_CLASS, CAMERA_SERVER_CLASS])
        assert render_signals_source(data, "v4_7_0") == render_signals_source(
            data, "v4_7_0"
        )

    def test_classes_sorted_regardless_of_input_order(self):
        data = _fake_data([FILESYSTEM_CLASS, CAMERA_SERVER_CLASS])
        source = render_signals_source(data, "v4_7_0")
        assert source.index('"CameraServer"') < source.index('"EditorFileSystem"')

    def test_class_without_signals_is_omitted(self):
        data = _fake_data([NO_SIGNALS_CLASS, CAMERA_SERVER_CLASS])
        source = render_signals_source(data, "v4_7_0")
        assert '"Object"' not in source

    def test_zero_argument_signal_renders_without_arguments(self):
        data = _fake_data([FILESYSTEM_CLASS])
        source = render_signals_source(data, "v4_7_0")
        assert 'GodotSignal(name="filesystem_changed")' in source

    def test_signal_with_arguments_renders_argument_models(self):
        data = _fake_data([CAMERA_SERVER_CLASS])
        source = render_signals_source(data, "v4_7_0")
        assert (
            'GodotSignal(name="camera_feed_added", '
            'arguments=(SignalArgument(name="id", type="int"),))' in source
        )

    def test_version_label_embedded_in_docstring(self):
        data = _fake_data([CAMERA_SERVER_CLASS])
        source = render_signals_source(data, "v9_9_9")
        assert "generate-signals --version v9_9_9" in source

    def test_generated_source_is_valid_importable_python(self, load_module):
        data = _fake_data([CAMERA_SERVER_CLASS, FILESYSTEM_CLASS])
        module = load_module(render_signals_source(data, "v4_7_0"))
        signals = module.SIGNALS["EditorFileSystem"]
        assert set(signals) == {
            "filesystem_changed",
            "sources_changed",
            "resources_reimported",
        }
        assert signals["filesystem_changed"].arguments == ()
        assert signals["sources_changed"].arguments[0].name == "exist"
        assert signals["sources_changed"].arguments[0].type == "bool"

    def test_generated_models_are_frozen(self, load_module):
        import pydantic
        import pytest

        module = load_module(
            render_signals_source(_fake_data([CAMERA_SERVER_CLASS]), "v4_7_0")
        )
        signal = module.SIGNALS["CameraServer"]["camera_feed_added"]
        with pytest.raises(pydantic.ValidationError):
            signal.name = "other"
