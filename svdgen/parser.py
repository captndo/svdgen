"""SVD parsing — thin wrapper around cmsis-svd with structured diagnostics."""

from __future__ import annotations

import io
import re
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from cmsis_svd.model import SVDDevice
from cmsis_svd.parser import SVDParser, SVDParserValidationError

from .diagnostics import Diagnostic, DiagnosticCollector, ParseError, Severity
from .source import SourceMap

_WARNING_RE = re.compile(r"^\[WARNING\]\s*(.+)$")


@dataclass
class ParseResult:
    """Outcome of parsing an SVD file."""

    device: SVDDevice
    diagnostics: list[Diagnostic]
    source_map: SourceMap


def parse_svd(
    path: str | Path,
    *,
    validate: bool = False,
) -> ParseResult:
    """Parse a CMSIS-SVD file into a device model with diagnostics.

    Args:
        path: Path to the ``.svd`` file.
        validate: Validate the XML against the CMSIS-SVD schema before parsing.

    Returns:
        A :class:`ParseResult` containing the parsed device, accumulated
        diagnostics, and a :class:`SourceMap` for tracing elements back to
        source locations.

    Raises:
        ParseError: If parsing or validation fails fatally.
        FileNotFoundError: If *path* does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SVD file not found: {path}")

    collector = DiagnosticCollector()

    source_map = _build_source_map(path, collector)
    device = _parse_device(path, validate, collector)

    return ParseResult(
        device=device,
        diagnostics=collector.diagnostics,
        source_map=source_map,
    )


# -- internal helpers ---------------------------------------------------------


def _build_source_map(path: Path, collector: DiagnosticCollector) -> SourceMap:
    try:
        return SourceMap.from_svd(path)
    except Exception as exc:
        collector.warning(f"Failed to build source map: {exc}", file_path=path)
        return SourceMap(path)


def _parse_device(
    path: Path, validate: bool, collector: DiagnosticCollector
) -> SVDDevice:
    try:
        svd_parser = SVDParser.for_xml_file(str(path))
        with _capture_stdout() as buf:
            device = svd_parser.get_device(xml_validation=validate)

        for diag in _extract_warnings(buf.getvalue(), path):
            collector.add(diag)

        return device

    except SVDParserValidationError as exc:
        collector.error(str(exc), file_path=path)
        raise ParseError(
            f"SVD validation failed: {path}",
            diagnostics=collector.diagnostics,
        ) from exc
    except ParseError:
        raise
    except Exception as exc:
        collector.error(f"SVD parsing failed: {exc}", file_path=path)
        raise ParseError(
            f"Failed to parse SVD file: {path}",
            diagnostics=collector.diagnostics,
        ) from exc


@contextmanager
def _capture_stdout() -> Generator[io.StringIO, None, None]:
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old


def _extract_warnings(captured: str, file_path: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for raw_line in captured.splitlines():
        text = raw_line.strip()
        if not text:
            continue
        match = _WARNING_RE.match(text)
        msg = match.group(1) if match else text
        diagnostics.append(
            Diagnostic(severity=Severity.WARNING, message=msg, file_path=file_path)
        )
    return diagnostics
