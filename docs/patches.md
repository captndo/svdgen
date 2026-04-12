# Patch Files

Patch files are YAML documents that declaratively modify the normalized device model after parsing, without editing the original SVD file.

## File format

A patch file is a YAML list. Each entry has a `target` selector and exactly one action (`set`, `rename`, `remove`, or `disable`):

```yaml
- target: "GPIOA.MODER"
  set:
    description: "GPIO port mode register"

- target: "GPIOA.MODER.MODE0"
  rename: "MODER0"

- target: "GPIOA.OLD_REG"
  remove: true

- target: "GPIOA.UNUSED_REG"
  disable: true
```

## Selectors

Selectors are dot-separated paths that identify a node in the device model hierarchy:

| Selector             | Targets                             |
|----------------------|-------------------------------------|
| `GPIOA`              | Peripheral named GPIOA              |
| `GPIOA.MODER`        | Register MODER within GPIOA        |
| `GPIOA.MODER.MODE0`  | Field MODE0 within GPIOA.MODER     |

Selectors match against the **canonical name** of each element (the normalized name, not the raw SVD name). Selectors are case-sensitive.

If a selector does not match any element, an error diagnostic is produced and the patch is skipped.

## Operations

### `set` — modify properties

Replace one or more properties of a peripheral, register, or field.

```yaml
- target: "GPIOA.MODER"
  set:
    description: "GPIO port mode register (corrected)"
    reset_value: 0xFFFFFFFF
```

**Settable properties by target level:**

| Level      | Settable properties                                           |
|------------|---------------------------------------------------------------|
| Peripheral | `description`, `group_name`                                  |
| Register   | `description`, `access`, `reset_value`, `reset_mask`, `size`, `display_name` |
| Field      | `description`, `access`, `bit_offset`, `bit_width`           |

**Access values:** `read-only`, `write-only`, `read-write`, `write-once`, `read-write-once`.

```yaml
- target: "GPIOA.MODER"
  set:
    access: "read-write"

- target: "GPIOA.MODER.MODE0"
  set:
    access: "read-only"
    description: "Port mode bits (read-only on this variant)"
```

Setting an unsupported property or an invalid access value produces an error diagnostic.

### `rename` — change the canonical name

Rename a peripheral, register, or field.

```yaml
# Rename a field
- target: "GPIOA.MODER.MODE0"
  rename: "MODER_BIT0"

# Rename a register
- target: "GPIOA.MODERX"
  rename: "MODER"

# Rename a peripheral
- target: "GPIO_A"
  rename: "GPIOA"
```

After a rename, subsequent patches must use the **new name** in their selectors.

### `remove` — delete a node

Remove a peripheral, register, or field from the model entirely.

```yaml
- target: "GPIOA.RESERVED_REG"
  remove: true

- target: "GPIOA.MODER.RESERVED_BITS"
  remove: true

- target: "UNUSED_PERIPH"
  remove: true
```

Removed elements are deleted from the model and will not appear in any rendered output.

### `disable` — soft-remove a node

Disable a peripheral, register, or field. Disabled elements remain in the model (with `enabled = false`) but are skipped by the render engine's scope iteration.

```yaml
- target: "GPIOB"
  disable: true

- target: "GPIOA.ODR"
  disable: true
```

Use `disable` instead of `remove` when you want the element to remain accessible to templates that explicitly check for it, but excluded from default iteration.

## Ordering

### Within a file

Patches are applied top-to-bottom. Later entries override earlier ones:

```yaml
# First set a description...
- target: "GPIOA.MODER"
  set:
    description: "Original description"

# ...then override it
- target: "GPIOA.MODER"
  set:
    description: "Final description"
```

The register's description will be "Final description".

### Across files

When multiple patch files are listed in the config, they are applied in the order specified:

```toml
[patches]
files = [
    "patches/vendor_fixups.yaml",   # applied first
    "patches/project_overrides.yaml", # applied second, can override
]
```

### Rename interactions

If you rename an element, subsequent patches must use the new name:

```yaml
# File 1: rename
- target: "GPIOA.MODE_REG"
  rename: "MODER"

# File 2: set (uses new name)
- target: "GPIOA.MODER"
  set:
    description: "Renamed and updated"
```

## Error handling

| Condition                        | Result                       |
|----------------------------------|------------------------------|
| Selector matches nothing         | Error diagnostic, patch skipped |
| Invalid property name in `set`   | Error diagnostic             |
| Invalid access value in `set`    | Error diagnostic             |
| Multiple actions in one entry    | Load-time error              |
| Missing `target` field           | Load-time error              |
| No action specified              | Load-time error              |
| YAML syntax error                | Load-time exception          |

All errors produce structured `Diagnostic` objects with the patch file path, entry index, and a descriptive message.

## Common vendor fixup patterns

### Fix incorrect access types

Many vendor SVDs mark registers as `read-write` when they should be `read-only`:

```yaml
- target: "ADC1.DR"
  set:
    access: "read-only"

- target: "RCC.CFGR.SWS"
  set:
    access: "read-only"
```

### Improve missing descriptions

```yaml
- target: "GPIOA.BSRR"
  set:
    description: "GPIO port bit set/reset register"

- target: "GPIOA.BSRR.BS0"
  set:
    description: "Set bit 0"
```

### Fix wrong reset values

```yaml
- target: "FLASH.ACR"
  set:
    reset_value: 0x00000030
```

### Rename vendor-prefixed fields

Some vendors prefix fields with the register name:

```yaml
- target: "GPIOA.MODER.MODER0"
  rename: "MODE0"

- target: "GPIOA.MODER.MODER1"
  rename: "MODE1"
```

### Disable unused peripherals

```yaml
- target: "USB_OTG_FS"
  disable: true

- target: "ETHERNET"
  disable: true
```

### Layered patches for multi-device projects

```toml
[patches]
files = [
    "patches/stm32f4_common.yaml",    # fixes shared across the family
    "patches/stm32f407_specific.yaml", # device-specific overrides
]
```

## Programmatic patches

Patches can also be constructed in Python code without YAML:

```python
from svdgen.patch import Patch, PatchSet, apply_patches

patches = PatchSet(patches=(
    Patch(target="GPIOA.MODER", set_={"description": "Updated"}),
    Patch(target="GPIOB", disable=True),
))
result = apply_patches(device, patches)
device = result.device
```

This is useful for build scripts that need to generate patches dynamically.
