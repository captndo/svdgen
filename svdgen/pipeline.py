"""Pipeline orchestrator — run the full generation pipeline from config."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import ProjectConfig, validate_config
from .diagnostics import Diagnostic, Severity
from .model import Device
from .normalize import normalize
from .parser import ParseError, parse_svd
from .patch import apply_patches, load_patches
from .render import OutputTarget, RenderArtifact, Scope, render_targets
from .writer import write_artifacts


@dataclass
class PipelineResult:
    """Outcome of a full pipeline run."""

    device: Device | None = None
    artifacts: list[RenderArtifact] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    success: bool = False


def run(
    config: ProjectConfig,
    *,
    dry_run: bool = False,
    custom_filters: dict | None = None,
    custom_globals: dict | None = None,
) -> PipelineResult:
    """Execute the full pipeline driven by *config*.

    Stages: parse → normalize → patch → render → write.

    Args:
        config: Loaded and (optionally) validated project configuration.
        dry_run: If True, render but do not write files to disk.
        custom_filters: User-defined Jinja filters forwarded to the
            render stage.  Keys are filter names, values are callables.
        custom_globals: User-defined Jinja globals forwarded to the
            render stage (functions, constants, etc.).

    Returns:
        A :class:`PipelineResult` with the final device model, rendered
        artifacts, and accumulated diagnostics from all stages.
    """
    result = PipelineResult()
    all_diags: list[Diagnostic] = []

    # -- validate config -----------------------------------------------------
    config_diags = validate_config(config)
    all_diags.extend(config_diags)
    if _has_errors(config_diags):
        result.diagnostics = all_diags
        return result

    # -- parse ---------------------------------------------------------------
    try:
        parse_result = parse_svd(config.input.svd, validate=config.validation.strict)
    except ParseError as exc:
        all_diags.extend(exc.diagnostics)
        result.diagnostics = all_diags
        return result

    all_diags.extend(parse_result.diagnostics)

    # -- normalize -----------------------------------------------------------
    device = normalize(parse_result)

    # -- patch ---------------------------------------------------------------
    for patch_path in config.patches.files:
        try:
            patch_set = load_patches(patch_path)
        except (FileNotFoundError, ValueError) as exc:
            all_diags.append(Diagnostic(
                severity=Severity.ERROR,
                message=str(exc),
                file_path=patch_path,
            ))
            result.diagnostics = all_diags
            return result

        patch_result = apply_patches(device, patch_set)
        all_diags.extend(patch_result.diagnostics)
        if _has_errors(patch_result.diagnostics):
            result.device = patch_result.device
            result.diagnostics = all_diags
            return result
        device = patch_result.device

    result.device = device

    # -- render --------------------------------------------------------------
    targets = [_target_from_config(tc) for tc in config.targets]
    template_dirs = list(config.templates.dirs)

    render_result = render_targets(
        device,
        targets,
        template_dirs or None,
        input_source=str(config.input.svd),
        include_timestamp=config.generation.include_timestamp,
        custom_filters=custom_filters,
        custom_globals=custom_globals,
    )
    all_diags.extend(render_result.diagnostics)
    result.artifacts = render_result.artifacts

    if _has_errors(render_result.diagnostics):
        result.diagnostics = all_diags
        return result

    # -- write ---------------------------------------------------------------
    if not dry_run:
        write_diags = write_artifacts(
            render_result.artifacts,
            config.output.dir,
            overwrite=config.output.overwrite,
            skip_unchanged=config.output.skip_unchanged,
        )
        all_diags.extend(write_diags)

    result.diagnostics = all_diags
    result.success = not _has_errors(all_diags)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _target_from_config(tc: ProjectConfig) -> OutputTarget:
    from .config import TargetConfig
    assert isinstance(tc, TargetConfig)
    return OutputTarget(
        name=tc.name,
        template=tc.template,
        output_path=tc.output_path,
        scope=Scope(tc.scope),
        variables=tc.variables,
    )


def _has_errors(diags: list[Diagnostic]) -> bool:
    return any(d.severity == Severity.ERROR for d in diags)
