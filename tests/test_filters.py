"""Tests for built-in Jinja filters."""

from svdgen.filters import (
    access_str,
    bit_range,
    c_comment,
    c_line_comment,
    camel_case,
    hex_format,
    lower_snake,
    pad,
    upper_snake,
)
from svdgen.model import AccessType, Field


class TestCaseConversion:
    def test_upper_snake_camel(self):
        assert upper_snake("MyPeripheral") == "MY_PERIPHERAL"

    def test_upper_snake_already(self):
        assert upper_snake("GPIOA") == "GPIOA"

    def test_upper_snake_mixed(self):
        assert upper_snake("gpioPortA") == "GPIO_PORT_A"

    def test_lower_snake_camel(self):
        assert lower_snake("MyPeripheral") == "my_peripheral"

    def test_lower_snake_upper(self):
        assert lower_snake("GPIOA_MODER") == "gpioa_moder"

    def test_camel_case_snake(self):
        assert camel_case("my_reg") == "MyReg"

    def test_camel_case_single(self):
        assert camel_case("moder") == "Moder"

    def test_upper_snake_with_spaces(self):
        assert upper_snake("some register name") == "SOME_REGISTER_NAME"

    def test_lower_snake_with_hyphens(self):
        assert lower_snake("some-register-name") == "some_register_name"


class TestHexFormat:
    def test_default_width(self):
        assert hex_format(0x4000) == "0x00004000"

    def test_custom_width(self):
        assert hex_format(0xFF, 2) == "0xFF"

    def test_zero(self):
        assert hex_format(0, 4) == "0x0000"

    def test_none(self):
        assert hex_format(None, 4) == "0x????"

    def test_large_value(self):
        assert hex_format(0xDEADBEEF) == "0xDEADBEEF"


class TestCommentFormatting:
    def test_c_comment(self):
        assert c_comment("hello") == "/* hello */"

    def test_c_comment_none(self):
        assert c_comment(None) == "/* */"

    def test_c_comment_empty(self):
        assert c_comment("") == "/* */"

    def test_c_line_comment(self):
        assert c_line_comment("hello") == "// hello"

    def test_c_line_comment_none(self):
        assert c_line_comment(None) == "//"


class TestAccessStr:
    def test_read_only(self):
        assert access_str(AccessType.READ_ONLY) == "RO"

    def test_write_only(self):
        assert access_str(AccessType.WRITE_ONLY) == "WO"

    def test_read_write(self):
        assert access_str(AccessType.READ_WRITE) == "RW"

    def test_none(self):
        assert access_str(None) == ""

    def test_string_value(self):
        assert access_str("read-only") == "RO"


class TestBitRange:
    def test_basic(self):
        f = Field(
            name="F", raw_name="F", description=None,
            bit_offset=0, bit_width=4, access=None, enumerated_values=(),
        )
        assert bit_range(f) == "[3:0]"

    def test_single_bit(self):
        f = Field(
            name="F", raw_name="F", description=None,
            bit_offset=7, bit_width=1, access=None, enumerated_values=(),
        )
        assert bit_range(f) == "[7:7]"

    def test_no_attributes(self):
        assert bit_range(object()) == ""


class TestPad:
    def test_basic(self):
        assert pad("ABC", 6) == "ABC   "

    def test_already_wider(self):
        assert pad("ABCDEF", 4) == "ABCDEF"
