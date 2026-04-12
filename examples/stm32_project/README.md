# STM32 BSP Example Project

A self-contained example showing a realistic svdgen workflow:

- Parses a CMSIS-SVD file (the minimal test fixture)
- Applies vendor fixup patches (rename, set, disable)
- Generates two different outputs from the same model:
  - **C headers** — one per peripheral using the built-in template
  - **Markdown register map** — a custom template for documentation

## Project structure

```
stm32_project/
├── svdgen.toml              # Project configuration
├── patches/
│   └── fixups.yaml          # Vendor SVD fixups
├── templates/
│   └── regmap.md.j2         # Custom Markdown template
└── output/                  # Generated (after running)
    ├── include/
    │   └── gpioa.h          # C header (GPIOB disabled by patch)
    └── docs/
        └── register_map.md  # Markdown register map
```

## Running

From the repository root:

```bash
# Generate all outputs
svdgen generate -c examples/stm32_project/svdgen.toml

# Validate without writing
svdgen validate -c examples/stm32_project/svdgen.toml

# Inspect the patched model
svdgen inspect GPIOA -c examples/stm32_project/svdgen.toml

# List peripherals (GPIOB will be absent — it's disabled)
svdgen list peripherals -c examples/stm32_project/svdgen.toml

# Export the full model as JSON
svdgen export-model -c examples/stm32_project/svdgen.toml -o model.json
```

Or from within this directory:

```bash
cd examples/stm32_project
svdgen generate
```

## What the patches do

1. **Improve descriptions** — GPIOA.MODER and GPIOA.ODR get better descriptions
2. **Fix reset value** — GPIOA.ODR reset value is explicitly set
3. **Rename a field** — GPIOA.MODER.MODE1 → MODER1 (project naming convention)
4. **Disable a peripheral** — GPIOB is disabled (not used on this board)

After patching, only GPIOA appears in the generated output.

## Outputs

After running `svdgen generate`, the `output/` directory will contain:

- `include/gpioa.h` — C header with register offsets, addresses, and field definitions
- `docs/register_map.md` — Markdown documentation with tables for every register and field
