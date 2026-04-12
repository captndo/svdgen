"""Normalized device model — the stable API contract for svdgen.

All types are frozen dataclasses with tuple collections, making the
normalized model fully immutable once constructed.  Downstream consumers
(patch system, templates, Python API) work against these types rather
than the raw cmsis-svd model.

Clusters are resolved/flattened during normalization and do not appear
as a separate entity.  Registers that originated from clusters carry
their flattened names (e.g. ``CLUSTER_REG``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AccessType(Enum):
    """Register or field access permissions (mirrors CMSIS-SVD access types)."""

    READ_ONLY = "read-only"
    WRITE_ONLY = "write-only"
    READ_WRITE = "read-write"
    WRITE_ONCE = "write-once"
    READ_WRITE_ONCE = "read-write-once"


class EndianType(Enum):
    """CPU byte ordering."""

    LITTLE = "little"
    BIG = "big"
    SELECTABLE = "selectable"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Leaf entities
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnumeratedValue:
    """A single named value within an enumerated value set."""

    name: str
    description: str | None
    value: int | None
    is_default: bool = False


@dataclass(frozen=True)
class EnumeratedValueSet:
    """A group of enumerated values associated with a field."""

    name: str | None
    usage: str | None
    values: tuple[EnumeratedValue, ...]


@dataclass(frozen=True)
class Interrupt:
    """An interrupt line associated with a peripheral."""

    name: str
    description: str | None
    value: int
    source_path: str | None = None


@dataclass(frozen=True)
class AddressBlock:
    """A contiguous address range within a peripheral."""

    offset: int
    size: int
    usage: str | None


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    """A bit-field within a register.

    Provides computed properties :attr:`lsb`, :attr:`msb`, and
    :attr:`bit_mask` derived from *bit_offset* and *bit_width*.
    """

    name: str
    raw_name: str
    description: str | None
    bit_offset: int
    bit_width: int
    access: AccessType | None
    enumerated_values: tuple[EnumeratedValueSet, ...]
    source_path: str | None = None
    enabled: bool = True

    @property
    def lsb(self) -> int:
        return self.bit_offset

    @property
    def msb(self) -> int:
        return self.bit_offset + self.bit_width - 1

    @property
    def bit_mask(self) -> int:
        return ((1 << self.bit_width) - 1) << self.bit_offset


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Register:
    """A memory-mapped register within a peripheral."""

    name: str
    raw_name: str
    description: str | None
    address_offset: int
    absolute_address: int
    size: int | None
    access: AccessType | None
    reset_value: int | None
    reset_mask: int | None
    fields: tuple[Field, ...]
    display_name: str | None = None
    source_path: str | None = None
    enabled: bool = True


# ---------------------------------------------------------------------------
# Peripheral
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Peripheral:
    """A hardware peripheral containing registers, interrupts, and address blocks."""

    name: str
    raw_name: str
    description: str | None
    group_name: str | None
    base_address: int
    derived_from: str | None
    registers: tuple[Register, ...]
    interrupts: tuple[Interrupt, ...]
    address_blocks: tuple[AddressBlock, ...]
    source_path: str | None = None
    enabled: bool = True


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CPU:
    """CPU metadata from the SVD device definition."""

    name: str
    revision: str | None
    endian: EndianType | None
    mpu_present: bool | None
    fpu_present: bool | None
    nvic_prio_bits: int | None
    vendor_systick_config: bool | None


# ---------------------------------------------------------------------------
# Device (root)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Device:
    """Root of the normalized device model.

    Contains all peripherals and device-level metadata.  This is the
    primary type passed to templates and consumed by the Python API.
    """

    name: str
    raw_name: str
    description: str | None
    version: str | None
    vendor: str | None
    vendor_id: str | None
    address_unit_bits: int | None
    width: int | None
    cpu: CPU | None
    peripherals: tuple[Peripheral, ...]
    default_register_size: int | None = None
    default_access: AccessType | None = None
    default_reset_value: int | None = None
    default_reset_mask: int | None = None
