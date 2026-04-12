"""Declarative TOML project configuration — load, model, and validate."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

from .diagnostics import Diagnostic, DiagnosticCollector
from .render import BUILTIN_TEMPLATE_DIR, Scope

# ---------------------------------------------------------------------------
# Config data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InputConfig:
    """SVD input file configuration."""

    svd: Path = field(default_factory=lambda: Path("device.svd"))


@dataclass(frozen=True)
class PatchConfig:
    """Patch file paths applied after normalization."""

    files: tuple[Path, ...] = ()


@dataclass(frozen=True)
class TemplateConfig:
    """Directories searched for Jinja templates."""

    dirs: tuple[Path, ...] = ()


@dataclass(frozen=True)
class OutputConfig:
    """Output directory and write-behaviour settings."""

    dir: Path = field(default_factory=lambda: Path("output"))
    overwrite: bool = True
    skip_unchanged: bool = True


@dataclass(frozen=True)
class TargetConfig:
    """A single output target definition within the project config."""

    name: str = ""
    template: str = ""
    output_path: str = ""
    scope: str = "device"
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationConfig:
    """Options controlling generation behaviour."""

    include_timestamp: bool = False


@dataclass(frozen=True)
class ValidationConfig:
    """Options controlling parse-time validation."""

    strict: bool = False


@dataclass(frozen=True)
class ProjectConfig:
    """Root configuration object."""

    project_name: str = ""
    project_description: str = ""
    input: InputConfig = field(default_factory=InputConfig)
    patches: PatchConfig = field(default_factory=PatchConfig)
    templates: TemplateConfig = field(default_factory=TemplateConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    targets: tuple[TargetConfig, ...] = ()
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> ProjectConfig:
    """Load a project configuration from a TOML file.

    All relative paths in the config are resolved against the directory
    containing the config file.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the TOML is structurally invalid for svdgen.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    config_dir = path.parent.resolve()
    return _build_config(raw, config_dir)


def _build_config(raw: dict[str, Any], config_dir: Path) -> ProjectConfig:
    proj = raw.get("project", {})
    inp = raw.get("input", {})
    pat = raw.get("patches", {})
    tpl = raw.get("templates", {})
    out = raw.get("output", {})
    gen = raw.get("generation", {})
    val = raw.get("validation", {})
    raw_targets = raw.get("targets", [])

    input_cfg = InputConfig(
        svd=config_dir / inp.get("svd", "device.svd"),
    )

    patch_cfg = PatchConfig(
        files=tuple(config_dir / p for p in pat.get("files", [])),
    )

    template_cfg = TemplateConfig(
        dirs=tuple(config_dir / d for d in tpl.get("dirs", [])),
    )

    output_cfg = OutputConfig(
        dir=config_dir / out.get("dir", "output"),
        overwrite=out.get("overwrite", True),
        skip_unchanged=out.get("skip_unchanged", True),
    )

    targets = tuple(_build_target(t, i) for i, t in enumerate(raw_targets))

    generation_cfg = GenerationConfig(
        include_timestamp=gen.get("include_timestamp", False),
    )

    validation_cfg = ValidationConfig(
        strict=val.get("strict", False),
    )

    return ProjectConfig(
        project_name=proj.get("name", ""),
        project_description=proj.get("description", ""),
        input=input_cfg,
        patches=patch_cfg,
        templates=template_cfg,
        output=output_cfg,
        targets=targets,
        generation=generation_cfg,
        validation=validation_cfg,
        config_dir=config_dir,
    )


def _build_target(raw: dict[str, Any], index: int) -> TargetConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"Target entry {index} must be a table, got {type(raw).__name__}")
    name = raw.get("name", "")
    if not name:
        raise ValueError(f"Target entry {index} missing required 'name'")

    template = raw.get("template", "")
    if not template:
        raise ValueError(f"Target {name!r} missing required 'template'")

    output_path = raw.get("output_path", "")
    if not output_path:
        raise ValueError(f"Target {name!r} missing required 'output_path'")

    return TargetConfig(
        name=name,
        template=template,
        output_path=output_path,
        scope=raw.get("scope", "device"),
        variables=raw.get("variables", {}),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_VALID_SCOPES = {s.value for s in Scope}


def validate_config(config: ProjectConfig) -> list[Diagnostic]:
    """Validate a loaded config, checking file existence and target correctness.

    Returns a list of diagnostics (errors and warnings).
    """
    collector = DiagnosticCollector()

    if not config.input.svd.exists():
        collector.error(f"SVD file not found: {config.input.svd}")

    for pf in config.patches.files:
        if not pf.exists():
            collector.error(f"Patch file not found: {pf}")

    for td in config.templates.dirs:
        if not td.is_dir():
            collector.error(f"Template directory not found: {td}")

    seen_names: set[str] = set()
    for target in config.targets:
        if target.name in seen_names:
            collector.error(f"Duplicate target name: {target.name!r}")
        seen_names.add(target.name)

        if target.scope not in _VALID_SCOPES:
            collector.error(
                f"Target {target.name!r}: invalid scope {target.scope!r}; "
                f"valid: {sorted(_VALID_SCOPES)}"
            )

        _check_template_resolvable(config, target, collector)

    return collector.diagnostics


def _check_template_resolvable(
    config: ProjectConfig,
    target: TargetConfig,
    collector: DiagnosticCollector,
) -> None:
    search_dirs = list(config.templates.dirs) + [BUILTIN_TEMPLATE_DIR]
    for d in search_dirs:
        if (d / target.template).exists():
            return
    collector.warning(
        f"Target {target.name!r}: template {target.template!r} not found in any template directory"
    )
