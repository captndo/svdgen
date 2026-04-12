"""Patch system — load, validate, and apply patches to the normalized model.

Patch files are YAML lists of operations.  Each entry has a ``target``
selector (dot-separated path) and exactly one action::

    - target: "GPIOA.MODER"
      set:
        description: "Mode register"
        reset_value: 0xFFFFFFFF

    - target: "GPIOA.MODER.MODE0"
      rename: "MODER_BIT0"

    - target: "GPIOA.OLD_REG"
      remove: true

    - target: "GPIOA.DISABLED_REG"
      disable: true

Patches are applied sequentially in file order.  Later patches may
override the effects of earlier ones.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TypeVar

import yaml

from .diagnostics import Diagnostic, DiagnosticCollector
from .model import AccessType, Device, Field, Peripheral, Register

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_ACTIONS = frozenset({"rename", "set", "remove", "disable"})

_SETTABLE_PERIPHERAL = frozenset({"description", "group_name"})
_SETTABLE_REGISTER = frozenset(
    {
        "description",
        "access",
        "reset_value",
        "reset_mask",
        "size",
        "display_name",
    }
)
_SETTABLE_FIELD = frozenset({"description", "access", "bit_offset", "bit_width"})


@dataclass(frozen=True)
class Patch:
    """A single patch operation."""

    target: str
    rename: str | None = None
    set_: dict[str, Any] | None = None
    remove: bool = False
    disable: bool = False
    source_file: Path | None = None
    source_index: int | None = None


@dataclass(frozen=True)
class PatchSet:
    """An ordered collection of patches from one file."""

    patches: tuple[Patch, ...]
    source_file: Path | None = None


@dataclass
class PatchResult:
    """Outcome of applying patches."""

    device: Device
    diagnostics: list[Diagnostic]


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def load_patches(path: str | Path) -> PatchSet:
    """Load a patch set from a YAML file.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the YAML structure is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Patch file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return PatchSet(patches=(), source_file=path)

    if not isinstance(raw, list):
        raise ValueError(f"Patch file must be a YAML list, got {type(raw).__name__}: {path}")

    patches: list[Patch] = []
    for idx, entry in enumerate(raw):
        patches.append(_parse_patch_entry(entry, idx, path))

    return PatchSet(patches=tuple(patches), source_file=path)


def _parse_patch_entry(entry: dict[str, Any], index: int, path: Path) -> Patch:
    if not isinstance(entry, dict):
        raise ValueError(f"Patch entry {index} must be a mapping, got {type(entry).__name__}")

    target = entry.get("target")
    if not target or not isinstance(target, str):
        raise ValueError(f"Patch entry {index} missing required 'target' string")

    actions_present = [a for a in _ACTIONS if a in entry and entry[a] is not None]
    if len(actions_present) == 0:
        raise ValueError(f"Patch entry {index} has no action (need one of {sorted(_ACTIONS)})")
    if len(actions_present) > 1:
        raise ValueError(
            f"Patch entry {index} has multiple actions: {actions_present} (need exactly one)"
        )

    rename = entry.get("rename")
    if rename is not None and not isinstance(rename, str):
        raise ValueError(f"Patch entry {index}: 'rename' must be a string")

    set_ = entry.get("set")
    if set_ is not None and not isinstance(set_, dict):
        raise ValueError(f"Patch entry {index}: 'set' must be a mapping")

    remove = bool(entry.get("remove", False))
    disable = bool(entry.get("disable", False))

    return Patch(
        target=target,
        rename=rename,
        set_=set_,
        remove=remove,
        disable=disable,
        source_file=path,
        source_index=index,
    )


# ---------------------------------------------------------------------------
# Selector engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Selector:
    peripheral: str
    register: str | None = None
    field: str | None = None

    @property
    def depth(self) -> int:
        if self.field is not None:
            return 3
        if self.register is not None:
            return 2
        return 1


