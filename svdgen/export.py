"""Model serialization — convert the frozen device model to JSON-friendly dicts."""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import IO, Any

from .model import Device


def device_to_dict(device: Device) -> dict[str, Any]:
    """Recursively convert a frozen :class:`Device` tree to plain dicts."""
    return _convert(device)  # type: ignore[return-value]


def export_json(
    device: Device,
    file: IO[str] | None = None,
    *,
    indent: int = 2,
) -> str | None:
    """Serialize *device* to JSON.

    If *file* is given the JSON is written there and ``None`` is returned.
    Otherwise the JSON string is returned.
    """
    data = device_to_dict(device)
    if file is not None:
        json.dump(data, file, indent=indent)
        file.write("\n")
        return None
    return json.dumps(data, indent=indent)


def _convert(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _convert(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (tuple, list)):
        return [_convert(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _convert(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj
