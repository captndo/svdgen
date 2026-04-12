"""Tests for model serialization (export.py)."""

from __future__ import annotations

import json
from io import StringIO

from svdgen.export import device_to_dict, export_json
from svdgen.model import (
    CPU,
    AccessType,
    AddressBlock,
    Device,
    EndianType,
    EnumeratedValue,
    EnumeratedValueSet,
    Field,
    Interrupt,
    Peripheral,
    Register,
)


def _make_device() -> Device:
    field = Field(
        name="MODE0",
        raw_name="MODE0",
        description="mode bits",
        bit_offset=0,
        bit_width=2,
        access=AccessType.READ_WRITE,
        enumerated_values=(
            EnumeratedValueSet(
                name="MODE",
                usage=None,
                values=(
                    EnumeratedValue(name="Input", description="input", value=0),
                    EnumeratedValue(name="Output", description="output", value=1),
                ),
            ),
        ),
    )
    reg = Register(
        name="MODER",
        raw_name="MODER",
        description="mode register",
        address_offset=0,
        absolute_address=0x4002_0000,
        size=32,
        access=AccessType.READ_WRITE,
        reset_value=0,
        reset_mask=0xFFFFFFFF,
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
        interrupts=(Interrupt(name="GPIOA_IRQ", description="irq", value=6),),
        address_blocks=(AddressBlock(offset=0, size=0x400, usage="registers"),),
    )
    return Device(
        name="TestDevice",
        raw_name="TestDevice",
        description="test",
        version="1.0",
        vendor="TestVendor",
        vendor_id="TV",
        address_unit_bits=8,
        width=32,
        cpu=CPU(
            name="CM4",
            revision="r0p1",
            endian=EndianType.LITTLE,
            mpu_present=True,
            fpu_present=True,
            nvic_prio_bits=4,
            vendor_systick_config=False,
        ),
        peripherals=(periph,),
    )


class TestDeviceToDict:
    def test_returns_dict(self):
        d = device_to_dict(_make_device())
        assert isinstance(d, dict)

    def test_device_name(self):
        d = device_to_dict(_make_device())
        assert d["name"] == "TestDevice"

    def test_enum_serialized_as_string(self):
        d = device_to_dict(_make_device())
        assert d["cpu"]["endian"] == "little"

    def test_access_type_serialized(self):
        d = device_to_dict(_make_device())
        reg = d["peripherals"][0]["registers"][0]
        assert reg["access"] == "read-write"

    def test_nested_structure(self):
        d = device_to_dict(_make_device())
        field = d["peripherals"][0]["registers"][0]["fields"][0]
        assert field["name"] == "MODE0"
        assert field["bit_offset"] == 0
        assert field["bit_width"] == 2

    def test_tuples_become_lists(self):
        d = device_to_dict(_make_device())
        assert isinstance(d["peripherals"], list)
        assert isinstance(d["peripherals"][0]["registers"], list)

    def test_enumerated_values(self):
        d = device_to_dict(_make_device())
        evs = d["peripherals"][0]["registers"][0]["fields"][0]["enumerated_values"]
        assert len(evs) == 1
        assert evs[0]["name"] == "MODE"
        assert len(evs[0]["values"]) == 2

    def test_none_preserved(self):
        d = device_to_dict(_make_device())
        assert d["peripherals"][0]["derived_from"] is None


class TestExportJson:
    def test_returns_string(self):
        result = export_json(_make_device())
        assert isinstance(result, str)

    def test_valid_json(self):
        result = export_json(_make_device())
        parsed = json.loads(result)
        assert parsed["name"] == "TestDevice"

    def test_write_to_file(self):
        buf = StringIO()
        result = export_json(_make_device(), file=buf)
        assert result is None
        parsed = json.loads(buf.getvalue())
        assert parsed["name"] == "TestDevice"

    def test_indent(self):
        result = export_json(_make_device(), indent=4)
        assert "    " in result

    def test_roundtrip_field_count(self):
        result = export_json(_make_device())
        parsed = json.loads(result)
        assert len(parsed["peripherals"][0]["registers"][0]["fields"]) == 1
