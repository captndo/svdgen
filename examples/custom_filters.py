#!/usr/bin/env python3
"""Demonstrate custom Jinja filters and globals via the Python API.

Run from the repository root:
    python examples/custom_filters.py
"""

from pathlib import Path

from svdgen import (
    OutputTarget,
    Scope,
    normalize,
    parse_svd,
    render_targets,
    upper_snake,
)

SVD_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "minimal.svd"


def prefixed_name(value: str, prefix: str = "HAL") -> str:
    """Custom filter: HAL_GPIOA_MODER."""
    return f"{prefix}_{upper_snake(value)}"


def main() -> None:
    result = parse_svd(SVD_PATH)
    device = normalize(result)

    # Write a small inline template to a temp dir
    tpl_dir = Path(__file__).parent / "_tmp_templates"
    tpl_dir.mkdir(exist_ok=True)

    (tpl_dir / "demo.j2").write_text(
        "Peripheral: {{ peripheral.name | prefixed }}\n"
        "Project:    {{ project_name }}\n"
        "Registers:\n"
        "{% for r in peripheral.registers %}"
        "  - {{ r.name | prefixed }}\n"
        "{% endfor %}"
    )

    targets = [
        OutputTarget(
            name="demo",
            template="demo.j2",
            output_path="{{ peripheral.name }}.txt",
            scope=Scope.PERIPHERAL,
        ),
    ]

    rendered = render_targets(
        device,
        targets,
        [tpl_dir],
        custom_filters={"prefixed": prefixed_name},
        custom_globals={"project_name": "My Firmware BSP"},
    )

    for art in rendered.artifacts:
        print(f"--- {art.path} ---")
        print(art.content)

    # Cleanup
    (tpl_dir / "demo.j2").unlink()
    tpl_dir.rmdir()


if __name__ == "__main__":
    main()
