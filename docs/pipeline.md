# Pipeline Architecture

## What is the pipeline?

The svdgen pipeline is the sequential execution model at the heart of the tool. A successful full generation run — via `svdgen generate` or the Python API's `run()` — validates configuration, then executes five stages in order. Dry runs skip writing, and the stage APIs can be called independently:

```
┌─────────┐    ┌───────────┐    ┌─────────┐    ┌────────┐    ┌─────────┐
│  Parse   │───▶│ Normalize │───▶│  Patch  │───▶│ Render │───▶│  Write  │
│          │    │           │    │         │    │        │    │         │
│ SVD XML  │    │ Immutable │    │ Modified│    │Artifact│    │ Files   │
│ → raw    │    │ Device    │    │ Device  │    │ objects│    │ on disk │
│ device   │    │ model     │    │ model   │    │        │    │         │
└─────────┘    └───────────┘    └─────────┘    └────────┘    └─────────┘
   SVDDevice       Device          Device      RenderArtifact[]  files
```

Each stage has a clear input type, output type, and responsibility. This separation makes the system testable, extensible, and debuggable.

## Why each stage exists

### Parse

**Input:** SVD file path → **Output:** `ParseResult` (raw `SVDDevice` + diagnostics + source map)

The parse stage ingests a CMSIS-SVD XML file using the `cmsis-svd` library. It exists as a separate stage to:

- **Isolate upstream format quirks.** Vendor SVD files are inconsistent — wrong access types, missing fields, non-standard extensions. The parser captures warnings from `cmsis-svd` as structured `Diagnostic` objects instead of letting them print to stdout.
- **Build a source map.** A secondary `lxml` pass records which XML line each element came from, enabling traceability from generated output back to the exact SVD source line.
- **Fail fast.** Malformed XML produces a `ParseError` with accumulated diagnostics, stopping the pipeline before any further work. Schema validation is optional and enabled with `validate=True`.

```python
from svdgen import parse_svd

result = parse_svd("device.svd", validate=True)
# result.device     — raw SVDDevice from cmsis-svd
# result.diagnostics — warnings/errors from parsing
# result.source_map  — element paths → source file:line
```

### Normalize

**Input:** `ParseResult` → **Output:** `Device` (immutable model)

Normalization converts the raw, mutable `cmsis-svd` objects into svdgen's own immutable data model. This stage exists because:

- **Stable API contract.** Templates, patches, and the Python API all work against `svdgen.model.Device`, not the upstream `cmsis-svd` types. This insulates users from upstream library changes.
- **Canonical ordering.** Peripherals are sorted by base address, registers by offset, fields by bit offset. This guarantees deterministic output regardless of SVD element ordering.
- **Computed values.** Absolute register addresses (`base_address + offset`) are computed once. Field bitmasks are available as properties. Descriptions are cleaned (whitespace collapsed).
- **Immutability.** All model types are frozen dataclasses with tuple collections. This means the model cannot be accidentally mutated — patches produce new objects via `dataclasses.replace()`.

```python
from svdgen import normalize

device = normalize(result)
# device.name              — "STM32F407"
# device.peripherals[0]    — first Peripheral (by base address)
# device.peripherals[0].registers[0].fields[0].bit_mask — computed
```

### Patch

**Input:** `Device` + `PatchSet` → **Output:** `PatchResult` (new `Device` + diagnostics)

The patch stage applies declarative modifications to the normalized model. It exists because:

- **Don't edit vendor SVDs.** Vendor SVD files are often wrong — missing descriptions, incorrect access types, deprecated registers. Patches let you fix these without modifying the original file, keeping it updatable.
- **Deterministic and auditable.** Patches are YAML files checked into version control. The application order is explicit (file order, then entry order within a file). Later patches override earlier ones.
- **Immutability preserved.** Each patch operation rebuilds only the affected branch of the model tree using `dataclasses.replace()`. The original device is never mutated.

Supported operations: `set`, `rename`, `remove`, `disable`.

```python
from svdgen import load_patches, apply_patches

patches = load_patches("fixups.yaml")
result = apply_patches(device, patches)
# result.device      — new Device with patches applied
# result.diagnostics — warnings/errors (e.g. selector not found)
```

Multiple patch files are applied sequentially:

```python
for path in patch_files:
    patches = load_patches(path)
    result = apply_patches(device, patches)
    device = result.device
```

### Render

**Input:** `Device` + `OutputTarget[]` → **Output:** `RenderResult` (artifacts + diagnostics)

The render stage evaluates Jinja templates against the device model and produces in-memory artifacts. It exists as a separate stage to:

- **Decouple generation from I/O.** Artifacts are `RenderArtifact` objects (path + content strings) that can be inspected, filtered, or modified before writing. The `--dry-run` flag uses this: render runs, write doesn't.
- **Scope iteration.** A single target definition with `scope = "peripheral"` automatically iterates over all enabled peripherals, rendering one artifact per peripheral. Register scope does the same per-register.
- **Path collision detection.** If two targets or scope iterations produce the same output path, an error diagnostic is emitted before any files are written.
- **Extension points.** Custom Jinja filters and globals are injected here.

```python
from svdgen import render_targets, OutputTarget, Scope

targets = [
    OutputTarget(
        name="headers",
        template="c_header/peripheral.h.j2",
        output_path="{{ peripheral.name | lower }}.h",
        scope=Scope.PERIPHERAL,
    ),
]
result = render_targets(device, targets)
# result.artifacts    — list of RenderArtifact(path, content, target_name)
# result.diagnostics  — template errors, collisions
```

