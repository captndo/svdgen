"""Structured diagnostics for SVD parsing and generation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Diagnostic:
    """A single diagnostic message tied to a source location."""

    severity: Severity
    message: str
    file_path: Path | None = None
    element_path: str | None = None
    line: int | None = None

    def __str__(self) -> str:
        parts: list[str] = [f"[{self.severity.value.upper()}]"]
        if self.file_path is not None:
            loc = str(self.file_path)
            if self.line is not None:
                loc += f":{self.line}"
            parts.append(loc)
        if self.element_path is not None:
            parts.append(f"({self.element_path})")
        parts.append(self.message)
        return " ".join(parts)


class DiagnosticCollector:
    """Accumulates diagnostics during a pipeline run."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def add(self, diagnostic: Diagnostic) -> None:
        self._items.append(diagnostic)

    def info(self, message: str, **kwargs: object) -> None:
        self.add(Diagnostic(severity=Severity.INFO, message=message, **kwargs))  # type: ignore[arg-type]

    def warning(self, message: str, **kwargs: object) -> None:
        self.add(Diagnostic(severity=Severity.WARNING, message=message, **kwargs))  # type: ignore[arg-type]

    def error(self, message: str, **kwargs: object) -> None:
        self.add(Diagnostic(severity=Severity.ERROR, message=message, **kwargs))  # type: ignore[arg-type]

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return list(self._items)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self._items)

    @property
    def has_warnings(self) -> bool:
        return any(d.severity == Severity.WARNING for d in self._items)

    def filter(self, severity: Severity) -> list[Diagnostic]:
        return [d for d in self._items if d.severity == severity]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self._items)


class ParseError(Exception):
    """Raised when SVD parsing fails fatally."""

    def __init__(self, message: str, diagnostics: list[Diagnostic] | None = None) -> None:
        super().__init__(message)
        self.diagnostics: list[Diagnostic] = diagnostics or []
