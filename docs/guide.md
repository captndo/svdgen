# svdgen User Guide

## Overview

**svdgen** is a command-line tool and Python library that ingests CMSIS-SVD hardware description files, applies declarative patches, and generates arbitrary text artifacts through Jinja templates.

The core pipeline:

```
SVD file → Parse → Normalize → Patch → Render → Write
```

Typical outputs include C register headers, Markdown documentation, Rust PAC fragments — anything expressible as text.

## Installation

From the repository root (editable install for development):

```bash
pip install -e ".[dev]"
```

This installs the `svdgen` command and the `svdgen` Python package.

## Quick Start

### 1. Create a project config

Create `svdgen.toml` in your project directory:

```toml
[project]
name = "my-bsp"
description = "Board support package for STM32F4"

[input]
svd = "STM32F407.svd"

[output]
dir = "generated"

[[targets]]
name = "c_headers"
template = "c_header/peripheral.h.j2"
output_path = "include/{{ peripheral.name | lower }}.h"
scope = "peripheral"
```

### 2. Generate

```bash
svdgen generate
```

This parses the SVD, normalizes the model, renders one C header per peripheral, and writes them to `generated/include/`.

### 3. Validate without writing

```bash
svdgen validate
```

Runs the full pipeline in dry-run mode and reports any errors or warnings without creating files.

### 4. Inspect the model

```bash
svdgen inspect                    # device overview
svdgen inspect GPIOA              # peripheral details
svdgen inspect GPIOA.MODER        # register details
svdgen inspect GPIOA.MODER.MODE0  # field details
svdgen inspect GPIOA --json       # machine-readable JSON
```

### 5. List elements

```bash
svdgen list peripherals
svdgen list registers GPIOA
svdgen list fields GPIOA.MODER
svdgen list targets
```

### 6. Export the full model

```bash
svdgen export-model -o model.json
```

---

## Project Configuration (TOML)

All paths in the config file are resolved relative to the directory containing the TOML file.

### `[project]`

Optional project metadata.

| Key           | Type   | Default | Description            |
|---------------|--------|---------|------------------------|
| `name`        | string | `""`    | Project name.          |
| `description` | string | `""`    | Project description.   |

```toml
[project]
name = "my-bsp"
description = "Register definitions for STM32F4xx"
```

### `[input]`

The SVD source file.

| Key  | Type   | Default        | Description        |
|------|--------|----------------|--------------------|
| `svd`| string | `"device.svd"` | Path to `.svd` file.|

```toml
[input]
svd = "vendor/STM32F407.svd"
```

### `[patches]`

Optional patch files applied in order after normalization.

| Key     | Type          | Default | Description                     |
|---------|---------------|---------|---------------------------------|
| `files` | list of paths | `[]`    | YAML patch files, applied in order.|

```toml
[patches]
files = [
    "patches/rename_fields.yaml",
    "patches/fix_access.yaml",
]
```

Patch files are applied sequentially — later files can override earlier ones. See [Patch Files](patches.md) for the YAML format.

### `[templates]`

Directories to search for Jinja templates. The built-in template directory is always appended as a fallback.

| Key    | Type          | Default | Description             |
|--------|---------------|---------|-------------------------|
| `dirs` | list of paths | `[]`    | Template search paths.  |

```toml
[templates]
dirs = ["templates"]
```

### `[output]`

Controls where and how files are written.

| Key              | Type   | Default    | Description                                    |
|------------------|--------|------------|------------------------------------------------|
| `dir`            | string | `"output"` | Root directory for generated files.            |
| `overwrite`      | bool   | `true`     | Overwrite existing files.                      |
| `skip_unchanged` | bool   | `true`     | Skip writing when content hasn't changed.      |

```toml
[output]
dir = "generated"
overwrite = true
skip_unchanged = true
```

`skip_unchanged = true` avoids unnecessary file modifications, which reduces build-system churn and keeps file timestamps stable in CI.

### `[[targets]]`

Each `[[targets]]` entry defines one output artifact (or set of artifacts). You can have as many as needed.

