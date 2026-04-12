"""svdgen — OSS hardware description generation engine."""

__version__ = "0.1.0"

from .config import (
    GenerationConfig,
    InputConfig,
    OutputConfig,
    PatchConfig,
    ProjectConfig,
    TargetConfig,
    TemplateConfig,
    ValidationConfig,
    load_config,
    validate_config,
)
from .diagnostics import Diagnostic, DiagnosticCollector, ParseError, Severity
from .export import device_to_dict, export_json
from .filters import (
    access_str,
    bit_range,
    c_comment,
    c_line_comment,
    camel_case,
    hex_format,
    lower_snake,
    pad,
    register_filters,
    upper_snake,
)
from .model import (
    CPU,
    AccessType,
    AddressBlock,
    Device,
    EndianType,
    EnumeratedValue,
    EnumeratedValueSet,
    Field,
    Interrupt,
    Peripheral,
    Register,
)
from .normalize import normalize
from .parser import ParseResult, parse_svd
from .patch import PatchResult, PatchSet, apply_patches, load_patches
from .pipeline import PipelineResult, run
from .render import OutputTarget, RenderArtifact, RenderResult, Scope, render_targets
from .source import SourceInfo, SourceMap
from .writer import write_artifacts

__all__ = [
    "CPU",
    "AccessType",
    "AddressBlock",
    "Device",
    "Diagnostic",
    "DiagnosticCollector",
    "EndianType",
    "EnumeratedValue",
    "EnumeratedValueSet",
    "Field",
    "GenerationConfig",
    "InputConfig",
    "Interrupt",
    "OutputConfig",
    "OutputTarget",
    "ParseError",
    "ParseResult",
    "PatchConfig",
    "PatchResult",
    "PatchSet",
    "Peripheral",
    "PipelineResult",
    "ProjectConfig",
    "Register",
    "RenderArtifact",
    "RenderResult",
    "Scope",
    "Severity",
    "SourceInfo",
    "SourceMap",
    "TargetConfig",
    "TemplateConfig",
    "ValidationConfig",
    "access_str",
    "apply_patches",
    "bit_range",
    "c_comment",
    "c_line_comment",
    "camel_case",
    "device_to_dict",
    "export_json",
    "hex_format",
    "lower_snake",
    "load_config",
    "load_patches",
    "normalize",
    "pad",
    "parse_svd",
    "register_filters",
    "render_targets",
    "run",
    "upper_snake",
    "validate_config",
    "write_artifacts",
]