def _parse_selector(target: str) -> _Selector:
    parts = target.split(".")
    if len(parts) == 1:
        return _Selector(peripheral=parts[0])
    if len(parts) == 2:
        return _Selector(peripheral=parts[0], register=parts[1])
    if len(parts) == 3:
        return _Selector(peripheral=parts[0], register=parts[1], field=parts[2])
    raise ValueError(f"Selector has too many components (max 3): {target!r}")


# ---------------------------------------------------------------------------
# Patch executor
# ---------------------------------------------------------------------------


def apply_patches(device: Device, patches: PatchSet) -> PatchResult:
    """Apply a :class:`PatchSet` to a normalized :class:`Device`.

    Returns a new :class:`PatchResult` with the modified device and any
    diagnostics produced during application.  Patches are applied
    sequentially in file order.
    """
    collector = DiagnosticCollector()
    current = device

    for patch in patches.patches:
        current = _apply_one(current, patch, collector)

    return PatchResult(device=current, diagnostics=collector.diagnostics)


def _apply_one(device: Device, patch: Patch, collector: DiagnosticCollector) -> Device:
    try:
        sel = _parse_selector(patch.target)
    except ValueError as exc:
        collector.error(str(exc), file_path=patch.source_file)
        return device

    periph_idx = _find_peripheral(device, sel.peripheral)
    if periph_idx is None:
        collector.error(
            f"Peripheral not found: {sel.peripheral!r}",
            file_path=patch.source_file,
            element_path=patch.target,
        )
        return device

    if sel.depth == 1:
        return _apply_to_peripheral(device, periph_idx, patch, collector)
    if sel.depth == 2:
        return _apply_to_register(device, periph_idx, sel, patch, collector)
    return _apply_to_field(device, periph_idx, sel, patch, collector)


# -- peripheral-level --------------------------------------------------------


def _apply_to_peripheral(
    device: Device, pidx: int, patch: Patch, collector: DiagnosticCollector
) -> Device:
    periph = device.peripherals[pidx]

    if patch.remove:
        new_periphs = _tuple_without(device.peripherals, pidx)
        return replace(device, peripherals=new_periphs)

    if patch.disable:
        return _replace_peripheral(device, pidx, replace(periph, enabled=False))

    if patch.rename:
        return _replace_peripheral(device, pidx, replace(periph, name=patch.rename))

    if patch.set_:
        return _replace_peripheral(
            device, pidx, _set_properties(periph, patch, _SETTABLE_PERIPHERAL, collector)
        )

    return device


# -- register-level ----------------------------------------------------------


def _apply_to_register(
    device: Device, pidx: int, sel: _Selector, patch: Patch, collector: DiagnosticCollector
) -> Device:
    periph = device.peripherals[pidx]
    ridx = _find_register(periph, sel.register)
    if ridx is None:
        collector.error(
            f"Register not found: {sel.register!r}",
            file_path=patch.source_file,
            element_path=patch.target,
        )
        return device

    reg = periph.registers[ridx]

    if patch.remove:
        new_regs = _tuple_without(periph.registers, ridx)
        return _replace_peripheral(device, pidx, replace(periph, registers=new_regs))

    if patch.disable:
        new_reg = replace(reg, enabled=False)
        return _replace_register(device, pidx, ridx, new_reg)

    if patch.rename:
        new_reg = replace(reg, name=patch.rename)
        return _replace_register(device, pidx, ridx, new_reg)

    if patch.set_:
        new_reg = _set_properties(reg, patch, _SETTABLE_REGISTER, collector)
        return _replace_register(device, pidx, ridx, new_reg)

    return device


# -- field-level -------------------------------------------------------------


