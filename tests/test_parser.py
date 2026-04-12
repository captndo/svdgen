from pathlib import Path

import pytest

from svdgen.diagnostics import ParseError, Severity
from svdgen.parser import ParseResult, parse_svd


class TestParseSuccess:
    def test_returns_parse_result(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        assert isinstance(result, ParseResult)

    def test_device_name(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        assert result.device.name == "TestDevice"

    def test_peripherals_parsed(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        names = [p.name for p in result.device.get_peripherals()]
        assert "GPIOA" in names
        assert "GPIOB" in names

    def test_registers_available(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        gpioa = next(p for p in result.device.get_peripherals() if p.name == "GPIOA")
        reg_names = [r.name for r in gpioa.get_registers()]
        assert "MODER" in reg_names
        assert "ODR" in reg_names

    def test_fields_available(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        gpioa = next(p for p in result.device.get_peripherals() if p.name == "GPIOA")
        moder = next(r for r in gpioa.get_registers() if r.name == "MODER")
        field_names = [f.name for f in moder.get_fields()]
        assert "MODE0" in field_names
        assert "MODE1" in field_names

    def test_derived_peripheral_inherits_registers(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        gpiob = next(p for p in result.device.get_peripherals() if p.name == "GPIOB")
        reg_names = [r.name for r in gpiob.get_registers()]
        assert "MODER" in reg_names

    def test_no_errors_on_clean_parse(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert errors == []

    def test_source_map_populated(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        assert len(result.source_map) > 0
        assert "GPIOA" in result.source_map

    def test_cpu_metadata(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        cpu = result.device.cpu
        assert cpu is not None
        assert cpu.revision == "r0p1"
        assert cpu.nvic_prio_bits == 4

    def test_interrupt_parsed(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        gpioa = next(p for p in result.device.get_peripherals() if p.name == "GPIOA")
        assert gpioa.interrupts is not None
        irq_names = [i.name for i in gpioa.interrupts]
        assert "GPIOA_IRQ" in irq_names

    def test_address_block_parsed(self, minimal_svd: Path):
        result = parse_svd(minimal_svd)
        gpioa = next(p for p in result.device.get_peripherals() if p.name == "GPIOA")
        assert gpioa.address_blocks is not None
        assert gpioa.address_blocks[0].size == 0x400


class TestWarningCapture:
    def test_invalid_access_produces_warnings(self, invalid_access_svd: Path):
        result = parse_svd(invalid_access_svd)
        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) >= 1
        assert any("banana" in w.message for w in warnings)

    def test_device_still_parses_with_warnings(self, invalid_access_svd: Path):
        result = parse_svd(invalid_access_svd)
        assert result.device.name == "WarnDevice"


class TestErrorHandling:
    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            parse_svd(tmp_path / "nonexistent.svd")

    def test_malformed_xml_raises_parse_error(self, malformed_svd: Path):
        with pytest.raises(ParseError) as exc_info:
            parse_svd(malformed_svd)
        assert len(exc_info.value.diagnostics) > 0
