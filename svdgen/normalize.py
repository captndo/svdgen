"""Convert a raw cmsis-svd parse result into the normalized device model."""

from __future__ import annotations

import re

from cmsis_svd.model import (
    SVDAccessType,
    SVDAddressBlock,
    SVDCpu,
    SVDDevice,
    SVDEndianType,
)
from cmsis_svd.model import (
    SVDEnumeratedValue as SVDEnumVal,
)
from cmsis_svd.model import (
    SVDEnumeratedValues as SVDEnumVals,
)
from cmsis_svd.model import (
    SVDField as SVDFieldRaw,
)
from cmsis_svd.model import (
    SVDInterrupt as SVDInterruptRaw,
)
from cmsis_svd.model import (
    SVDPeripheral as SVDPeripheralRaw,
)
from cmsis_svd.model import (
    SVDRegister as SVDRegisterRaw,
)

from .model import (
    CPU,
    AccessType,
    AddressBlock,
    Device,
    EndianType,
    EnumeratedValue,
    EnumeratedValueSet,
    Field,
    Interrupt,
    Peripheral,
    Register,
)
from .parser import ParseResult

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(result: ParseResult) -> Device:
    """Convert a :class:`ParseResult` into a normalized :class:`Device`."""
    return _normalize_device(result.device)


# ---------------------------------------------------------------------------
# Device / CPU
# ---------------------------------------------------------------------------


def _normalize_device(raw: SVDDevice) -> Device:
    peripherals = tuple(
        sorted(
            (_normalize_peripheral(p) for p in raw.get_peripherals()),
            key=lambda p: p.base_address,
        )
    )

    return Device(
        name=_clean_name(raw.name),
        raw_name=raw.name or "",
        description=_clean_description(raw.description),
        version=raw.version,
        vendor=raw.vendor,
        vendor_id=raw.vendor_id,
        address_unit_bits=raw.address_unit_bits,
        width=raw.width,
        cpu=_normalize_cpu(raw.cpu) if raw.cpu else None,
        peripherals=peripherals,
        default_register_size=raw.size,
        default_access=_map_access(raw.access),
        default_reset_value=raw.reset_value,
        default_reset_mask=raw.reset_mask,
    )


def _normalize_cpu(raw: SVDCpu) -> CPU:
    name = raw.name.value if isinstance(raw.name, SVDEndianType) else str(raw.name)
    if hasattr(raw.name, "value"):
        name = raw.name.value

    endian: EndianType | None = None
    if raw.endian is not None:
        try:
            endian = EndianType(raw.endian.value)
        except (ValueError, AttributeError):
            endian = None

    return CPU(
        name=name,
        revision=raw.revision,
        endian=endian,
        mpu_present=raw.mpu_present,
        fpu_present=raw.fpu_present,
        nvic_prio_bits=raw.nvic_prio_bits,
        vendor_systick_config=raw.vendor_systick_config,
    )


# ---------------------------------------------------------------------------
# Peripheral
# ---------------------------------------------------------------------------


def _normalize_peripheral(raw: SVDPeripheralRaw) -> Peripheral:
    periph_name = _clean_name(raw.name)

    registers = tuple(
        sorted(
            (_normalize_register(r, periph_name, raw.base_address) for r in raw.get_registers()),
            key=lambda r: r.address_offset,
        )
    )

    interrupts = tuple(
        sorted(
            (_normalize_interrupt(i, periph_name) for i in (raw.interrupts or [])),
            key=lambda i: i.value,
        )
    )

    address_blocks = tuple(_normalize_address_block(ab) for ab in (raw.address_blocks or []))

    return Peripheral(
        name=periph_name,
        raw_name=raw.name or "",
        description=_clean_description(raw.description),
        group_name=raw.group_name,
        base_address=raw.base_address,
        derived_from=raw.derived_from,
        registers=registers,
        interrupts=interrupts,
        address_blocks=address_blocks,
        source_path=periph_name,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


def _normalize_register(raw: SVDRegisterRaw, periph_name: str, base_address: int) -> Register:
    reg_name = _clean_name(raw.name)
    source_path = f"{periph_name}.{reg_name}"

    fields = tuple(
        sorted(
            (_normalize_field(f, source_path) for f in raw.get_fields()),
            key=lambda f: f.bit_offset,
        )
    )

    return Register(
        name=reg_name,
        raw_name=raw.name or "",
        description=_clean_description(raw.description),
        address_offset=raw.address_offset,
        absolute_address=base_address + raw.address_offset,
        size=raw.size,
        access=_map_access(raw.access),
        reset_value=raw.reset_value,
        reset_mask=raw.reset_mask,
        fields=fields,
        display_name=raw.display_name,
        source_path=source_path,
    )


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------


def _normalize_field(raw: SVDFieldRaw, reg_source_path: str) -> Field:
    field_name = _clean_name(raw.name)

    enum_sets: tuple[EnumeratedValueSet, ...] = ()
    if raw.enumerated_values:
        enum_sets = tuple(_normalize_enum_set(ev) for ev in raw.enumerated_values)

    return Field(
        name=field_name,
        raw_name=raw.name or "",
        description=_clean_description(raw.description),
        bit_offset=raw.bit_offset or 0,
        bit_width=raw.bit_width or 0,
        access=_map_access(raw.access),
        enumerated_values=enum_sets,
        source_path=f"{reg_source_path}.{field_name}",
    )


# ---------------------------------------------------------------------------
# EnumeratedValues
# ---------------------------------------------------------------------------


def _normalize_enum_set(raw: SVDEnumVals) -> EnumeratedValueSet:
    values = tuple(_normalize_enum_value(ev) for ev in raw.enumerated_values)
    usage = raw.usage.value if raw.usage is not None else None
    return EnumeratedValueSet(name=raw.name, usage=usage, values=values)


def _normalize_enum_value(raw: SVDEnumVal) -> EnumeratedValue:
    return EnumeratedValue(
        name=raw.name or "",
        description=_clean_description(raw.description),
        value=raw.value,
        is_default=raw.is_default or False,
    )


# ---------------------------------------------------------------------------
# Interrupt / AddressBlock
# ---------------------------------------------------------------------------


def _normalize_interrupt(raw: SVDInterruptRaw, periph_name: str) -> Interrupt:
    return Interrupt(
        name=raw.name or "",
        description=_clean_description(raw.description),
        value=raw.value,
        source_path=f"{periph_name}.{raw.name}",
    )


def _normalize_address_block(raw: SVDAddressBlock) -> AddressBlock:
    usage = raw.usage.value if raw.usage is not None else None
    return AddressBlock(offset=raw.offset, size=raw.size, usage=usage)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACCESS_MAP: dict[SVDAccessType, AccessType] = {
    SVDAccessType.READ_ONLY: AccessType.READ_ONLY,
    SVDAccessType.WRITE_ONLY: AccessType.WRITE_ONLY,
    SVDAccessType.READ_WRITE: AccessType.READ_WRITE,
    SVDAccessType.WRITE_ONCE: AccessType.WRITE_ONCE,
    SVDAccessType.READ_WRITE_ONCE: AccessType.READ_WRITE_ONCE,
}


def _map_access(raw: SVDAccessType | None) -> AccessType | None:
    if raw is None:
        return None
    return _ACCESS_MAP.get(raw)


_WS_RUN = re.compile(r"\s+")


def _clean_name(name: str | None) -> str:
    if not name:
        return ""
    return name.strip()


def _clean_description(desc: str | None) -> str | None:
    if not desc:
        return None
    cleaned = _WS_RUN.sub(" ", desc).strip()
    return cleaned or None
