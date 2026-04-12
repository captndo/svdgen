"""Tests for config loading and validation."""

from pathlib import Path

import pytest

from svdgen.config import ProjectConfig, load_config, validate_config
from svdgen.diagnostics import Severity

FIXTURES = Path(__file__).parent / "fixtures"


def _write_config(tmp_path: Path, toml: str, svd: bool = True) -> Path:
    """Write a TOML config and optionally a dummy SVD file."""
    cfg = tmp_path / "svdgen.toml"
    cfg.write_text(toml)
    if svd:
        (tmp_path / "device.svd").write_text("<device/>")
    return cfg


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_minimal(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[input]
svd = "device.svd"

[[targets]]
name = "hdr"
template = "t.j2"
output_path = "out.h"
""")
        config = load_config(cfg_path)
        assert isinstance(config, ProjectConfig)
        assert config.input.svd == tmp_path / "device.svd"
        assert len(config.targets) == 1
        assert config.targets[0].name == "hdr"

    def test_defaults(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "x"
template = "t.j2"
output_path = "o.h"
""")
        config = load_config(cfg_path)
        assert config.output.overwrite is True
        assert config.output.skip_unchanged is True
        assert config.generation.include_timestamp is False
        assert config.validation.strict is False

    def test_full_config(self, tmp_path: Path):
        (tmp_path / "tpl").mkdir()
        cfg_path = _write_config(tmp_path, """
[project]
name = "myproject"
description = "test"

[input]
svd = "device.svd"

[patches]
files = ["p1.yaml", "p2.yaml"]

[templates]
dirs = ["tpl"]

[output]
dir = "gen"
overwrite = false
skip_unchanged = false

[[targets]]
name = "a"
template = "t.j2"
output_path = "a.h"
scope = "peripheral"

[targets.variables]
prefix = "MY"

[generation]
include_timestamp = true

[validation]
strict = true
""")
        config = load_config(cfg_path)
        assert config.project_name == "myproject"
        assert len(config.patches.files) == 2
        assert config.patches.files[0] == tmp_path / "p1.yaml"
        assert config.output.overwrite is False
        assert config.targets[0].scope == "peripheral"
        assert config.targets[0].variables == {"prefix": "MY"}
        assert config.generation.include_timestamp is True
        assert config.validation.strict is True

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nope.toml")

    def test_paths_relative_to_config_dir(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        cfg_path = _write_config(sub, """
[input]
svd = "chip.svd"

[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
""", svd=False)
        (sub / "chip.svd").write_text("<device/>")
        config = load_config(cfg_path)
        assert config.input.svd == sub / "chip.svd"

    def test_missing_target_name(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
template = "t.j2"
output_path = "o.h"
""")
        with pytest.raises(ValueError, match="name"):
            load_config(cfg_path)

    def test_missing_target_template(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "x"
output_path = "o.h"
""")
        with pytest.raises(ValueError, match="template"):
            load_config(cfg_path)

    def test_empty_config(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, "")
        config = load_config(cfg_path)
        assert len(config.targets) == 0

    def test_multiple_targets(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "a"
template = "a.j2"
output_path = "a.h"

[[targets]]
name = "b"
template = "b.j2"
output_path = "b.h"
scope = "register"
""")
        config = load_config(cfg_path)
        assert len(config.targets) == 2
        assert config.targets[1].scope == "register"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_valid_config(self, tmp_path: Path, minimal_svd: Path):
        cfg_path = _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[[targets]]
name = "hdr"
template = "c_header/peripheral.h.j2"
output_path = "out.h"
""", svd=False)
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert errors == []

    def test_missing_svd(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[input]
svd = "nonexistent.svd"

[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
""", svd=False)
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert any("SVD" in e.message or "svd" in e.message.lower() for e in errors)

    def test_missing_patch_file(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[patches]
files = ["nope.yaml"]

[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
""")
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert any("nope.yaml" in e.message for e in errors)

    def test_invalid_scope(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
scope = "banana"
""")
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert any("banana" in e.message for e in errors)

    def test_duplicate_target_names(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "dup"
template = "a.j2"
output_path = "a.h"

[[targets]]
name = "dup"
template = "b.j2"
output_path = "b.h"
""")
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert any("dup" in e.message.lower() for e in errors)

    def test_missing_template_dir(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[templates]
dirs = ["nonexistent_dir"]

[[targets]]
name = "t"
template = "t.j2"
output_path = "o.h"
""")
        config = load_config(cfg_path)
        diags = validate_config(config)
        errors = [d for d in diags if d.severity == Severity.ERROR]
        assert any("nonexistent_dir" in e.message for e in errors)

    def test_unresolvable_template_warns(self, tmp_path: Path):
        cfg_path = _write_config(tmp_path, """
[[targets]]
name = "t"
template = "no_such_template.j2"
output_path = "o.h"
""")
        config = load_config(cfg_path)
        diags = validate_config(config)
        warnings = [d for d in diags if d.severity == Severity.WARNING]
        assert any("no_such_template" in w.message for w in warnings)
