# svdgen Python API Reference

## Quick Start

```python
from pathlib import Path
from svdgen import parse_svd, normalize, render_targets, write_artifacts, OutputTarget, Scope

result = parse_svd("device.svd")
device = normalize(result)

targets = [OutputTarget(
    name="headers",
    template="c_header/peripheral.h.j2",
    output_path="{{ peripheral.name | lower }}.h",
    scope=Scope.PERIPHERAL,
)]

rendered = render_targets(device, targets)
write_artifacts(rendered.artifacts, Path("output"))
```

Or use `run()` for the full config-driven pipeline:

```python
from svdgen import load_config, run

config = load_config("svdgen.toml")
result = run(config)
# result.success, result.device, result.artifacts, result.diagnostics
```

---

## Parsing

### `parse_svd(path, *, validate=False) -> ParseResult`

Parse a CMSIS-SVD file into the raw device model with structured diagnostics.

| Parameter  | Type           | Description                                  |
|------------|----------------|----------------------------------------------|
| `path`     | `str \| Path`  | Path to the `.svd` file.                     |
| `validate` | `bool`         | Validate XML against the CMSIS-SVD schema.   |

**Returns:** `ParseResult` with `.device`, `.diagnostics`, `.source_map`.

**Raises:** `ParseError` on fatal failure, `FileNotFoundError` if missing.

### `ParseResult`

| Attribute     | Type              | Description                        |
|---------------|-------------------|------------------------------------|
| `device`      | `SVDDevice`       | Raw cmsis-svd device object.       |
| `diagnostics` | `list[Diagnostic]`| Warnings/errors from parsing.      |
| `source_map`  | `SourceMap`       | Maps element paths to source lines.|

---

## Normalization

### `normalize(result: ParseResult) -> Device`

Convert a raw `ParseResult` into the normalized, immutable `Device` model. Flattens clusters, computes absolute addresses, sorts elements deterministically, and cleans descriptions.

---

## Device Model

All model types are **frozen dataclasses** with **tuple** collections, making the tree fully immutable.

### `Device`

Root of the model. Key attributes:

| Attribute      | Type                   | Description                    |
|----------------|------------------------|--------------------------------|
| `name`         | `str`                  | Canonical device name.         |
| `description`  | `str \| None`          | Device description.            |
| `cpu`          | `CPU \| None`          | CPU metadata.                  |
| `peripherals`  | `tuple[Peripheral, ...]`| Sorted by base address.       |
| `width`        | `int \| None`          | Default register width (bits). |

### `Peripheral`

| Attribute       | Type                     | Description                     |
|-----------------|--------------------------|----------------------------------|
| `name`          | `str`                    | Canonical name.                  |
| `base_address`  | `int`                    | Base address.                    |
| `registers`     | `tuple[Register, ...]`   | Sorted by offset.               |
| `interrupts`    | `tuple[Interrupt, ...]`  | Associated interrupts.           |
| `enabled`       | `bool`                   | `False` if disabled by a patch.  |

### `Register`

| Attribute          | Type                  | Description                       |
|--------------------|-----------------------|-----------------------------------|
| `name`             | `str`                 | Canonical name.                   |
| `address_offset`   | `int`                 | Offset from peripheral base.      |
| `absolute_address` | `int`                 | Computed base + offset.           |
| `fields`           | `tuple[Field, ...]`   | Sorted by bit offset.             |
| `access`           | `AccessType \| None`  | Read/write permissions.           |
| `reset_value`      | `int \| None`         | Reset value.                      |

### `Field`

| Attribute     | Type                  | Description                              |
|---------------|-----------------------|------------------------------------------|
| `name`        | `str`                 | Canonical name.                          |
| `bit_offset`  | `int`                 | LSB position.                            |
| `bit_width`   | `int`                 | Width in bits.                           |
| `lsb`         | `int` (property)      | Same as `bit_offset`.                    |
| `msb`         | `int` (property)      | `bit_offset + bit_width - 1`.            |
| `bit_mask`    | `int` (property)      | Computed bitmask.                        |
| `access`      | `AccessType \| None`  | Field-level access override.             |

### Enums

- `AccessType`: `READ_ONLY`, `WRITE_ONLY`, `READ_WRITE`, `WRITE_ONCE`, `READ_WRITE_ONCE`
- `EndianType`: `LITTLE`, `BIG`, `SELECTABLE`, `OTHER`

---

## Patching

### `load_patches(path) -> PatchSet`

Load a YAML patch file. Raises `FileNotFoundError` or `ValueError` on invalid structure.

### `apply_patches(device, patches) -> PatchResult`

Apply a `PatchSet` to a `Device`, returning a new `PatchResult` with:

| Attribute     | Type               | Description                   |
|---------------|--------------------|-------------------------------|
| `device`      | `Device`           | Modified device (new object). |
| `diagnostics` | `list[Diagnostic]` | Errors/warnings from patching.|

The original device is never mutated.

---

## Configuration

### `load_config(path) -> ProjectConfig`

Load a TOML configuration file. All relative paths are resolved against the config file's directory.

### `validate_config(config) -> list[Diagnostic]`

Check file existence, valid scopes, duplicate target names, and template resolvability.

### `ProjectConfig`

