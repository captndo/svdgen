"""Tests for the normalized data model computed properties."""

from svdgen.model import AccessType, EndianType, Field


class TestFieldComputedProperties:
    def _field(self, bit_offset: int, bit_width: int) -> Field:
        return Field(
            name="F",
            raw_name="F",
            description=None,
            bit_offset=bit_offset,
            bit_width=bit_width,
            access=None,
            enumerated_values=(),
        )

    def test_lsb(self):
        assert self._field(4, 3).lsb == 4

    def test_msb(self):
        assert self._field(4, 3).msb == 6

    def test_bit_mask_single_bit(self):
        f = self._field(0, 1)
        assert f.bit_mask == 0x1

    def test_bit_mask_byte_aligned(self):
        f = self._field(8, 8)
        assert f.bit_mask == 0xFF00

    def test_bit_mask_full_32(self):
        f = self._field(0, 32)
        assert f.bit_mask == 0xFFFFFFFF

    def test_bit_mask_two_bits_at_offset(self):
        f = self._field(2, 2)
        assert f.bit_mask == 0b1100


class TestFieldFrozen:
    def test_immutable(self):
        f = Field(
            name="X",
            raw_name="X",
            description=None,
            bit_offset=0,
            bit_width=1,
            access=AccessType.READ_WRITE,
            enumerated_values=(),
        )
        try:
            f.name = "Y"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass


class TestEnums:
    def test_access_type_values(self):
        assert AccessType.READ_ONLY.value == "read-only"
        assert AccessType.READ_WRITE.value == "read-write"

    def test_endian_type_values(self):
        assert EndianType.LITTLE.value == "little"
        assert EndianType.BIG.value == "big"
