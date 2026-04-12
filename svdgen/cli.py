"""CLI entry point — Typer-based command interface for svdgen."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="svdgen",
    help="Hardware description generation engine — parse, patch, and render CMSIS-SVD.",
    no_args_is_help=True,
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

ConfigOption = Annotated[
    Path,
    typer.Option("--config", "-c", help="Path to svdgen TOML config file."),
]

JsonFlag = Annotated[
    bool,
    typer.Option("--json", help="Output in JSON format."),
]

VerboseFlag = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Show all diagnostics including info."),
]

QuietFlag = Annotated[
    bool,
    typer.Option("--quiet", "-q", help="Only show errors."),
]

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_RUNTIME = 2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config_or_exit(config: Path):
    from .config import load_config

    try:
        return load_config(config)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from exc
    except ValueError as exc:
        typer.echo(f"Config error: {exc}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from exc


def _load_device(config: Path):
    """Run parse → normalize → patch and return (device, cfg, diagnostics)."""
    from .diagnostics import Diagnostic, Severity
    from .normalize import normalize
    from .parser import ParseError, parse_svd
    from .patch import apply_patches, load_patches

    cfg = _load_config_or_exit(config)

    all_diags: list[Diagnostic] = []

    try:
        parse_result = parse_svd(cfg.input.svd, validate=cfg.validation.strict)
    except ParseError as exc:
        for d in exc.diagnostics:
            typer.echo(str(d), err=True)
        raise typer.Exit(EXIT_FAILURE) from exc

    all_diags.extend(parse_result.diagnostics)
    device = normalize(parse_result)

    for patch_path in cfg.patches.files:
        try:
            patch_set = load_patches(patch_path)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(f"Patch error: {exc}", err=True)
            raise typer.Exit(EXIT_FAILURE) from exc

        patch_result = apply_patches(device, patch_set)
        all_diags.extend(patch_result.diagnostics)
        if any(d.severity == Severity.ERROR for d in patch_result.diagnostics):
            _print_diagnostics(all_diags, verbose=True, quiet=False)
            raise typer.Exit(EXIT_FAILURE)
        device = patch_result.device

    return device, cfg, all_diags


def _print_diagnostics(
    diagnostics: list,
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    from .diagnostics import Severity

    for d in diagnostics:
        if quiet and d.severity != Severity.ERROR:
            continue
        if not verbose and d.severity == Severity.INFO:
            continue
        typer.echo(str(d), err=True)


def _resolve_selector(device, selector: str):
    """Walk the device tree by dot-separated selector.

    Returns the matched element and its kind ('device', 'peripheral',
    'register', or 'field').
    """
    if not selector:
        return device, "device"

    parts = selector.split(".")

    periph = None
    for p in device.peripherals:
        if p.name == parts[0]:
            periph = p
            break
    if periph is None:
        typer.echo(f"Peripheral not found: {parts[0]!r}", err=True)
        raise typer.Exit(EXIT_FAILURE)
    if len(parts) == 1:
        return periph, "peripheral"

    reg = None
    for r in periph.registers:
        if r.name == parts[1]:
            reg = r
            break
    if reg is None:
        typer.echo(f"Register not found: {parts[1]!r} in {parts[0]!r}", err=True)
        raise typer.Exit(EXIT_FAILURE)
    if len(parts) == 2:
        return reg, "register"

    field = None
    for f in reg.fields:
        if f.name == parts[2]:
            field = f
            break
    if field is None:
        typer.echo(
            f"Field not found: {parts[2]!r} in {parts[0]}.{parts[1]!r}",
            err=True,
        )
        raise typer.Exit(EXIT_FAILURE)
    if len(parts) == 3:
        return field, "field"

    typer.echo(f"Selector too deep (max 3 levels): {selector!r}", err=True)
    raise typer.Exit(EXIT_FAILURE)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def generate(
    config: ConfigOption = Path("svdgen.toml"),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Render without writing files.")
    ] = False,
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    """Run the full generation pipeline."""
    from .diagnostics import Severity
    from .pipeline import run

    cfg = _load_config_or_exit(config)
    result = run(cfg, dry_run=dry_run)

    _print_diagnostics(result.diagnostics, verbose=verbose, quiet=quiet)

    errors = sum(1 for d in result.diagnostics if d.severity == Severity.ERROR)
    warnings = sum(1 for d in result.diagnostics if d.severity == Severity.WARNING)
    n_artifacts = len(result.artifacts)

    if not quiet:
        if dry_run:
            typer.echo(f"Dry run: {n_artifacts} file(s) would be written.")
        else:
            typer.echo(f"Generated {n_artifacts} file(s).")
        if warnings:
            typer.echo(f"Warnings: {warnings}")
        if errors:
            typer.echo(f"Errors: {errors}")

    if not result.success:
        raise typer.Exit(EXIT_FAILURE)


@app.command()
def validate(
    config: ConfigOption = Path("svdgen.toml"),
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    """Validate config, inputs, patches, and targets without writing files."""
    from .diagnostics import Severity
    from .pipeline import run

    cfg = _load_config_or_exit(config)
    result = run(cfg, dry_run=True)

    _print_diagnostics(result.diagnostics, verbose=verbose, quiet=quiet)

    errors = sum(1 for d in result.diagnostics if d.severity == Severity.ERROR)
    warnings = sum(1 for d in result.diagnostics if d.severity == Severity.WARNING)

    if not quiet:
        if errors:
            typer.echo(f"Validation failed: {errors} error(s), {warnings} warning(s).")
        else:
            typer.echo("Validation passed." + (f" {warnings} warning(s)." if warnings else ""))

    if not result.success:
        raise typer.Exit(EXIT_FAILURE)


@app.command()
def inspect(
    selector: Annotated[str, typer.Argument(help="Element selector: PERIPH[.REG[.FIELD]]")] = "",
    config: ConfigOption = Path("svdgen.toml"),
    json_output: JsonFlag = False,
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    """Inspect a device, peripheral, register, or field."""

    device, cfg, diags = _load_device(config)
    _print_diagnostics(diags, verbose=verbose, quiet=quiet)

    element, kind = _resolve_selector(device, selector)

    if json_output:
        from .export import _convert

        typer.echo(json.dumps(_convert(element), indent=2))
    else:
        _print_element(element, kind)


def _print_element(element, kind: str) -> None:
    """Human-readable property display."""
    if kind == "device":
        _kv("Name", element.name)
        _kv("Description", element.description)
        _kv("Version", element.version)
        _kv("Vendor", element.vendor)
        _kv("Width", element.width)
        _kv("Address unit bits", element.address_unit_bits)
        _kv("Peripherals", len(element.peripherals))
        if element.cpu:
            _kv("CPU", element.cpu.name)
    elif kind == "peripheral":
        _kv("Name", element.name)
        _kv("Description", element.description)
        _kv("Base address", f"0x{element.base_address:08X}")
        _kv("Group", element.group_name)
        _kv("Derived from", element.derived_from)
        _kv("Registers", len(element.registers))
        _kv("Interrupts", len(element.interrupts))
        _kv("Enabled", element.enabled)
    elif kind == "register":
        _kv("Name", element.name)
        _kv("Description", element.description)
        _kv("Offset", f"0x{element.address_offset:X}")
        _kv("Address", f"0x{element.absolute_address:08X}")
        _kv("Size", element.size)
        _kv("Access", element.access.value if element.access else None)
        _kv("Reset value", f"0x{element.reset_value:08X}" if element.reset_value else None)
        _kv("Fields", len(element.fields))
        _kv("Enabled", element.enabled)
    elif kind == "field":
        _kv("Name", element.name)
        _kv("Description", element.description)
        _kv("Bit offset", element.bit_offset)
        _kv("Bit width", element.bit_width)
        _kv("Bit range", f"[{element.msb}:{element.lsb}]")
        _kv("Bit mask", f"0x{element.bit_mask:08X}")
        _kv("Access", element.access.value if element.access else None)
        _kv("Enabled", element.enabled)
        if element.enumerated_values:
            for evs in element.enumerated_values:
                for ev in evs.values:
                    val = f"0x{ev.value:X}" if ev.value is not None else "?"
                    _kv(f"  {ev.name}", val)


def _kv(key: str, value) -> None:
    if value is None:
        return
    typer.echo(f"  {key + ':':<22} {value}")


class ListResource(str, Enum):
    peripherals = "peripherals"
    registers = "registers"
    fields = "fields"
    targets = "targets"


@app.command("list")
def list_cmd(
    resource: Annotated[ListResource, typer.Argument(help="What to list.")],
    filter: Annotated[str, typer.Argument(help="Optional filter (e.g. peripheral name).")] = "",
    config: ConfigOption = Path("svdgen.toml"),
    json_output: JsonFlag = False,
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    """List peripherals, registers, fields, or configured targets."""
    if resource == ListResource.targets:
        _list_targets(config, json_output)
        return

    device, cfg, diags = _load_device(config)
    _print_diagnostics(diags, verbose=verbose, quiet=quiet)

    if resource == ListResource.peripherals:
        _list_peripherals(device, json_output)
    elif resource == ListResource.registers:
        _list_registers(device, filter, json_output)
    elif resource == ListResource.fields:
        _list_fields(device, filter, json_output)


def _list_targets(config: Path, json_output: bool) -> None:
    cfg = _load_config_or_exit(config)
    items = [
        {"name": t.name, "template": t.template, "scope": t.scope, "output_path": t.output_path}
        for t in cfg.targets
    ]
    if json_output:
        typer.echo(json.dumps(items, indent=2))
    else:
        if not items:
            typer.echo("No targets configured.")
            return
        _table(
            ["Name", "Scope", "Template", "Output Path"],
            [[i["name"], i["scope"], i["template"], i["output_path"]] for i in items],
        )


def _list_peripherals(device, json_output: bool) -> None:
    items = [
        {
            "name": p.name,
            "base_address": f"0x{p.base_address:08X}",
            "registers": len(p.registers),
            "description": _trunc(p.description, 40),
        }
        for p in device.peripherals
        if p.enabled
    ]
    if json_output:
        typer.echo(json.dumps(items, indent=2))
    else:
        _table(
            ["Name", "Base Address", "Regs", "Description"],
            [
                [i["name"], i["base_address"], str(i["registers"]), i["description"] or ""]
                for i in items
            ],
        )


def _list_registers(device, filter_name: str, json_output: bool) -> None:
    items = []
    for p in device.peripherals:
        if not p.enabled:
            continue
        if filter_name and p.name != filter_name:
            continue
        for r in p.registers:
            if not r.enabled:
                continue
            items.append(
                {
                    "peripheral": p.name,
                    "name": r.name,
                    "offset": f"0x{r.address_offset:X}",
                    "address": f"0x{r.absolute_address:08X}",
                    "fields": len(r.fields),
                }
            )
    if json_output:
        typer.echo(json.dumps(items, indent=2))
    else:
        if not items:
            typer.echo("No registers found.")
            return
        _table(
            ["Peripheral", "Register", "Offset", "Address", "Fields"],
            [
                [i["peripheral"], i["name"], i["offset"], i["address"], str(i["fields"])]
                for i in items
            ],
        )


def _list_fields(device, filter_path: str, json_output: bool) -> None:
    parts = filter_path.split(".") if filter_path else []
    items = []
    for p in device.peripherals:
        if not p.enabled:
            continue
        if len(parts) >= 1 and p.name != parts[0]:
            continue
        for r in p.registers:
            if not r.enabled:
                continue
            if len(parts) >= 2 and r.name != parts[1]:
                continue
            for f in r.fields:
                if not f.enabled:
                    continue
                items.append(
                    {
                        "peripheral": p.name,
                        "register": r.name,
                        "name": f.name,
                        "bits": f"[{f.msb}:{f.lsb}]",
                        "access": f.access.value if f.access else "",
                    }
                )
    if json_output:
        typer.echo(json.dumps(items, indent=2))
    else:
        if not items:
            typer.echo("No fields found.")
            return
        _table(
            ["Peripheral", "Register", "Field", "Bits", "Access"],
            [[i["peripheral"], i["register"], i["name"], i["bits"], i["access"]] for i in items],
        )


@app.command("export-model")
def export_model(
    config: ConfigOption = Path("svdgen.toml"),
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Write JSON to file instead of stdout."),
    ] = None,
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    """Export the full normalized model as JSON."""
    from .export import export_json

    device, cfg, diags = _load_device(config)
    _print_diagnostics(diags, verbose=verbose, quiet=quiet)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            export_json(device, file=f)
        if not quiet:
            typer.echo(f"Model exported to {output}")
    else:
        typer.echo(export_json(device))


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------


def _table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    typer.echo(fmt.format(*headers))
    typer.echo(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        typer.echo(fmt.format(*row))


def _trunc(s: str | None, length: int) -> str | None:
    if s is None:
        return None
    if len(s) <= length:
        return s
    return s[: length - 3] + "..."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