| Attribute    | Type               | Description                  |
|--------------|--------------------|------------------------------|
| `input`      | `InputConfig`      | SVD file path.               |
| `patches`    | `PatchConfig`      | Patch file list.             |
| `templates`  | `TemplateConfig`   | Template search directories. |
| `output`     | `OutputConfig`     | Output dir and write policy. |
| `targets`    | `tuple[TargetConfig, ...]` | Output target defs.  |
| `generation` | `GenerationConfig` | Timestamp, etc.              |
| `validation` | `ValidationConfig` | Strict mode.                 |

---

## Rendering

### `render_targets(device, targets, ...) -> RenderResult`

Render all targets against the device model.

| Parameter         | Type                         | Description                           |
|-------------------|------------------------------|---------------------------------------|
| `device`          | `Device`                     | Normalized (optionally patched) model.|
| `targets`         | `list[OutputTarget]`         | Target definitions.                   |
| `template_dirs`   | `list[Path] \| None`        | Search paths; built-ins always added. |
| `custom_filters`  | `dict[str, Callable] \| None`| User-defined Jinja filters.          |
| `custom_globals`  | `dict[str, Any] \| None`    | User-defined Jinja globals.          |
| `extra_context`   | `dict[str, Any] \| None`    | Extra template context variables.     |

### `OutputTarget`

| Field        | Type        | Description                                          |
|-------------|-------------|------------------------------------------------------|
| `name`       | `str`       | Target identifier.                                   |
| `template`   | `str`       | Template filename (resolved from search path).       |
| `output_path`| `str`       | Jinja expression for the output path.                |
| `scope`      | `Scope`     | Iteration scope: `DEVICE`, `PERIPHERAL`, `REGISTER`. |
| `variables`  | `dict`      | Extra variables for this target's templates.         |

### `Scope`

- `Scope.DEVICE` — one artifact per device.
- `Scope.PERIPHERAL` — one artifact per enabled peripheral.
- `Scope.REGISTER` — one artifact per enabled register.

---

## Writing

### `write_artifacts(artifacts, output_dir, *, overwrite=True, skip_unchanged=True) -> list[Diagnostic]`

Write rendered artifacts to disk. Uses atomic writes (temp file + replace). Skips unchanged files when `skip_unchanged=True`. Blocks path traversal outside `output_dir`.

---

## Pipeline

### `run(config, *, dry_run=False, custom_filters=None, custom_globals=None) -> PipelineResult`

Execute the full pipeline: **parse → normalize → patch → render → write**.

| Parameter        | Type                          | Description                    |
|------------------|-------------------------------|--------------------------------|
| `config`         | `ProjectConfig`               | Loaded project configuration.  |
| `dry_run`        | `bool`                        | Render without writing.        |
| `custom_filters` | `dict[str, Callable] \| None` | User-defined Jinja filters.    |
| `custom_globals` | `dict[str, Any] \| None`     | User-defined Jinja globals.    |

### `PipelineResult`

| Attribute     | Type                  | Description                     |
|---------------|-----------------------|---------------------------------|
| `device`      | `Device \| None`      | Final device model.             |
| `artifacts`   | `list[RenderArtifact]`| Rendered artifacts.             |
| `diagnostics` | `list[Diagnostic]`    | All diagnostics from all stages.|
| `success`     | `bool`                | `True` if no errors.            |

---

## Export

### `device_to_dict(device) -> dict`

Recursively convert the frozen `Device` tree to JSON-serializable dicts. Enums become string values, tuples become lists.

### `export_json(device, file=None, *, indent=2) -> str | None`

Serialize to JSON. Returns a string if `file` is `None`, otherwise writes to the file object.

---

## Extension API

### Custom Jinja Filters

Pass a dict of `{name: callable}` to `render_targets()` or `run()`:

```python
from svdgen import run, load_config

def prefix_name(value, prefix="HAL"):
    return f"{prefix}_{value}"

config = load_config("svdgen.toml")
result = run(config, custom_filters={"prefix_name": prefix_name})
```

Custom filters are registered after built-ins, so they can override them.

### Custom Jinja Globals

Pass a dict of `{name: value}` to make constants or functions available in all templates:

```python
result = run(config, custom_globals={"copyright_year": 2026})
```

### Built-in Filters

All built-in filters are importable for composition:

```python
from svdgen import upper_snake, lower_snake, camel_case, hex_format
from svdgen import c_comment, c_line_comment, access_str, bit_range, pad
```

---

## Diagnostics

### `Diagnostic`

| Attribute      | Type            | Description                     |
|----------------|-----------------|---------------------------------|
| `severity`     | `Severity`      | `INFO`, `WARNING`, or `ERROR`.  |
| `message`      | `str`           | Human-readable message.         |
| `file_path`    | `Path \| None`  | Source file, if applicable.     |
| `element_path` | `str \| None`   | Model path (e.g. `GPIOA.MODER`).|
| `line`         | `int \| None`   | Source line number.             |

### `DiagnosticCollector`

Accumulates diagnostics during a pipeline stage. Provides `.info()`, `.warning()`, `.error()` shorthand, `.has_errors`, `.has_warnings`, `.filter(severity)`.

### `Severity`

Enum: `Severity.INFO`, `Severity.WARNING`, `Severity.ERROR`.