def _apply_to_field(
    device: Device, pidx: int, sel: _Selector, patch: Patch, collector: DiagnosticCollector
) -> Device:
    periph = device.peripherals[pidx]
    ridx = _find_register(periph, sel.register)
    if ridx is None:
        collector.error(
            f"Register not found: {sel.register!r}",
            file_path=patch.source_file,
            element_path=patch.target,
        )
        return device

    reg = periph.registers[ridx]
    fidx = _find_field(reg, sel.field)
    if fidx is None:
        collector.error(
            f"Field not found: {sel.field!r}",
            file_path=patch.source_file,
            element_path=patch.target,
        )
        return device

    field = reg.fields[fidx]

    if patch.remove:
        new_fields = _tuple_without(reg.fields, fidx)
        new_reg = replace(reg, fields=new_fields)
        return _replace_register(device, pidx, ridx, new_reg)

    if patch.disable:
        new_field = replace(field, enabled=False)
        return _replace_field(device, pidx, ridx, fidx, new_field)

    if patch.rename:
        new_field = replace(field, name=patch.rename)
        return _replace_field(device, pidx, ridx, fidx, new_field)

    if patch.set_:
        new_field = _set_properties(field, patch, _SETTABLE_FIELD, collector)
        return _replace_field(device, pidx, ridx, fidx, new_field)

    return device


# ---------------------------------------------------------------------------
# Tree-rebuild helpers
# ---------------------------------------------------------------------------


def _replace_peripheral(device: Device, pidx: int, new_periph: Peripheral) -> Device:
    new_periphs = _tuple_replace(device.peripherals, pidx, new_periph)
    return replace(device, peripherals=new_periphs)


def _replace_register(device: Device, pidx: int, ridx: int, new_reg: Register) -> Device:
    periph = device.peripherals[pidx]
    new_regs = _tuple_replace(periph.registers, ridx, new_reg)
    new_periph = replace(periph, registers=new_regs)
    return _replace_peripheral(device, pidx, new_periph)


def _replace_field(device: Device, pidx: int, ridx: int, fidx: int, new_field: Field) -> Device:
    reg = device.peripherals[pidx].registers[ridx]
    new_fields = _tuple_replace(reg.fields, fidx, new_field)
    new_reg = replace(reg, fields=new_fields)
    return _replace_register(device, pidx, ridx, new_reg)


_T = TypeVar("_T")


def _tuple_replace(tup: tuple[_T, ...], idx: int, value: _T) -> tuple[_T, ...]:
    lst = list(tup)
    lst[idx] = value
    return tuple(lst)


def _tuple_without(tup: tuple[_T, ...], idx: int) -> tuple[_T, ...]:
    return tup[:idx] + tup[idx + 1 :]


# ---------------------------------------------------------------------------
# Property setting
# ---------------------------------------------------------------------------


def _set_properties(
    node: _T, patch: Patch, allowed: frozenset[str], collector: DiagnosticCollector
) -> _T:
    kwargs: dict[str, Any] = {}
    for key, value in (patch.set_ or {}).items():
        if key not in allowed:
            collector.error(
                f"Cannot set property {key!r} on {type(node).__name__}; "
                f"allowed: {sorted(allowed)}",
                file_path=patch.source_file,
                element_path=patch.target,
            )
            continue
        if key == "access":
            value = _coerce_access(value, patch, collector)
        kwargs[key] = value

    return replace(node, **kwargs) if kwargs else node


def _coerce_access(value: Any, patch: Patch, collector: DiagnosticCollector) -> AccessType | None:
    if value is None:
        return None
    try:
        return AccessType(value)
    except ValueError:
        collector.error(
            f"Invalid access type {value!r}; valid: {[a.value for a in AccessType]}",
            file_path=patch.source_file,
            element_path=patch.target,
        )
        return None


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _find_peripheral(device: Device, name: str) -> int | None:
    for i, p in enumerate(device.peripherals):
        if p.name == name:
            return i
    return None


def _find_register(periph: Peripheral, name: str | None) -> int | None:
    if name is None:
        return None
    for i, r in enumerate(periph.registers):
        if r.name == name:
            return i
    return None


def _find_field(reg: Register, name: str | None) -> int | None:
    if name is None:
        return None
    for i, f in enumerate(reg.fields):
        if f.name == name:
            return i
    return None
