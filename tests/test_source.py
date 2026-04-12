from pathlib import Path

from svdgen.source import SourceMap


class TestSourceMap:
    def test_device_entry(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        info = sm.lookup("TestDevice")
        assert info is not None
        assert info.element_tag == "device"
        assert info.line is not None
        assert info.file_path == minimal_svd

    def test_peripheral_entry(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        assert "GPIOA" in sm
        assert "GPIOB" in sm
        info = sm.lookup("GPIOA")
        assert info is not None
        assert info.element_tag == "peripheral"
        assert info.line is not None

    def test_register_entry(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        info = sm.lookup("GPIOA.MODER")
        assert info is not None
        assert info.element_tag == "register"
        assert info.line is not None

    def test_field_entry(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        info = sm.lookup("GPIOA.MODER.MODE0")
        assert info is not None
        assert info.element_tag == "field"
        assert info.line is not None

    def test_interrupt_entry(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        info = sm.lookup("GPIOA.GPIOA_IRQ")
        assert info is not None
        assert info.element_tag == "interrupt"

    def test_missing_path_returns_none(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        assert sm.lookup("NONEXISTENT") is None

    def test_len(self, minimal_svd: Path):
        sm = SourceMap.from_svd(minimal_svd)
        assert len(sm) > 0

    def test_line_ordering(self, minimal_svd: Path):
        """Peripheral GPIOA should appear before GPIOB in the source."""
        sm = SourceMap.from_svd(minimal_svd)
        a = sm.lookup("GPIOA")
        b = sm.lookup("GPIOB")
        assert a is not None and b is not None
        assert a.line < b.line
