# Template Authoring Guide

svdgen uses [Jinja2](https://jinja.palletsprojects.com/) templates to generate text artifacts. This guide covers the template context, built-in filters, and patterns for writing your own templates.

## Template context

Every template receives these variables. Additional variables are available depending on the target scope.

### Always available

| Variable               | Type     | Description                             |
|------------------------|----------|-----------------------------------------|
| `device`               | `Device` | The full normalized device model.       |
| `provenance.svdgen_version` | `str` | Generator version (e.g. `"0.1.0"`). |
| `provenance.input_source`   | `str` | Path to the input SVD file.        |
| `provenance.timestamp`      | `str` | ISO timestamp (only if enabled).   |

### Scope-dependent variables

| Scope        | Extra variables                  | Description                      |
|--------------|----------------------------------|----------------------------------|
| `device`     | —                                | Only `device` and `provenance`.  |
| `peripheral` | `peripheral`                     | Current `Peripheral` object.     |
| `register`   | `peripheral`, `register`         | Current `Peripheral` and `Register`. |

### Target variables

Any `[targets.variables]` entries in the config are also available:

```toml
[[targets]]
name = "headers"
template = "header.j2"
output_path = "{{ peripheral.name | lower }}.h"
scope = "peripheral"

[targets.variables]
copyright = "2026 My Company"
guard_prefix = "BSP"
```

```jinja
/* {{ copyright }} */
#ifndef {{ guard_prefix }}_{{ peripheral.name | upper_snake }}_H
```

## Device model reference

Templates access the model through frozen dataclass attributes. Here are the key types:

### `device`

```jinja
{{ device.name }}                    {# "STM32F407" #}
{{ device.description }}             {# "STM32F4xx MCU" #}
{{ device.vendor }}                  {# "STMicroelectronics" #}
{{ device.width }}                   {# 32 #}
{{ device.cpu.name }}                {# "CM4" #}
{{ device.cpu.endian.value }}        {# "little" #}
{{ device.peripherals | length }}    {# number of peripherals #}
```

### `peripheral`

```jinja
{{ peripheral.name }}                {# "GPIOA" #}
{{ peripheral.description }}         {# "General purpose I/O" #}
{{ peripheral.base_address }}        {# 1073872896 (integer) #}
{{ peripheral.base_address | hex }}  {# "0x40020000" #}
{{ peripheral.group_name }}          {# "GPIO" #}
{{ peripheral.derived_from }}        {# "GPIOA" or None #}
{{ peripheral.enabled }}             {# true #}
{% for reg in peripheral.registers if reg.enabled %}
  {{ reg.name }}
{% endfor %}
{% for irq in peripheral.interrupts %}
  {{ irq.name }}: {{ irq.value }}
{% endfor %}
```

### `register`

```jinja
{{ register.name }}                  {# "MODER" #}
{{ register.description }}           {# "GPIO port mode register" #}
{{ register.address_offset | hex(4) }} {# "0x0000" #}
{{ register.absolute_address | hex }}  {# "0x40020000" #}
{{ register.size }}                  {# 32 #}
{{ register.access }}                {# AccessType enum or None #}
{{ register.access | access_str }}   {# "RW" #}
{{ register.reset_value | hex }}     {# "0x00000000" #}
{% for field in register.fields if field.enabled %}
  {{ field.name }}: [{{ field.msb }}:{{ field.lsb }}]
{% endfor %}
```

### `field`

```jinja
{{ field.name }}                     {# "MODE0" #}
{{ field.description }}              {# "Port mode bits" #}
{{ field.bit_offset }}               {# 0 #}
{{ field.bit_width }}                {# 2 #}
{{ field.lsb }}                      {# 0 (property) #}
{{ field.msb }}                      {# 1 (property) #}
{{ field.bit_mask | hex }}           {# "0x00000003" #}
{{ field.access | access_str }}      {# "RW" #}
{% for evs in field.enumerated_values %}
  {% for ev in evs.values %}
    {{ ev.name }} = {{ ev.value }}   {# "Input = 0" #}
  {% endfor %}
{% endfor %}
```

## Built-in filters

All filters are registered automatically. They are also importable from the `svdgen` package for use in custom filter composition.

### Case conversion

| Filter         | Input            | Output             | Template alias   |
|----------------|------------------|--------------------|------------------|
| `upper_snake`  | `"MyPeripheral"` | `"MY_PERIPHERAL"`  | `upper_snake`    |
| `lower_snake`  | `"MyPeripheral"` | `"my_peripheral"`  | `lower_snake`    |
| `camel_case`   | `"my_reg"`       | `"MyReg"`          | `camel_case`     |

```jinja
{{ peripheral.name | upper_snake }}  → GPIOA
{{ peripheral.name | lower_snake }}  → gpioa
{{ register.name | camel_case }}     → Moder
```

### Numeric formatting

| Filter | Input  | Parameters     | Output          | Template alias |
|--------|--------|----------------|-----------------|----------------|
| `hex`  | `1024` | `width=8`      | `"0x00000400"`  | `hex`          |
| `hex`  | `255`  | `width=2`      | `"0xFF"`        | `hex`          |
| `hex`  | `None` | `width=8`      | `"0x????????"`  | `hex`          |

```jinja
{{ peripheral.base_address | hex }}       → 0x40020000
{{ register.address_offset | hex(4) }}    → 0x0000
{{ field.bit_mask | hex(8) }}             → 0x00000003
```

### Comment formatting

| Filter           | Input     | Output            |
|------------------|-----------|-------------------|
| `c_comment`      | `"text"`  | `"/* text */"`    |
| `c_comment`      | `None`    | `"/* */"`         |
| `c_line_comment` | `"text"`  | `"// text"`       |
| `c_line_comment` | `None`    | `"//"`            |
| `c_comment`      | `"a\nb"` | `"/*\n * a\n * b\n */"` |
| `c_line_comment` | `"a\nb"` | `"// a\n// b"` |

```jinja
{{ register.description | c_comment }}
{{ field.description | c_line_comment }}
```

### Access formatting

| Filter       | Input                    | Output |
|--------------|--------------------------|--------|
| `access_str` | `AccessType.READ_ONLY`   | `"RO"` |
| `access_str` | `AccessType.WRITE_ONLY`  | `"WO"` |
| `access_str` | `AccessType.READ_WRITE`  | `"RW"` |
| `access_str` | `AccessType.WRITE_ONCE`  | `"W1"` |
| `access_str` | `None`                   | `""`   |

### Field helpers

| Filter      | Input                        | Output     |
|-------------|------------------------------|------------|
| `bit_range` | Field with offset=0, width=2 | `"[1:0]"`  |

### Padding

| Filter | Input   | Parameters | Output              |
|--------|---------|------------|---------------------|
| `pad`  | `"FOO"` | `width=10` | `"FOO       "`      |

Useful for aligning `#define` columns:

```jinja
#define {{ (name ~ "_POS") | pad(48) }} ({{ field.bit_offset }})
```

## Output path expressions

The `output_path` field in a target is itself a Jinja expression rendered with the same context as the template:

```toml
# One file per peripheral
output_path = "include/{{ peripheral.name | lower }}.h"

# One file per register
output_path = "regs/{{ peripheral.name | lower }}/{{ register.name | lower }}.h"

# Device-level single file
output_path = "docs/{{ device.name | lower }}_map.md"
```

## Template includes

Templates can include other templates using Jinja's `{% include %}`:

```
templates/
├── base/
│   └── license_header.j2
└── c_header/
    └── peripheral.h.j2
```

```jinja
{# peripheral.h.j2 #}
{% include "base/license_header.j2" %}

#ifndef {{ peripheral.name | upper_snake }}_H
...
```

All directories in `[templates] dirs` plus the built-in template directory are searched.

## Walkthrough: built-in C header template

The built-in template at `c_header/peripheral.h.j2` generates one C header per peripheral. Here's how it works:

**Provenance header:**

```jinja
/**
 * @file {{ peripheral.name | lower }}.h
 * @brief {{ peripheral.description | default("Register definitions for " ~ peripheral.name, true) }}
 *
 * Generated by svdgen {{ provenance.svdgen_version }}
 * Source: {{ provenance.input_source }}
 *
 * DO NOT EDIT — this file is auto-generated.
 */
```

**Include guard:**

```jinja
#ifndef {{ peripheral.name | upper_snake }}_H
#define {{ peripheral.name | upper_snake }}_H
...
#endif /* {{ peripheral.name | upper_snake }}_H */
```

**Base address and register offsets:**

```jinja
#define {{ peripheral.name | upper_snake }}_BASE  {{ peripheral.base_address | hex(8) }}

{% for reg in peripheral.registers if reg.enabled %}
#define {{ peripheral.name | upper_snake }}_{{ reg.name | upper_snake }}_OFFSET  {{ reg.address_offset | hex(4) }}
{% endfor %}
```

**Field definitions with aligned columns:**

```jinja
{% set prefix = peripheral.name | upper_snake ~ "_" ~ reg.name | upper_snake ~ "_" ~ field.name | upper_snake %}
#define {{ (prefix ~ "_POS") | pad(48) }} ({{ field.bit_offset }})
#define {{ (prefix ~ "_MSK") | pad(48) }} ({{ field.bit_mask | hex(8) }})
#define {{ (prefix ~ "_WIDTH") | pad(48) }} ({{ field.bit_width }})
```

**Enumerated values:**

```jinja
{% for evs in field.enumerated_values %}
{% for ev in evs.values %}
{% if ev.value is not none %}
#define {{ (prefix ~ "_" ~ ev.name | upper_snake) | pad(48) }} ({{ ev.value | hex(8) }} << {{ field.bit_offset }})  {{ ev.description | c_line_comment }}
{% endif %}
{% endfor %}
{% endfor %}
```

## Walkthrough: writing a Markdown register map

Here's a complete device-scope template that generates a register map document:

```jinja
# {{ device.name }} Register Map

{{ device.description }}

Generated by svdgen {{ provenance.svdgen_version }} from {{ provenance.input_source }}.

{% for p in device.peripherals if p.enabled %}
## {{ p.name }}

{{ p.description }}

**Base address:** {{ p.base_address | hex }}

| Register | Offset | Access | Description |
|----------|--------|--------|-------------|
{% for r in p.registers if r.enabled %}
| {{ r.name }} | {{ r.address_offset | hex(4) }} | {{ r.access | access_str }} | {{ r.description | default("") }} |
{% endfor %}

{% for r in p.registers if r.enabled %}
{% if r.fields %}
### {{ p.name }}.{{ r.name }}

{{ r.description }}

| Field | Bits | Access | Description |
|-------|------|--------|-------------|
{% for f in r.fields if f.enabled %}
| {{ f.name }} | {{ f | bit_range }} | {{ f.access | access_str }} | {{ f.description | default("") }} |
{% endfor %}
{% endif %}

{% endfor %}
{% endfor %}
```

Save this as `templates/regmap.md.j2` and add a target:

```toml
[[targets]]
name = "regmap"
template = "regmap.md.j2"
output_path = "docs/{{ device.name | lower }}_registers.md"
scope = "device"
```

## Custom filters and globals

### Via Python API

```python
from svdgen import render_targets

def prefix_name(value, prefix="HAL"):
    return f"{prefix}_{value.upper()}"

result = render_targets(
    device, targets, [template_dir],
    custom_filters={"prefixed": prefix_name},
    custom_globals={"project_name": "My BSP"},
)
```

### Composing with built-in filters

```python
from svdgen import upper_snake

def hal_name(value):
    return f"HAL_{upper_snake(value)}"
```

Custom filters override built-in filters if they share the same name.

## Tips

- **Use `default()` for optional fields.** Descriptions can be `None`:
  ```jinja
  {{ register.description | default("No description", true) }}
  ```

- **Filter disabled elements.** Use `if reg.enabled` / `if field.enabled` in loops to skip disabled elements (the scope iteration does this automatically, but within templates you may loop over nested elements manually).

- **Use `~ ` for string concatenation.** Jinja uses `~` not `+`:
  ```jinja
  {{ peripheral.name ~ "_" ~ register.name }}
  ```

- **Access enum values.** Access types are Python enums. Use the `access_str` filter for short labels, or `.value` for the full string:
  ```jinja
  {{ register.access | access_str }}      → "RW"
  {{ register.access.value }}             → "read-write"
  ```

- **Provenance for CI.** Include the generator version and source path so generated files are traceable:
  ```jinja
  /* Generated by svdgen {{ provenance.svdgen_version }} from {{ provenance.input_source }} */
  ```
