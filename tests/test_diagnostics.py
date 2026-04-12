from pathlib import Path

from svdgen.diagnostics import Diagnostic, DiagnosticCollector, ParseError, Severity


class TestDiagnostic:
    def test_str_full(self):
        d = Diagnostic(
            severity=Severity.ERROR,
            message="bad field",
            file_path=Path("chip.svd"),
            element_path="GPIOA.MODER.MODE0",
            line=42,
        )
        s = str(d)
        assert "[ERROR]" in s
        assert "chip.svd:42" in s
        assert "(GPIOA.MODER.MODE0)" in s
        assert "bad field" in s

    def test_str_minimal(self):
        d = Diagnostic(severity=Severity.WARNING, message="oops")
        assert str(d) == "[WARNING] oops"


class TestDiagnosticCollector:
    def test_accumulation(self):
        c = DiagnosticCollector()
        c.info("note")
        c.warning("heads up")
        c.error("boom")
        assert len(c) == 3
        assert c.has_errors
        assert c.has_warnings

    def test_filter(self):
        c = DiagnosticCollector()
        c.warning("w1")
        c.warning("w2")
        c.error("e1")
        assert len(c.filter(Severity.WARNING)) == 2
        assert len(c.filter(Severity.ERROR)) == 1
        assert len(c.filter(Severity.INFO)) == 0

    def test_diagnostics_returns_copy(self):
        c = DiagnosticCollector()
        c.info("x")
        snapshot = c.diagnostics
        c.info("y")
        assert len(snapshot) == 1
        assert len(c.diagnostics) == 2

    def test_iterable(self):
        c = DiagnosticCollector()
        c.info("a")
        c.info("b")
        assert [d.message for d in c] == ["a", "b"]


class TestParseError:
    def test_carries_diagnostics(self):
        diags = [Diagnostic(severity=Severity.ERROR, message="fail")]
        err = ParseError("fatal", diagnostics=diags)
        assert str(err) == "fatal"
        assert len(err.diagnostics) == 1

    def test_default_empty_diagnostics(self):
        err = ParseError("oops")
        assert err.diagnostics == []
