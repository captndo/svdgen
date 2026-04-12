"""Built-in Jinja filters for template rendering."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jinja2 import Environment

    from .model import AccessType, Field

# ---------------------------------------------------------------------------
# Case conversion
# ---------------------------------------------------------------------------

_WORD_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])|[_\-\s]+")
_NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")


def _split_words(name: str) -> list[str]:
    def _repl(m: re.Match[str]) -> str:
        return f"{m.group(1)} {m.group(2)}" if m.group(1) else " "

    spaced = _WORD_BOUNDARY.sub(_repl, name)
    return [w for w in _NON_ALNUM.sub(" ", spaced).split() if w]


def upper_snake(name: str) -> str:
    """``MyPeripheral`` → ``MY_PERIPHERAL``"""
    return "_".join(w.upper() for w in _split_words(name))


def lower_snake(name: str) -> str:
    """``MyPeripheral`` → ``my_peripheral``"""
    return "_".join(w.lower() for w in _split_words(name))


def camel_case(name: str) -> str:
    """``my_reg`` → ``MyReg``"""
    return "".join(w.capitalize() for w in _split_words(name))


# ---------------------------------------------------------------------------
# Numeric formatting
# ---------------------------------------------------------------------------


def hex_format(value: int | None, width: int = 8) -> str:
    """Format *value* as zero-padded hexadecimal: ``0x00004000``."""
    if value is None:
        return "0x" + "?" * width
    return f"0x{value:0{width}X}"


# ---------------------------------------------------------------------------
# Comment formatting
# ---------------------------------------------------------------------------


def c_comment(text: str | None) -> str:
    """Wrap *text* in a C block comment: ``/* text */``."""
    if not text:
        return "/* */"
    return f"/* {text} */"


def c_line_comment(text: str | None) -> str:
    """Format *text* as a C line comment: ``// text``."""
    if not text:
        return "//"
    return f"// {text}"


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

_ACCESS_SHORT: dict[str, str] = {
    "read-only": "RO",
    "write-only": "WO",
    "read-write": "RW",
    "write-once": "W1",
    "read-write-once": "RW1",
}


def access_str(access: AccessType | str | None) -> str:
    """Short human-readable access label: ``RW``, ``RO``, ``WO``."""
    if access is None:
        return ""
    val = access.value if hasattr(access, "value") else str(access)
    return _ACCESS_SHORT.get(val, val)


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def bit_range(field: Field | object) -> str:
    """Format a field's bit range: ``[3:0]``."""
    msb = getattr(field, "msb", None)
    lsb = getattr(field, "lsb", None)
    if msb is not None and lsb is not None:
        return f"[{msb}:{lsb}]"
    return ""


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------


def pad(text: str, width: int) -> str:
    """Right-pad *text* to *width* characters."""
    return str(text).ljust(width)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_filters(env: Environment) -> None:
    """Register all built-in svdgen filters on a Jinja *env*."""
    env.filters["upper_snake"] = upper_snake
    env.filters["lower_snake"] = lower_snake
    env.filters["camel_case"] = camel_case
    env.filters["hex"] = hex_format
    env.filters["c_comment"] = c_comment
    env.filters["c_line_comment"] = c_line_comment
    env.filters["access_str"] = access_str
    env.filters["bit_range"] = bit_range
    env.filters["pad"] = pad
