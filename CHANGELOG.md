# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-12

### Added

- CMSIS-SVD parsing via `cmsis-svd`, normalized into a stable immutable dataclass model (`Device`, `Peripheral`, `Register`, `Field`, `Interrupt`, `AddressBlock`, `EnumeratedValueSet`)
- Patch system (YAML): `rename`, `set`, `remove`, `disable` operations targeting nodes by dot-separated selector (`PERIPH`, `PERIPH.REG`, `PERIPH.REG.FIELD`)
- Jinja2 template rendering with `device`, `peripheral`, and `register` scope iteration
- Built-in C header template (`c_header/peripheral.h.j2`)
- Built-in Jinja filters: `upper_snake`, `lower_snake`, `camel_case`, `hex`, `c_comment`, `c_line_comment`, `access_str`, `bit_range`, `pad`
- Declarative TOML project configuration (`svdgen.toml`) with schema validation
- CLI commands: `generate`, `validate`, `inspect`, `list`, `export-model`
- Python API: `parse_svd`, `normalize`, `load_patches`, `apply_patches`, `render_targets`, `write_artifacts`, `run`
- JSON model export (`export-model` command and `export_json` API)
- Dry-run mode (`--dry-run`) — renders without writing files
- Output path collision detection at render time
- Path traversal protection in the file writer
- Deterministic, atomic file writes with skip-unchanged optimisation
- Provenance metadata injected into template context (`svdgen_version`, `input_source`, optional `timestamp`)
- Custom Jinja filter and global registration via the Python API
- Structured diagnostics (`Diagnostic`, `DiagnosticCollector`) with `ERROR`, `WARNING`, `INFO` severity levels throughout all pipeline stages
- CLI exit codes: `0` success, `1` validation/generation failure, `2` runtime error
