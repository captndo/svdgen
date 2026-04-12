"""File writer — deterministic, atomic, skip-unchanged output writing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .diagnostics import Diagnostic, DiagnosticCollector
from .render import RenderArtifact


def write_artifacts(
    artifacts: list[RenderArtifact],
    output_dir: str | Path,
    *,
    overwrite: bool = True,
    skip_unchanged: bool = True,
) -> list[Diagnostic]:
    """Write rendered artifacts to *output_dir*.

    Args:
        artifacts: Artifacts from :func:`render_targets`.
        output_dir: Root directory for output files.
        overwrite: Allow overwriting existing files.
        skip_unchanged: Skip writes when file content is identical.

    Returns:
        Diagnostics produced during writing.
    """
    output_dir = Path(output_dir).resolve()
    collector = DiagnosticCollector()

    for artifact in sorted(artifacts, key=lambda a: a.path):
        _write_one(artifact, output_dir, overwrite, skip_unchanged, collector)

    return collector.diagnostics


def _write_one(
    artifact: RenderArtifact,
    output_dir: Path,
    overwrite: bool,
    skip_unchanged: bool,
    collector: DiagnosticCollector,
) -> None:
    dest = (output_dir / artifact.path).resolve()

    if not str(dest).startswith(str(output_dir)):
        collector.error(
            f"Path traversal blocked: {artifact.path!r} resolves outside output directory"
        )
        return

    if dest.exists():
        if not overwrite:
            collector.warning(f"Skipping existing file (overwrite=False): {dest}")
            return
        if skip_unchanged and dest.read_text(encoding="utf-8") == artifact.content:
            collector.info(f"Unchanged, skipping: {dest}")
            return

    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=dest.parent, prefix=".svdgen_")
        try:
            os.write(fd, artifact.content.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp_path, dest)
    except OSError as exc:
        collector.error(f"Failed to write {dest}: {exc}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
