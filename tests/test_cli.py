"""Tests for the CLI (typer-based)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from svdgen.cli import app

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures"


def _write_config(tmp_path: Path, toml: str) -> Path:
    cfg = tmp_path / "svdgen.toml"
    cfg.write_text(toml)
    return cfg


def _minimal_config(tmp_path: Path, minimal_svd: Path, **extra) -> Path:
    tpl_dir = extra.get("tpl_dir", "")
    tpl_dirs_line = f'dirs = ["{tpl_dir}"]' if tpl_dir else ""
    return _write_config(tmp_path, f"""
[input]
svd = "{minimal_svd}"

[output]
dir = "{tmp_path / 'gen'}"

[templates]
{tpl_dirs_line}

[[targets]]
name = "hdr"
template = "c_header/peripheral.h.j2"
output_path = "include/{{{{peripheral.name | lower}}}}.h"
scope = "peripheral"
""")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


class TestGenerate:
    def test_success(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["generate", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "Generated" in result.stdout
        assert (tmp_path / "gen" / "include" / "gpioa.h").exists()

    def test_dry_run(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["generate", "-c", str(cfg), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert not (tmp_path / "gen").exists()

    def test_missing_config(self, tmp_path: Path):
        result = runner.invoke(app, ["generate", "-c", str(tmp_path / "nope.toml")])
        assert result.exit_code == 2

    def test_missing_svd(self, tmp_path: Path):
        cfg = _write_config(tmp_path, """
[input]
svd = "nonexistent.svd"

[[targets]]
name = "x"
template = "t.j2"
output_path = "o.h"
""")
        result = runner.invoke(app, ["generate", "-c", str(cfg)])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["validate", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "passed" in result.stdout.lower()

    def test_invalid(self, tmp_path: Path):
        cfg = _write_config(tmp_path, """
[input]
svd = "nonexistent.svd"

[[targets]]
name = "x"
template = "t.j2"
output_path = "o.h"
""")
        result = runner.invoke(app, ["validate", "-c", str(cfg)])
        assert result.exit_code == 1
        assert "failed" in result.stdout.lower() or "error" in result.stdout.lower()


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


class TestInspect:
    def test_device_level(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "TestDevice" in result.stdout

    def test_peripheral(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "GPIOA", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "GPIOA" in result.stdout
        assert "0x40020000" in result.stdout

    def test_register(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "GPIOA.MODER", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "MODER" in result.stdout

    def test_field(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "GPIOA.MODER.MODE0", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "MODE0" in result.stdout
        assert "[1:0]" in result.stdout

    def test_json_output(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["inspect", "GPIOA", "-c", str(cfg), "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "GPIOA"

    def test_bad_selector(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "NOPE", "-c", str(cfg)])
        assert result.exit_code == 1

    def test_device_json(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["inspect", "-c", str(cfg), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "TestDevice"
        assert len(data["peripherals"]) == 2


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestList:
    def test_peripherals(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["list", "peripherals", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "GPIOA" in result.stdout
        assert "GPIOB" in result.stdout

    def test_peripherals_json(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "peripherals", "-c", str(cfg), "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"GPIOA", "GPIOB"}

    def test_registers(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "registers", "GPIOA", "-c", str(cfg)]
        )
        assert result.exit_code == 0
        assert "MODER" in result.stdout
        assert "ODR" in result.stdout

    def test_registers_json(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "registers", "GPIOA", "-c", str(cfg), "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        names = {d["name"] for d in data}
        assert "MODER" in names

    def test_fields(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "fields", "GPIOA.MODER", "-c", str(cfg)]
        )
        assert result.exit_code == 0
        assert "MODE0" in result.stdout
        assert "MODE1" in result.stdout

    def test_fields_json(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "fields", "GPIOA.MODER", "-c", str(cfg), "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        names = {d["name"] for d in data}
        assert names == {"MODE0", "MODE1"}

    def test_targets(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["list", "targets", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "hdr" in result.stdout

    def test_targets_json(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(
            app, ["list", "targets", "-c", str(cfg), "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["name"] == "hdr"


# ---------------------------------------------------------------------------
# export-model
# ---------------------------------------------------------------------------


class TestExportModel:
    def test_stdout(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["export-model", "-c", str(cfg)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "TestDevice"

    def test_to_file(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        out = tmp_path / "model.json"
        result = runner.invoke(
            app, ["export-model", "-c", str(cfg), "-o", str(out)]
        )
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert data["name"] == "TestDevice"
        assert len(data["peripherals"]) == 2

    def test_peripheral_details_in_export(self, tmp_path: Path, minimal_svd: Path):
        cfg = _minimal_config(tmp_path, minimal_svd)
        result = runner.invoke(app, ["export-model", "-c", str(cfg)])
        data = json.loads(result.stdout)
        gpioa = data["peripherals"][0]
        assert gpioa["name"] == "GPIOA"
        assert gpioa["base_address"] == 0x40020000
        assert len(gpioa["registers"]) == 2
