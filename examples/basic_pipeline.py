#!/usr/bin/env python3
"""Demonstrate the step-by-step svdgen Python API.

Run from the repository root:
    python examples/basic_pipeline.py
"""

from pathlib import Path

from svdgen import (
    OutputTarget,
    Scope,
    normalize,
    parse_svd,
    render_targets,
    write_artifacts,
)

SVD_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "minimal.svd"
OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    # 1. Parse
    result = parse_svd(SVD_PATH)
    print(f"Parsed {result.device.name} — {len(result.diagnostics)} diagnostics")

    # 2. Normalize
    device = normalize(result)
    print(f"Normalized: {len(device.peripherals)} peripherals")

    for p in device.peripherals:
        print(f"  {p.name} @ 0x{p.base_address:08X} — {len(p.registers)} registers")

    # 3. Render using the built-in C header template
    targets = [
        OutputTarget(
            name="c_headers",
            template="c_header/peripheral.h.j2",
            output_path="{{ peripheral.name | lower }}.h",
            scope=Scope.PERIPHERAL,
        ),
    ]
    rendered = render_targets(device, targets, input_source=str(SVD_PATH))
    print(f"\nRendered {len(rendered.artifacts)} artifacts:")
    for art in rendered.artifacts:
        print(f"  {art.path} ({len(art.content)} bytes)")

    # 4. Write
    diags = write_artifacts(rendered.artifacts, OUTPUT_DIR)
    print(f"\nWrote files to {OUTPUT_DIR}/ — {len(diags)} write diagnostics")


if __name__ == "__main__":
    main()