| Key           | Type   | Required | Default    | Description                                |
|---------------|--------|----------|------------|--------------------------------------------|
| `name`        | string | yes      | —          | Unique identifier for this target.         |
| `template`    | string | yes      | —          | Template filename (resolved from search path).|
| `output_path` | string | yes      | —          | Output path (Jinja expression).            |
| `scope`       | string | no       | `"device"` | Iteration scope: `device`, `peripheral`, or `register`.|
| `variables`   | table  | no       | `{}`       | Extra variables available in this target's templates.|

```toml
[[targets]]
name = "c_headers"
template = "c_header/peripheral.h.j2"
output_path = "include/{{ peripheral.name | lower }}.h"
scope = "peripheral"

[[targets]]
name = "regmap"
template = "regmap.md.j2"
output_path = "docs/{{ device.name | lower }}_registers.md"
scope = "device"

[targets.variables]
copyright = "2026 My Company"
```

**Scope behaviour:**

| Scope        | Iteration                                 | Template context          |
|--------------|-------------------------------------------|---------------------------|
| `device`     | One artifact per run.                     | `device`                  |
| `peripheral` | One artifact per enabled peripheral.      | `device`, `peripheral`    |
| `register`   | One artifact per enabled register.        | `device`, `peripheral`, `register` |

The `output_path` is itself a Jinja expression rendered with the same context as the template, so you can use filters and variables in the path.

### `[generation]`

| Key                 | Type | Default | Description                              |
|---------------------|------|---------|------------------------------------------|
| `include_timestamp` | bool | `false` | Add generation timestamp to provenance.  |

```toml
[generation]
include_timestamp = false
```

Setting this to `true` adds a `provenance.timestamp` variable to templates, but breaks deterministic output.

### `[validation]`

| Key      | Type | Default | Description                                |
|----------|------|---------|--------------------------------------------|
| `strict` | bool | `false` | Validate SVD XML against the CMSIS schema. |

```toml
[validation]
strict = true
```

### Full example

```toml
[project]
name = "my-bsp"
description = "STM32F4 board support"

[input]
svd = "vendor/STM32F407.svd"

[patches]
files = ["patches/fixups.yaml"]

[templates]
dirs = ["templates"]

[output]
dir = "generated"
overwrite = true
skip_unchanged = true

[[targets]]
name = "c_headers"
template = "c_header/peripheral.h.j2"
output_path = "include/{{ peripheral.name | lower }}.h"
scope = "peripheral"

[[targets]]
name = "register_map"
template = "regmap.md.j2"
output_path = "docs/registers.md"
scope = "device"

[generation]
include_timestamp = false

[validation]
strict = false
```

---

## CLI Reference

All commands accept `--config / -c` (default `svdgen.toml`), `--verbose / -v`, and `--quiet / -q`.

### Exit codes

| Code | Meaning                                      |
|------|----------------------------------------------|
| `0`  | Success.                                     |
| `1`  | Validation or generation failure.            |
| `2`  | Runtime error (missing config, broken TOML). |

### `svdgen generate`

Run the full pipeline and write output files.

```bash
svdgen generate                        # default config
svdgen generate -c project.toml        # custom config path
svdgen generate --dry-run              # render without writing
svdgen generate -v                     # show all diagnostics
```

### `svdgen validate`

Validate everything without writing files. Useful in CI.

```bash
svdgen validate
svdgen validate -c project.toml
```

### `svdgen inspect`

Inspect the parsed and normalized model.

```bash
svdgen inspect                         # device-level summary
svdgen inspect GPIOA                   # peripheral
svdgen inspect GPIOA.MODER            # register
svdgen inspect GPIOA.MODER.MODE0      # field
svdgen inspect GPIOA --json           # JSON output
```

### `svdgen list`

List available elements or configured targets.

```bash
svdgen list peripherals                # all peripherals
svdgen list registers GPIOA            # registers in GPIOA
svdgen list fields GPIOA.MODER        # fields in GPIOA.MODER
svdgen list targets                    # configured output targets
svdgen list peripherals --json        # JSON output
```

### `svdgen export-model`

Export the full normalized (and patched) model as JSON.

```bash
svdgen export-model                    # to stdout
svdgen export-model -o model.json     # to file
```

---

## Further Reading

- [Pipeline Architecture](pipeline.md) — how the pipeline stages work and why
- [Patch Files](patches.md) — YAML patch format, operations, and cookbook
- [Template Authoring](templates.md) — writing Jinja templates, filters, context
- [Python API Reference](python-api.md) — programmatic usage
