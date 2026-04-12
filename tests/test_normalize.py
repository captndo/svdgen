"""Tests for the normalization pipeline."""

from pathlib import Path

import pytest

from svdgen.model import AccessType, Device, EndianType
from svdgen.normalize import normalize
from svdgen.parser import parse_svd


@pytest.fixture
def device(minimal_svd: Path) -> Device:
    return normalize(parse_svd(minimal_svd))


class TestDeviceNormalization:
    def test_returns_device(self, device: Device):
        assert isinstance(device, Device)

    def test_device_name(self, device: Device):
        assert device.name == "TestDevice"
        assert device.raw_name == "TestDevice"

    def test_device_metadata(self, device: Device):
        assert device.vendor == "TestVendor"
        assert device.vendor_id == "TV"
        assert device.version == "1.0"
        assert device.width == 32
        assert device.address_unit_bits == 8

    def test_default_register_properties(self, device: Device):
        assert device.default_register_size == 32
        assert device.default_access == AccessType.READ_WRITE
        assert device.default_reset_value == 0
        assert device.default_reset_mask == 0xFFFFFFFF

    def test_description_cleaned(self, device: Device):
        assert device.description is not None
        assert "\n" not in device.description


class TestCPUNormalization:
    def test_cpu_present(self, device: Device):
        assert device.cpu is not None

    def test_cpu_name(self, device: Device):
        assert device.cpu.name == "CM4"

    def test_cpu_endian(self, device: Device):
        assert device.cpu.endian == EndianType.LITTLE

    def test_cpu_capabilities(self, device: Device):
        assert device.cpu.mpu_present is True
        assert device.cpu.fpu_present is True
        assert device.cpu.nvic_prio_bits == 4
        assert device.cpu.vendor_systick_config is False


class TestPeripheralNormalization:
    def test_peripheral_count(self, device: Device):
        assert len(device.peripherals) == 2

    def test_sorted_by_base_address(self, device: Device):
        addrs = [p.base_address for p in device.peripherals]
        assert addrs == sorted(addrs)

    def test_gpioa_basics(self, device: Device):
        gpioa = device.peripherals[0]
        assert gpioa.name == "GPIOA"
        assert gpioa.raw_name == "GPIOA"
        assert gpioa.base_address == 0x40020000
        assert gpioa.group_name == "GPIO"

    def test_gpiob_derived(self, device: Device):
        gpiob = device.peripherals[1]
        assert gpiob.name == "GPIOB"
        assert gpiob.base_address == 0x40020400
        assert gpiob.derived_from == "GPIOA"

    def test_derived_peripheral_has_registers(self, device: Device):
        gpiob = device.peripherals[1]
        assert len(gpiob.registers) > 0
        reg_names = [r.name for r in gpiob.registers]
        assert "MODER" in reg_names

    def test_source_path(self, device: Device):
        assert device.peripherals[0].source_path == "GPIOA"

    def test_address_blocks(self, device: Device):
        gpioa = device.peripherals[0]
        assert len(gpioa.address_blocks) == 1
        ab = gpioa.address_blocks[0]
        assert ab.offset == 0
        assert ab.size == 0x400
        assert ab.usage == "registers"

    def test_interrupts(self, device: Device):
        gpioa = device.peripherals[0]
        assert len(gpioa.interrupts) == 1
        irq = gpioa.interrupts[0]
        assert irq.name == "GPIOA_IRQ"
        assert irq.value == 6


class TestRegisterNormalization:
    def test_registers_sorted_by_offset(self, device: Device):
        gpioa = device.peripherals[0]
        offsets = [r.address_offset for r in gpioa.registers]
        assert offsets == sorted(offsets)

    def test_absolute_address(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.address_offset == 0x00
        assert moder.absolute_address == 0x40020000

    def test_odr_absolute_address(self, device: Device):
        gpioa = device.peripherals[0]
        odr = next(r for r in gpioa.registers if r.name == "ODR")
        assert odr.address_offset == 0x14
        assert odr.absolute_address == 0x40020014

    def test_register_properties(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.size == 32
        assert moder.access == AccessType.READ_WRITE
        assert moder.reset_value == 0

    def test_source_path(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.source_path == "GPIOA.MODER"

    def test_raw_name_preserved(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        assert moder.raw_name == "MODER"

    def test_derived_peripheral_register_addresses(self, device: Device):
        """GPIOB's registers should use GPIOB's base address."""
        gpiob = device.peripherals[1]
        moder = next(r for r in gpiob.registers if r.name == "MODER")
        assert moder.absolute_address == 0x40020400


class TestFieldNormalization:
    def test_fields_sorted_by_bit_offset(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        offsets = [f.bit_offset for f in moder.fields]
        assert offsets == sorted(offsets)

    def test_field_basics(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        assert mode0.bit_offset == 0
        assert mode0.bit_width == 2
        assert mode0.access == AccessType.READ_WRITE

    def test_field_bit_mask(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        assert mode0.bit_mask == 0b11

    def test_field_source_path(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        assert mode0.source_path == "GPIOA.MODER.MODE0"

    def test_enumerated_values(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        assert len(mode0.enumerated_values) == 1
        evs = mode0.enumerated_values[0]
        assert evs.name == "MODE"
        assert len(evs.values) == 2
        names = {v.name for v in evs.values}
        assert names == {"Input", "Output"}

    def test_enumerated_value_details(self, device: Device):
        gpioa = device.peripherals[0]
        moder = next(r for r in gpioa.registers if r.name == "MODER")
        mode0 = next(f for f in moder.fields if f.name == "MODE0")
        evs = mode0.enumerated_values[0]
        inp = next(v for v in evs.values if v.name == "Input")
        assert inp.value == 0
        assert inp.description == "Input mode"
        assert inp.is_default is False


class TestDescriptionCleanup:
    def test_whitespace_collapsed(self, minimal_svd: Path):
        """Multi-word descriptions should have single-space separation."""
        device = normalize(parse_svd(minimal_svd))
        gpioa = device.peripherals[0]
        assert gpioa.description is not None
        assert "  " not in gpioa.description


class TestImmutability:
    def test_device_frozen(self, device: Device):
        with pytest.raises(AttributeError):
            device.name = "changed"  # type: ignore[misc]

    def test_peripheral_frozen(self, device: Device):
        with pytest.raises(AttributeError):
            device.peripherals[0].name = "changed"  # type: ignore[misc]

    def test_register_frozen(self, device: Device):
        reg = device.peripherals[0].registers[0]
        with pytest.raises(AttributeError):
            reg.name = "changed"  # type: ignore[misc]

    def test_field_frozen(self, device: Device):
        field = device.peripherals[0].registers[0].fields[0]
        with pytest.raises(AttributeError):
            field.name = "changed"  # type: ignore[misc]
