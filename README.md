# svdgen

OSS hardware description generation engine — parse CMSIS-SVD, apply declarative patches, and render arbitrary text artifacts through Jinja templates.

```
SVD file → Parse → Normalize → Patch → Render → Write
```

Typical outputs: C register headers, Markdown documentation, Rust PAC fragments — anything expressible as text.

## Installation

```bash
pip install svdgen
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

**1. Create `svdgen.toml` in your project:**

```toml
[project]
name = "my-bsp"

[input]
svd = "STM32F407.svd"

[output]
dir = "generated"

[[targets]]
name        = "c_headers"
template    = "c_header/peripheral.h.j2"
output_path = "include/{{ peripheral.name | lower }}.h"
scope       = "peripheral"
```

**2. Generate:**

```bash
svdgen generate
```

This parses the SVD, normalizes the model, renders one C header per peripheral, and writes them to `generated/include/`.

## CLI

| Command | Description |
|---|---|
| `svdgen generate` | Run the full pipeline and write output files |
| `svdgen validate` | Validate config, inputs, and patches without writing files |
| `svdgen inspect [PERIPH[.REG[.FIELD]]]` | Inspect the normalized device model |
| `svdgen list peripherals\|registers\|fields\|targets` | List model elements or configured targets |
| `svdgen export-model` | Export the full normalized model as JSON |

All commands accept `--config / -c` (default `svdgen.toml`), `--dry-run`, `--verbose / -v`, and `--quiet / -q`.

## Patch Files

Patches are YAML files that modify the normalized model without editing the original SVD:

```yaml
- target: "GPIOA.MODER"
  set:
    description: "GPIO port mode register (corrected)"
    reset_value: 0xFFFFFFFF

- target: "GPIOA.MODER.MODE0"
  rename: "MODER0"

- target: "GPIOB"
  disable: true
```

Selectors are dot-separated paths: `PERIPH`, `PERIPH.REG`, or `PERIPH.REG.FIELD`.

## Python API

```python
import svdgen

config = svdgen.load_config("svdgen.toml")
result = svdgen.run(config)

# or step by step:
parse_result = svdgen.parse_svd("device.svd")
device       = svdgen.normalize(parse_result)
patch_set    = svdgen.load_patches("patches/fixups.yaml")
patched      = svdgen.apply_patches(device, patch_set).device
```

## Documentation

- [User Guide](docs/guide.md) — configuration reference, CLI reference, quick start
- [Patch Files](docs/patches.md) — YAML patch format, operations, cookbook
- [Template Authoring](docs/templates.md) — Jinja context, built-in filters, scope
- [Python API Reference](docs/python-api.md) — programmatic usage

## Examples

- [`examples/svdgen.toml`](examples/svdgen.toml) — minimal config
- [`examples/stm32_project/`](examples/stm32_project/) — realistic multi-target project with patches and a custom template

## License

Apache-2.0 — see [LICENSE](LICENSE).
