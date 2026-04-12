"""Tests for the extension API (custom filters and globals)."""

from __future__ import annotations

from pathlib import Path

import svdgen
from svdgen.config import load_config
from svdgen.model import Device, Field, Peripheral, Register
from svdgen.pipeline import run
from svdgen.render import OutputTarget, render_targets


def _make_device() -> Device:
    field = Field(
        name="MODE0",
        raw_name="MODE0",
        description="mode bits",
        bit_offset=0,
        bit_width=2,
        access=None,
        enumerated_values=(),
    )
    reg = Register(
        name="MODER",
        raw_name="MODER",
        description="mode register",
        address_offset=0,
        absolute_address=0x4002_0000,
        size=32,
        access=None,
        reset_value=0,
        reset_mask=None,
        fields=(field,),
    )
    periph = Peripheral(
        name="GPIOA",
        raw_name="GPIOA",
        description="GPIO A",
        group_name="GPIO",
        base_address=0x4002_0000,
        derived_from=None,
        registers=(reg,),
        interrupts=(),
        address_blocks=(),
    )
    return Device(
        name="TestDevice",
        raw_name="TestDevice",
        description="test",
        version="1.0",
        vendor=None,
        vendor_id=None,
        address_unit_bits=8,
        width=32,
        cpu=None,
        peripherals=(periph,),
    )


# ---------------------------------------------------------------------------
# render_targets extension points
# ---------------------------------------------------------------------------


class TestCustomFilters:
    def test_custom_filter_available(self, tmp_path: Path):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ device.name | shout }}")

        device = _make_device()
        targets = [OutputTarget(
            name="t", template="test.j2", output_path="out.txt",
        )]
        result = render_targets(
            device, targets, [tmp_path],
            custom_filters={"shout": lambda s: s.upper() + "!!!"},
        )
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "TESTDEVICE!!!"

    def test_custom_filter_overrides_builtin(self, tmp_path: Path):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ device.name | upper_snake }}")

        device = _make_device()
        targets = [OutputTarget(
            name="t", template="test.j2", output_path="out.txt",
        )]

        result = render_targets(
            device, targets, [tmp_path],
            custom_filters={"upper_snake": lambda s: f"CUSTOM_{s}"},
        )
        assert result.artifacts[0].content == "CUSTOM_TestDevice"

    def test_none_filters_is_noop(self, tmp_path: Path):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ device.name | upper_snake }}")

        device = _make_device()
        targets = [OutputTarget(
            name="t", template="test.j2", output_path="out.txt",
        )]
        result = render_targets(
            device, targets, [tmp_path], custom_filters=None,
        )
        assert result.artifacts[0].content == "TEST_DEVICE"


class TestCustomGlobals:
    def test_custom_global_available(self, tmp_path: Path):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ project_prefix }}_{{ device.name }}")

        device = _make_device()
        targets = [OutputTarget(
            name="t", template="test.j2", output_path="out.txt",
        )]
        result = render_targets(
            device, targets, [tmp_path],
            custom_globals={"project_prefix": "HAL"},
        )
        assert result.artifacts[0].content == "HAL_TestDevice"

    def test_custom_global_function(self, tmp_path: Path):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ repeat(device.name, 2) }}")

        device = _make_device()
        targets = [OutputTarget(
            name="t", template="test.j2", output_path="out.txt",
        )]
        result = render_targets(
            device, targets, [tmp_path],
            custom_globals={"repeat": lambda s, n: (s + " ") * n},
        )
        assert result.artifacts[0].content.strip() == "TestDevice TestDevice"


# ---------------------------------------------------------------------------
# pipeline.run extension points
# ---------------------------------------------------------------------------


class TestPipelineExtensions:
    def test_custom_filter_through_pipeline(
        self, tmp_path: Path, minimal_svd: Path
    ):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ device.name | reverse_str }}")
        cfg_path = tmp_path / "svdgen.toml"
        cfg_path.write_text(f"""
[input]
svd = "{minimal_svd}"

[templates]
dirs = ["{tmp_path}"]

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "rev"
template = "test.j2"
output_path = "rev.txt"
""")
        config = load_config(cfg_path)
        result = run(
            config,
            custom_filters={"reverse_str": lambda s: s[::-1]},
        )
        assert result.success
        content = (tmp_path / "gen" / "rev.txt").read_text()
        assert content == "eciveDtseT"

    def test_custom_global_through_pipeline(
        self, tmp_path: Path, minimal_svd: Path
    ):
        tpl = tmp_path / "test.j2"
        tpl.write_text("{{ banner }}:{{ device.name }}")
        cfg_path = tmp_path / "svdgen.toml"
        cfg_path.write_text(f"""
[input]
svd = "{minimal_svd}"

[templates]
dirs = ["{tmp_path}"]

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "g"
template = "test.j2"
output_path = "g.txt"
""")
        config = load_config(cfg_path)
        result = run(
            config,
            custom_globals={"banner": "GENERATED"},
        )
        assert result.success
        content = (tmp_path / "gen" / "g.txt").read_text()
        assert content == "GENERATED:TestDevice"


# ---------------------------------------------------------------------------
# Built-in filter imports
# ---------------------------------------------------------------------------


class TestBuiltinFilterImports:
    def test_upper_snake_importable(self):
        assert svdgen.upper_snake("myName") == "MY_NAME"

    def test_lower_snake_importable(self):
        assert svdgen.lower_snake("MyName") == "my_name"

    def test_camel_case_importable(self):
        assert svdgen.camel_case("my_name") == "MyName"

    def test_hex_format_importable(self):
        assert svdgen.hex_format(255, 4) == "0x00FF"

    def test_c_comment_importable(self):
        assert svdgen.c_comment("hello") == "/* hello */"

    def test_c_line_comment_importable(self):
        assert svdgen.c_line_comment("hello") == "// hello"

    def test_pad_importable(self):
        assert svdgen.pad("hi", 10) == "hi        "

    def test_access_str_importable(self):
        from svdgen import AccessType
        assert svdgen.access_str(AccessType.READ_ONLY) == "RO"
