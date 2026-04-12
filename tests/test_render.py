"""Tests for the render engine — scope iteration, path resolution, collision detection."""

from pathlib import Path

import pytest

from svdgen.diagnostics import Severity
from svdgen.model import Device
from svdgen.normalize import normalize
from svdgen.parser import parse_svd
from svdgen.render import (
    OutputTarget,
    Scope,
    render_targets,
)


@pytest.fixture
def device(minimal_svd: Path) -> Device:
    return normalize(parse_svd(minimal_svd))


# ---------------------------------------------------------------------------
# Scope iteration
# ---------------------------------------------------------------------------


class TestDeviceScope:
    def test_single_artifact(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "dev.h.j2"
        tpl.write_text("/* {{ device.name }} */\n")
        target = OutputTarget(
            name="dev",
            template="dev.h.j2",
            output_path="device.h",
            scope=Scope.DEVICE,
        )
        result = render_targets(device, [target], [tmp_path])
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "/* TestDevice */\n"
        assert result.artifacts[0].path == "device.h"


class TestPeripheralScope:
    def test_one_per_peripheral(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "periph.j2"
        tpl.write_text("{{ peripheral.name }}")
        target = OutputTarget(
            name="periph",
            template="periph.j2",
            output_path="{{ peripheral.name }}.h",
            scope=Scope.PERIPHERAL,
        )
        result = render_targets(device, [target], [tmp_path])
        assert len(result.artifacts) == 2
        names = {a.path for a in result.artifacts}
        assert names == {"GPIOA.h", "GPIOB.h"}

    def test_path_with_filter(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "periph.j2"
        tpl.write_text("ok")
        target = OutputTarget(
            name="p",
            template="periph.j2",
            output_path="include/{{ peripheral.name | lower }}.h",
            scope=Scope.PERIPHERAL,
        )
        result = render_targets(device, [target], [tmp_path])
        paths = {a.path for a in result.artifacts}
        assert "include/gpioa.h" in paths


class TestRegisterScope:
    def test_one_per_register(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "reg.j2"
        tpl.write_text("{{ peripheral.name }}.{{ register.name }}")
        target = OutputTarget(
            name="reg",
            template="reg.j2",
            output_path="{{ peripheral.name }}_{{ register.name }}.txt",
            scope=Scope.REGISTER,
        )
        result = render_targets(device, [target], [tmp_path])
        assert len(result.artifacts) >= 2
        paths = {a.path for a in result.artifacts}
        assert "GPIOA_MODER.txt" in paths
        assert "GPIOA_ODR.txt" in paths


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


class TestCollisionDetection:
    def test_collision_produces_error(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "t.j2"
        tpl.write_text("x")
        t1 = OutputTarget(name="a", template="t.j2", output_path="same.h")
        t2 = OutputTarget(name="b", template="t.j2", output_path="same.h")
        result = render_targets(device, [t1, t2], [tmp_path])
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "collision" in errors[0].message.lower()


# ---------------------------------------------------------------------------
# Template not found
# ---------------------------------------------------------------------------


class TestTemplateMissing:
    def test_missing_template(self, device: Device, tmp_path: Path):
        target = OutputTarget(name="bad", template="no_such.j2", output_path="out.h")
        result = render_targets(device, [target], [tmp_path])
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "not found" in errors[0].message.lower()


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_version_in_context(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "v.j2"
        tpl.write_text("v={{ provenance.svdgen_version }}")
        target = OutputTarget(name="v", template="v.j2", output_path="v.txt")
        result = render_targets(device, [target], [tmp_path])
        assert result.artifacts[0].content.startswith("v=0.")

    def test_input_source(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "s.j2"
        tpl.write_text("src={{ provenance.input_source }}")
        target = OutputTarget(name="s", template="s.j2", output_path="s.txt")
        result = render_targets(device, [target], [tmp_path], input_source="test.svd")
        assert "test.svd" in result.artifacts[0].content


# ---------------------------------------------------------------------------
# Extra context / target variables
# ---------------------------------------------------------------------------


class TestExtraContext:
    def test_extra_context(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "e.j2"
        tpl.write_text("{{ custom_var }}")
        target = OutputTarget(name="e", template="e.j2", output_path="e.txt")
        ctx = {"custom_var": "hello"}
        result = render_targets(device, [target], [tmp_path], extra_context=ctx)
        assert result.artifacts[0].content == "hello"

    def test_target_variables(self, device: Device, tmp_path: Path):
        tpl = tmp_path / "tv.j2"
        tpl.write_text("{{ guard_prefix }}")
        target = OutputTarget(
            name="tv",
            template="tv.j2",
            output_path="tv.txt",
            variables={"guard_prefix": "MY_PROJECT"},
        )
        result = render_targets(device, [target], [tmp_path])
        assert result.artifacts[0].content == "MY_PROJECT"


# ---------------------------------------------------------------------------
# Built-in template
# ---------------------------------------------------------------------------


class TestBuiltinTemplate:
    def test_c_header_renders(self, device: Device):
        target = OutputTarget(
            name="c_hdr",
            template="c_header/peripheral.h.j2",
            output_path="{{ peripheral.name | lower }}.h",
            scope=Scope.PERIPHERAL,
        )
        result = render_targets(device, [target])
        assert len(result.artifacts) == 2
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert errors == []

    def test_c_header_content(self, device: Device):
        target = OutputTarget(
            name="c_hdr",
            template="c_header/peripheral.h.j2",
            output_path="{{ peripheral.name | lower }}.h",
            scope=Scope.PERIPHERAL,
        )
        result = render_targets(device, [target], input_source="test.svd")
        gpioa_art = next(a for a in result.artifacts if a.path == "gpioa.h")
        content = gpioa_art.content
        assert "#ifndef GPIOA_H" in content
        assert "#define GPIOA_BASE" in content
        assert "GPIOA_MODER_OFFSET" in content
        assert "GPIOA_MODER_MODE0_POS" in content
        assert "GPIOA_MODER_MODE0_MSK" in content
        assert "svdgen" in content
        assert "test.svd" in content
