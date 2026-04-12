"""Tests for the pipeline orchestrator."""

from pathlib import Path

from svdgen.config import load_config
from svdgen.diagnostics import Severity
from svdgen.pipeline import run

FIXTURES = Path(__file__).parent / "fixtures"


def _write_config(tmp_path: Path, toml: str) -> Path:
    cfg = tmp_path / "svdgen.toml"
    cfg.write_text(toml)
    return cfg


class TestFullPipeline:
    def test_end_to_end(self, tmp_path: Path, minimal_svd: Path):
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "c_headers"
template = "c_header/peripheral.h.j2"
output_path = "include/{{{{ peripheral.name | lower }}}}.h"
scope = "peripheral"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success is True
        assert result.device is not None
        assert result.device.name == "TestDevice"
        assert len(result.artifacts) == 2
        assert (tmp_path / "gen" / "include" / "gpioa.h").exists()
        assert (tmp_path / "gen" / "include" / "gpiob.h").exists()

    def test_generated_content(self, tmp_path: Path, minimal_svd: Path):
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "hdr"
template = "c_header/peripheral.h.j2"
output_path = "{{{{ peripheral.name }}}}.h"
scope = "peripheral"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success
        content = (tmp_path / "gen" / "GPIOA.h").read_text()
        assert "#ifndef GPIOA_H" in content
        assert "GPIOA_MODER_MODE0_POS" in content


class TestPipelineWithPatches:
    def test_patches_applied(self, tmp_path: Path, minimal_svd: Path):
        patch_file = tmp_path / "fix.yaml"
        patch_file.write_text(
            '- target: "GPIOA.MODER"\n'
            '  set:\n'
            '    description: "patched description"\n'
        )
        tpl = tmp_path / "desc.j2"
        tpl.write_text(
            "{% for r in device.peripherals[0].registers %}"
            "{{ r.name }}:{{ r.description }}\n"
            "{% endfor %}"
        )
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[patches]
files = ["{patch_file}"]

[templates]
dirs = ["{tmp_path}"]

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "desc"
template = "desc.j2"
output_path = "desc.txt"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success
        content = (tmp_path / "gen" / "desc.txt").read_text()
        assert "patched description" in content


class TestDryRun:
    def test_no_files_written(self, tmp_path: Path, minimal_svd: Path):
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "hdr"
template = "c_header/peripheral.h.j2"
output_path = "{{{{ peripheral.name }}}}.h"
scope = "peripheral"
""")
        config = load_config(cfg_path)
        result = run(config, dry_run=True)
        assert result.success
        assert len(result.artifacts) == 2
        assert not (tmp_path / "gen").exists()


class TestErrorPropagation:
    def test_missing_svd_fails(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[input]
svd = "nonexistent.svd"

[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success is False
        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) > 0

    def test_bad_patch_target_non_fatal(
        self, tmp_path: Path, minimal_svd: Path
    ):
        patch_file = tmp_path / "bad.yaml"
        patch_file.write_text(
            '- target: "NONEXISTENT.REG"\n  set:\n    description: "x"\n'
        )
        tpl = tmp_path / "simple.j2"
        tpl.write_text("{{ device.name }}")
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[patches]
files = ["{patch_file}"]

[templates]
dirs = ["{tmp_path}"]

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "s"
template = "simple.j2"
output_path = "out.txt"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success is False
        assert result.device is not None


class TestMultipleTargets:
    def test_two_targets(self, tmp_path: Path, minimal_svd: Path):
        tpl_a = tmp_path / "a.j2"
        tpl_a.write_text("A:{{ device.name }}")
        tpl_b = tmp_path / "b.j2"
        tpl_b.write_text("B:{{ device.name }}")
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[templates]
dirs = ["{tmp_path}"]

[output]
dir = "{tmp_path / 'gen'}"

[[targets]]
name = "a"
template = "a.j2"
output_path = "a.txt"

[[targets]]
name = "b"
template = "b.j2"
output_path = "b.txt"
""")
        config = load_config(cfg_path)
        result = run(config)
        assert result.success
        assert (tmp_path / "gen" / "a.txt").read_text() == "A:TestDevice"
        assert (tmp_path / "gen" / "b.txt").read_text() == "B:TestDevice"
