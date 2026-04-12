"""Tests for the patch system — loading, validation, selector resolution, execution."""

from pathlib import Path

import pytest

from svdgen.diagnostics import Severity
from svdgen.model import AccessType, Device
from svdgen.normalize import normalize
from svdgen.parser import parse_svd
from svdgen.patch import PatchSet, apply_patches, load_patches

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def device(minimal_svd: Path) -> Device:
    return normalize(parse_svd(minimal_svd))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoadPatches:
    def test_load_basic(self):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        assert isinstance(ps, PatchSet)
        assert len(ps.patches) == 3

    def test_load_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        ps = load_patches(f)
        assert len(ps.patches) == 0

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_patches(tmp_path / "nope.yaml")

    def test_invalid_structure_not_list(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("target: foo\n")
        with pytest.raises(ValueError, match="YAML list"):
            load_patches(f)

    def test_missing_target(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("- rename: foo\n")
        with pytest.raises(ValueError, match="target"):
            load_patches(f)

    def test_no_action(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text('- target: "X"\n')
        with pytest.raises(ValueError, match="no action"):
            load_patches(f)

    def test_multiple_actions(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text('- target: "X"\n  rename: "Y"\n  remove: true\n')
        with pytest.raises(ValueError, match="multiple actions"):
            load_patches(f)

    def test_patch_fields_populated(self):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        p0 = ps.patches[0]
        assert p0.target == "GPIOA.MODER"
        assert p0.set_ is not None
        assert p0.set_["description"] == "Patched mode register"

    def test_source_metadata(self):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        assert ps.source_file == FIXTURES / "patches_basic.yaml"
        assert ps.patches[0].source_index == 0
        assert ps.patches[1].source_index == 1


# ---------------------------------------------------------------------------
# Set properties
# ---------------------------------------------------------------------------


class TestSetProperties:
    def test_set_description(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        moder = next(r for r in result.device.peripherals[0].registers if r.name == "MODER")
        assert moder.description == "Patched mode register"

    def test_set_reset_value(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        moder = next(r for r in result.device.peripherals[0].registers if r.name == "MODER")
        assert moder.reset_value == 0xFFFFFFFF

    def test_set_access_on_register(self, device: Device):
        ps = load_patches(FIXTURES / "patches_access.yaml")
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.access == AccessType.READ_ONLY

    def test_set_access_on_field(self, device: Device):
        ps = load_patches(FIXTURES / "patches_access.yaml")
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        assert mode0.access == AccessType.WRITE_ONLY

    def test_invalid_property_produces_error(self, device: Device, tmp_path: Path):
        f = tmp_path / "bad_prop.yaml"
        f.write_text('- target: "GPIOA"\n  set:\n    nonexistent_prop: 42\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "nonexistent_prop" in errors[0].message

    def test_invalid_access_value_produces_error(self, device: Device, tmp_path: Path):
        f = tmp_path / "bad_access.yaml"
        f.write_text('- target: "GPIOA.MODER"\n  set:\n    access: "banana"\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert any("banana" in e.message for e in errors)


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


class TestRename:
    def test_rename_field(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        field_names = [f.name for f in moder.fields]
        assert "MODER_BIT1" in field_names
        assert "MODE1" not in field_names

    def test_rename_peripheral(self, device: Device, tmp_path: Path):
        f = tmp_path / "rename_periph.yaml"
        f.write_text('- target: "GPIOA"\n  rename: "PORTA"\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        names = [p.name for p in result.device.peripherals]
        assert "PORTA" in names
        assert "GPIOA" not in names

    def test_rename_register(self, device: Device, tmp_path: Path):
        f = tmp_path / "rename_reg.yaml"
        f.write_text('- target: "GPIOA.MODER"\n  rename: "MODE_REG"\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        reg_names = [r.name for r in gpioa.registers]
        assert "MODE_REG" in reg_names
        assert "MODER" not in reg_names


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_register(self, device: Device):
        ps = load_patches(FIXTURES / "patches_remove.yaml")
        gpioa_before = device.peripherals[0]
        assert any(r.name == "ODR" for r in gpioa_before.registers)

        result = apply_patches(device, ps)
        gpioa_after = result.device.peripherals[0]
        assert not any(r.name == "ODR" for r in gpioa_after.registers)

    def test_remove_peripheral(self, device: Device, tmp_path: Path):
        f = tmp_path / "rm_periph.yaml"
        f.write_text('- target: "GPIOB"\n  remove: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        names = [p.name for p in result.device.peripherals]
        assert "GPIOB" not in names

    def test_remove_field(self, device: Device, tmp_path: Path):
        f = tmp_path / "rm_field.yaml"
        f.write_text('- target: "GPIOA.MODER.MODE1"\n  remove: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        field_names = [fl.name for fl in moder.fields]
        assert "MODE1" not in field_names
        assert "MODE0" in field_names


# ---------------------------------------------------------------------------
# Disable
# ---------------------------------------------------------------------------


class TestDisable:
    def test_disable_field(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        odr = next(r for r in gpioa.registers if r.name == "ODR")
        od0 = next(f for f in odr.fields if f.name == "OD0")
        assert od0.enabled is False

    def test_disable_register(self, device: Device, tmp_path: Path):
        f = tmp_path / "dis_reg.yaml"
        f.write_text('- target: "GPIOA.ODR"\n  disable: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        odr = next(r for r in gpioa.registers if r.name == "ODR")
        assert odr.enabled is False

    def test_disable_peripheral(self, device: Device, tmp_path: Path):
        f = tmp_path / "dis_periph.yaml"
        f.write_text('- target: "GPIOB"\n  disable: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        gpiob = next(p for p in result.device.peripherals if p.name == "GPIOB")
        assert gpiob.enabled is False

    def test_enabled_by_default(self, device: Device):
        gpioa = device.peripherals[0]
        assert gpioa.enabled is True
        assert gpioa.registers[0].enabled is True
        assert gpioa.registers[0].fields[0].enabled is True


# ---------------------------------------------------------------------------
# Selector resolution / error handling
# ---------------------------------------------------------------------------


class TestSelectorErrors:
    def test_bad_peripheral(self, device: Device):
        ps = load_patches(FIXTURES / "patches_bad_target.yaml")
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "NONEXISTENT" in errors[0].message

    def test_bad_register(self, device: Device, tmp_path: Path):
        f = tmp_path / "bad_reg.yaml"
        f.write_text('- target: "GPIOA.NONEXISTENT"\n  remove: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1

    def test_bad_field(self, device: Device, tmp_path: Path):
        f = tmp_path / "bad_field.yaml"
        f.write_text('- target: "GPIOA.MODER.NONEXISTENT"\n  remove: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1

    def test_too_deep_selector(self, device: Device, tmp_path: Path):
        f = tmp_path / "deep.yaml"
        f.write_text('- target: "A.B.C.D"\n  remove: true\n')
        ps = load_patches(f)
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_later_patch_wins(self, device: Device):
        ps = load_patches(FIXTURES / "patches_ordering.yaml")
        result = apply_patches(device, ps)
        gpioa = result.device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.description == "second"


# ---------------------------------------------------------------------------
# Immutability — original device unchanged
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_original_device_unchanged(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        assert result.device is not device
        moder_orig = next(r for r in device.peripherals[0].registers if r.name == "MODER")
        assert moder_orig.description != "Patched mode register"

    def test_no_diagnostics_on_clean_patch(self, device: Device):
        ps = load_patches(FIXTURES / "patches_basic.yaml")
        result = apply_patches(device, ps)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert errors == []
