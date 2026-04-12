"""Tests for the file writer — atomic writes, skip-unchanged, path safety."""

from pathlib import Path

from svdgen.diagnostics import Severity
from svdgen.render import RenderArtifact
from svdgen.writer import write_artifacts


def _art(path: str, content: str) -> RenderArtifact:
    return RenderArtifact(path=path, content=content, target_name="test")


class TestBasicWrite:
    def test_creates_file(self, tmp_path: Path):
        arts = [_art("out.h", "hello")]
        diags = write_artifacts(arts, tmp_path)
        assert (tmp_path / "out.h").read_text() == "hello"
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert errors == []

    def test_creates_subdirectories(self, tmp_path: Path):
        arts = [_art("include/chip/regs.h", "content")]
        write_artifacts(arts, tmp_path)
        assert (tmp_path / "include" / "chip" / "regs.h").read_text() == "content"

    def test_deterministic_order(self, tmp_path: Path):
        arts = [_art("z.h", "z"), _art("a.h", "a"), _art("m.h", "m")]
        write_artifacts(arts, tmp_path)
        assert (tmp_path / "a.h").exists()
        assert (tmp_path / "m.h").exists()
        assert (tmp_path / "z.h").exists()


class TestOverwrite:
    def test_overwrites_by_default(self, tmp_path: Path):
        (tmp_path / "out.h").write_text("old")
        arts = [_art("out.h", "new")]
        write_artifacts(arts, tmp_path)
        assert (tmp_path / "out.h").read_text() == "new"

    def test_skip_overwrite_when_disabled(self, tmp_path: Path):
        (tmp_path / "out.h").write_text("old")
        arts = [_art("out.h", "new")]
        diags = write_artifacts(arts, tmp_path, overwrite=False)
        assert (tmp_path / "out.h").read_text() == "old"
        warnings = [d for d in diags if d.severity == Severity.WARNING]
        assert len(warnings) == 1


class TestSkipUnchanged:
    def test_skip_when_identical(self, tmp_path: Path):
        (tmp_path / "out.h").write_text("same")
        arts = [_art("out.h", "same")]
        diags = write_artifacts(arts, tmp_path)
        infos = [d for d in diags if d.severity == Severity.INFO]
        assert len(infos) == 1
        assert "unchanged" in infos[0].message.lower()

    def test_write_when_different(self, tmp_path: Path):
        (tmp_path / "out.h").write_text("old")
        arts = [_art("out.h", "new")]
        diags = write_artifacts(arts, tmp_path)
        assert (tmp_path / "out.h").read_text() == "new"
        infos = [d for d in diags if d.severity == Severity.INFO]
        assert len(infos) == 0


class TestPathSafety:
    def test_path_traversal_blocked(self, tmp_path: Path):
        arts = [_art("../escape.h", "bad")]
        diags = write_artifacts(arts, tmp_path)
        assert not (tmp_path.parent / "escape.h").exists()
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "traversal" in errors[0].message.lower()