### Write

**Input:** `RenderArtifact[]` + output directory → **Output:** files on disk + diagnostics

The write stage persists rendered artifacts to the filesystem. It exists as a separate stage to:

- **Atomic writes.** Each file is written to a temporary file first, then atomically replaced via `os.replace()`. This prevents partial writes on failure.
- **Skip-unchanged.** When `skip_unchanged=True`, files whose content hasn't changed are not rewritten. This preserves file timestamps, which matters for build systems that use mtime for incremental compilation.
- **Deterministic ordering.** Artifacts are written in sorted path order, regardless of rendering order.

```python
from svdgen import write_artifacts

diagnostics = write_artifacts(result.artifacts, "output/")
```

## Diagnostics flow

Configuration validation, parsing, patching, rendering, and writing produce `Diagnostic` objects that accumulate into the final result. Normalization returns a `Device` directly. Each diagnostic has:

- **Severity:** `INFO`, `WARNING`, or `ERROR`
- **Message:** human-readable description
- **File path:** source file, if applicable
- **Element path:** model path like `GPIOA.MODER.MODE0`
- **Line number:** SVD source line, if available

The pipeline orchestrator collects diagnostics from all stages:

```
Config diagnostics    ──┐
Parse diagnostics     ──┤
Patch diagnostics     ──┼──▶ PipelineResult.diagnostics
Render diagnostics    ──┤
Write diagnostics     ──┘
```

**Short-circuiting:** Configuration errors, parse failures, patch errors, and render errors stop the pipeline before the next stage. The writer collects diagnostics while processing artifacts; write errors make the final result unsuccessful.

**Strict mode:** When `[validation] strict = true`, the SVD XML is validated against the CMSIS schema during parsing. Schema violations become errors instead of being silently tolerated.

## Running the pipeline

### Full pipeline via CLI

```bash
# Generate (parse → normalize → patch → render → write)
svdgen generate

# Validate (parse → normalize → patch → render, no write)
svdgen validate

# Dry run (same as validate but reports what would be written)
svdgen generate --dry-run
```

### Full pipeline via Python API

```python
from svdgen import load_config, run

config = load_config("svdgen.toml")
result = run(config)

print(f"Success: {result.success}")
if result.device is not None:
    print(f"Device: {result.device.name}")
print(f"Artifacts: {len(result.artifacts)}")
for d in result.diagnostics:
    print(d)
```

The `run()` function accepts extension points:

```python
result = run(
    config,
    dry_run=True,
    custom_filters={"my_filter": lambda s: s.upper()},
    custom_globals={"project_version": "2.0.0"},
)
```

### Stage-by-stage via Python API

For maximum control, call each stage individually:

```python
from svdgen import (
    parse_svd, normalize, load_patches, apply_patches,
    render_targets, write_artifacts, OutputTarget, Scope,
)

# 1. Parse
parse_result = parse_svd("device.svd")
for d in parse_result.diagnostics:
    print(d)

# 2. Normalize
device = normalize(parse_result)
print(f"{device.name}: {len(device.peripherals)} peripherals")

# 3. Patch (optional, repeat for multiple files)
patches = load_patches("fixups.yaml")
patch_result = apply_patches(device, patches)
device = patch_result.device

# --- Intercept: inspect or modify the model here ---
for p in device.peripherals:
    print(f"  {p.name} @ 0x{p.base_address:08X}")

# 4. Render
targets = [
    OutputTarget(
        name="headers",
        template="c_header/peripheral.h.j2",
        output_path="{{ peripheral.name | lower }}.h",
        scope=Scope.PERIPHERAL,
    ),
]
render_result = render_targets(device, targets)

# --- Intercept: filter or post-process artifacts here ---
artifacts = [a for a in render_result.artifacts if "gpioa" in a.path]

# 5. Write
write_diagnostics = write_artifacts(artifacts, "output/")
```

This approach lets you:

- **Inspect between stages** — examine the model after parsing, after normalization, or after patching.
- **Skip stages** — render without patches, or parse without rendering.
- **Inject custom logic** — filter peripherals, transform artifact content, write to non-filesystem targets.
- **Build custom pipelines** — combine svdgen stages with your own processing steps.

## Extension points

| Stage  | Extension mechanism                                  |
|--------|------------------------------------------------------|
| Patch  | Programmatic `Patch` / `PatchSet` construction       |
| Render | `custom_filters`, `custom_globals`, `extra_context`  |
| Write  | Post-process `RenderArtifact` list before writing    |

### Programmatic patch construction

Instead of loading from YAML, you can build patches in code:

```python
from svdgen.patch import Patch, PatchSet, apply_patches

patches = PatchSet(patches=(
    Patch(target="GPIOA.MODER", set_={"description": "Updated by script"}),
    Patch(target="GPIOB", disable=True),
))
result = apply_patches(device, patches)
```

### Custom artifact post-processing

```python
from svdgen import RenderArtifact

render_result = render_targets(device, targets)

# Add a license header to every artifact
LICENSE = "/* Copyright 2026 My Company. All rights reserved. */\n\n"
modified = [
    RenderArtifact(path=a.path, content=LICENSE + a.content, target_name=a.target_name)
    for a in render_result.artifacts
]

write_artifacts(modified, "output/")
```
