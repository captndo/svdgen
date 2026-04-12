"""Render engine — Jinja template rendering with scope iteration and path resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from . import __version__
from .diagnostics import Diagnostic, DiagnosticCollector
from .filters import register_filters
from .model import Device

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATE_DIR = Path(__file__).parent / "templates"


class Scope(Enum):
    DEVICE = "device"
    PERIPHERAL = "peripheral"
    REGISTER = "register"


@dataclass(frozen=True)
class OutputTarget:
    """Declarative definition of a single output artifact (or series of artifacts)."""

    name: str
    template: str
    output_path: str
    scope: Scope = Scope.DEVICE
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderArtifact:
    """A rendered template ready to be written to disk."""

    path: str
    content: str
    target_name: str


@dataclass
class RenderResult:
    """Outcome of rendering all targets."""

    artifacts: list[RenderArtifact]
    diagnostics: list[Diagnostic]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _provenance_context(
    input_source: str | None = None,
    include_timestamp: bool = False,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "svdgen_version": __version__,
    }
    if input_source is not None:
        ctx["input_source"] = input_source
    if include_timestamp:
        import datetime

        ctx["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return ctx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_targets(
    device: Device,
    targets: list[OutputTarget],
    template_dirs: list[str | Path] | None = None,
    *,
    input_source: str | None = None,
    include_timestamp: bool = False,
    extra_context: dict[str, Any] | None = None,
    custom_filters: dict[str, Any] | None = None,
    custom_globals: dict[str, Any] | None = None,
) -> RenderResult:
    """Render all *targets* against the normalized *device* model.

    Args:
        device: The (possibly patched) normalized device model.
        targets: Output target definitions.
        template_dirs: Directories to search for templates.  The built-in
            template directory is always appended as a fallback.
        input_source: SVD file path for provenance metadata.
        include_timestamp: Include generation timestamp in provenance
            (breaks determinism).
        extra_context: Additional variables available in all templates.
        custom_filters: User-defined Jinja filters merged after built-ins.
            Keys are filter names, values are callables.  May override
            built-in filters.
        custom_globals: User-defined Jinja globals available in all
            templates (functions, constants, etc.).

    Returns:
        A :class:`RenderResult` with rendered artifacts and diagnostics.
    """
    collector = DiagnosticCollector()

    search_path = [str(p) for p in (template_dirs or [])]
    search_path.append(str(BUILTIN_TEMPLATE_DIR))

    env = Environment(
        loader=FileSystemLoader(search_path),
        keep_trailing_newline=True,
        lstrip_blocks=True,
        trim_blocks=True,
    )
    register_filters(env)

    if custom_filters:
        env.filters.update(custom_filters)
    if custom_globals:
        env.globals.update(custom_globals)

    provenance = _provenance_context(input_source, include_timestamp)
    base_ctx: dict[str, Any] = {
        "device": device,
        "provenance": provenance,
        **(extra_context or {}),
    }

    artifacts: list[RenderArtifact] = []
    for target in targets:
        artifacts.extend(_render_target(env, device, target, base_ctx, collector))

    _check_collisions(artifacts, collector)

    return RenderResult(artifacts=artifacts, diagnostics=collector.diagnostics)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _render_target(
    env: Environment,
    device: Device,
    target: OutputTarget,
    base_ctx: dict[str, Any],
    collector: DiagnosticCollector,
) -> list[RenderArtifact]:
    try:
        template = env.get_template(target.template)
    except TemplateNotFound:
        collector.error(f"Template not found: {target.template!r}")
        return []

    path_template = env.from_string(target.output_path)

    artifacts: list[RenderArtifact] = []
    for scope_ctx in _iterate_scope(device, target.scope):
        ctx = {**base_ctx, **target.variables, **scope_ctx}
        try:
            content = template.render(ctx)
            resolved_path = path_template.render(ctx)
        except Exception as exc:
            collector.error(
                f"Render failed for target {target.name!r}: {exc}",
                element_path=scope_ctx.get("_scope_label"),
            )
            continue

        artifacts.append(
            RenderArtifact(
                path=resolved_path,
                content=content,
                target_name=target.name,
            )
        )

    return artifacts


def _iterate_scope(device: Device, scope: Scope) -> list[dict[str, Any]]:
    if scope == Scope.DEVICE:
        return [{"_scope_label": device.name}]

    if scope == Scope.PERIPHERAL:
        return [
            {
                "peripheral": p,
                "_scope_label": p.name,
            }
            for p in device.peripherals
            if p.enabled
        ]

    if scope == Scope.REGISTER:
        contexts: list[dict[str, Any]] = []
        for p in device.peripherals:
            if not p.enabled:
                continue
            for r in p.registers:
                if not r.enabled:
                    continue
                contexts.append(
                    {
                        "peripheral": p,
                        "register": r,
                        "_scope_label": f"{p.name}.{r.name}",
                    }
                )
        return contexts

    return []


def _check_collisions(artifacts: list[RenderArtifact], collector: DiagnosticCollector) -> None:
    seen: dict[str, str] = {}
    for art in artifacts:
        if art.path in seen:
            collector.error(
                f"Output path collision: {art.path!r} produced by "
                f"targets {seen[art.path]!r} and {art.target_name!r}"
            )
        else:
            seen[art.path] = art.target_name
