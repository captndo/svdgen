
# Requirements Document — OSS Hardware Description Generation Engine

## 1. Purpose

Define requirements for an open-source tool that ingests CMSIS-SVD hardware descriptions, normalizes and patches them, and generates arbitrary text artifacts through templates.

This document describes product requirements and roadmap goals, including features not yet implemented. For current behavior, see the [User Guide](guide.md) and [Pipeline Architecture](pipeline.md).

## 2. Scope

### In Scope

* CMSIS-SVD input parsing
* Normalized internal device model
* Patch/override system
* Template-driven text generation
* Multi-file and multi-target output generation
* Declarative project configuration
* CLI
* Python API
* Validation and inspection tooling
* Deterministic generation
* Built-in example templates

### Out of Scope

* IDE features
* Driver implementation generation beyond templated output
* Hosted collaboration platform
* Vendor SDK replacement
* Graphical UI
* Full support for all hardware description formats in initial OSS release

## 3. Product Definition

An OSS engine that executes the pipeline:

**Parse → Normalize → Patch → Validate → Render → Write Outputs**

## 4. Target Users

* Embedded developers
* Firmware teams
* Tooling engineers
* Build/CI engineers
* Open-source maintainers of device support packages

## 5. Primary Use Cases

* Generate C headers from SVD with custom naming and file layout
* Generate register maps and documentation from one source
* Patch broken vendor SVDs without editing originals
* Generate multiple artifacts from one device definition in CI
* Inspect and validate hardware metadata before generation
* Reuse templates across projects and devices

## 6. Functional Requirements

### 6.1 Input Parsing

* The system shall accept one or more CMSIS-SVD files as input.
* The system shall parse CMSIS-SVD into an internal structured representation.
* The system shall report parsing errors with file path, location if available, and failing construct.
* The system shall preserve source metadata sufficient for traceability.
* The system should tolerate common vendor SVD inconsistencies where feasible.
* The system may support additional metadata sidecar files in future versions.

### 6.2 Normalized Internal Model

* The system shall define a normalized model for:

  * device
  * CPU metadata
  * peripheral
  * cluster
  * register
  * field
  * enumerated values
  * address blocks
  * interrupts
* The system shall expose normalized values independent of raw SVD irregularities.
* The system shall preserve access to raw source values where needed for debugging.
* The system shall make the normalized model available to templates and the Python API.
* The system shall provide a stable model contract within a major version.

### 6.3 Patch and Override System

* The system shall support external patch files.
* Patch files shall be applied after parsing and before rendering.
* Patch files shall allow:

  * rename node
  * override description
  * override access type
  * override reset value
  * add missing metadata
  * remove node
  * disable node
  * override display/naming metadata
* The system shall reject patches targeting nonexistent nodes unless explicitly configured otherwise.
* The system shall produce actionable errors for invalid patches.
* The system shall support deterministic patch ordering.
* The system should support layered patch sets.
* The system should support patch scoping per device/peripheral.

### 6.4 Template-Based Generation

* The system shall support text generation through Jinja templates.
* The system shall support generating multiple output files in one run.
* The system shall support user-defined output paths and directory structures.
* The system shall expose a documented template context.
* The system shall support reusable template partials/includes.
* The system shall support reusable filters/helpers.
* The system shall allow multiple output targets using the same normalized model.
* The system shall support generation of arbitrary text-based artifacts.
* The system shall not be limited to C output.

### 6.5 Output Definition

* The system shall allow declarative output target definitions.
* Each output target shall define:

  * template source
  * output path or path pattern
  * scope
  * optional target-specific settings
* The system shall support target scopes such as:

  * device-level
  * peripheral-level
  * register-level
  * custom collection scope
* The system shall detect output path collisions.
* The system shall fail or warn on collisions based on configuration.

### 6.6 Project Configuration

* The system shall support a declarative project config file.
* The configuration shall define:

  * input files
  * patch files
  * template directories
  * output targets
  * naming/style settings
  * validation settings
  * write behavior
* The configuration format shall be human-readable.
* The configuration shall be schema-validated.
* The system should use TOML unless implementation constraints require otherwise.

### 6.7 Validation

* The system shall validate:

  * parse success
  * config correctness
  * patch correctness
  * normalized model consistency
  * output target correctness
  * template reference availability
  * output collision conditions
* The system shall emit actionable validation errors.
* The system should support a validation-only mode.
* The system should support warning levels and strict mode.

### 6.8 Inspection and Introspection

* The system shall support inspection of parsed and normalized data.
* The system shall provide CLI commands to inspect devices, peripherals, registers, and fields.
* The system shall support exporting the normalized model in machine-readable form.
* The system should support JSON export.
* The system may support YAML export.

### 6.9 CLI

* The system shall provide a CLI.
* The CLI shall support at minimum:

  * generate
  * validate
  * inspect
  * list
* The CLI should support:

  * dry-run
  * export-model
  * explain-patch
  * diff-preview
* CLI output shall be suitable for CI usage.
* CLI exit codes shall distinguish success, validation failure, and runtime failure.

### 6.10 Python API

* The system shall provide a Python API.
* The API shall support:

  * parsing input
  * loading config
  * applying patches
  * accessing normalized model
  * rendering templates
  * writing outputs
  * registering custom filters/helpers
* The Python API shall be documented.
* The Python API should enable embedding in external tooling.

### 6.11 File Writing Behavior

* The system shall write generated files deterministically.
* The system shall support safe overwrite behavior.
* The system shall not overwrite unrelated files outside configured outputs.
* The system should support an atomic write strategy where practical.
* The system should support preserving unchanged files to reduce churn.

### 6.12 Provenance

* The system shall support generation metadata in outputs.
* Generated files should be able to include:

  * generator name/version
  * input source
  * patch set identifiers
  * generation timestamp if enabled
* The system should allow disabling timestamps to preserve determinism.

## 7. Non-Functional Requirements

### 7.1 Determinism

* Given identical inputs, config, patches, templates, and tool version, output shall be identical across runs on the same platform.
* Output ordering shall be stable.

### 7.2 Traceability

* The system shall allow tracing generated content back to source model elements.
* The system shall preserve enough metadata for debugging generation issues.

### 7.3 Extensibility

* The architecture shall support future addition of:

  * new input adapters
  * new patch operations
  * new render helpers
  * new output target types
* Extension mechanisms shall not require modifying the core for common template customization.

### 7.4 Reliability

* The system shall fail fast on invalid configuration or broken patches.
* The system shall not silently skip invalid operations unless explicitly configured.

### 7.5 Usability

* Error messages shall identify the failing file, object, and operation where possible.
* CLI help shall be complete enough for standalone use.
* Documentation shall cover common workflows.

### 7.6 Performance

* The system should handle typical MCU SVD inputs and multi-file generation within practical local development times.
* Performance optimization is secondary to correctness and debuggability in the OSS core.

### 7.7 Testability

* The system shall be covered by automated tests for:

  * parser integration
  * normalization
  * patching
  * config validation
  * rendering
  * golden outputs
  * regression cases for malformed or vendor-quirky SVDs

## 8. Data Model Requirements

## 8.1 Required Core Entities

* Device
* CPU
* Peripheral
* Register
* Field
* EnumeratedValueSet
* Interrupt
* AddressBlock

## 8.2 Required Core Attributes

Each entity shall expose applicable metadata including:

* canonical name
* original/raw name if different
* description
* address or offset
* width/size
* access type
* reset value and mask where available
* derived-from relationship where applicable
* source reference metadata

## 8.3 Naming Requirements

* The system shall maintain canonical internal identifiers.
* The system shall allow target-specific rendered naming via helpers or templates.
* The system should support naming normalization rules in configuration.

## 9. Patch System Requirements

## 9.1 Patch Operations

Initial OSS patch operations shall include:

* rename
* set property
* remove
* disable
* add property
* override description
* override access
* override reset metadata

## 9.2 Patch Targeting

* Patches shall target nodes by stable selectors.
* Selectors shall support hierarchical addressing.
* Selector resolution shall be deterministic.
* Ambiguous selectors shall fail unless explicitly disambiguated.

## 9.3 Patch Ordering

* Patch application order shall be defined and documented.
* Later patches may override earlier patches.
* Order-dependent behavior shall be visible and testable.

## 10. Template System Requirements

## 10.1 Template Context

The template context shall provide access to:

* global config
* device model
* current render scope
* helper filters/functions
* source metadata where appropriate

## 10.2 Template Utilities

The OSS core should provide helpers for:

* identifier normalization
* case conversion
* comment formatting
* numeric formatting
* address formatting
* access flag interpretation
* description cleanup

## 10.3 Template Packaging

* The system shall support loading templates from configured directories.
* The system should support reusable shared template libraries.
* The system may support template package discovery in future versions.

## 11. CLI Feature Breakdown

### 11.1 generate

Purpose:

* Execute full pipeline and write outputs

Required behavior:

* load config
* parse inputs
* apply patches
* validate
* render outputs
* write files
* report summary

### 11.2 validate

Purpose:

* Validate config, inputs, patches, and generation setup without writing files

Required behavior:

* no output file writes
* nonzero exit code on validation failure

### 11.3 inspect

Purpose:

* Show parsed/normalized model details

Required behavior:

* inspect device/peripheral/register/field by selector
* machine-readable output option

### 11.4 list

Purpose:

* Enumerate available model elements or configured targets

Required behavior:

* list devices
* list peripherals
* list registers
* list output targets
* list templates if configured

### 11.5 export-model

Optional initial feature:

* export normalized model as JSON

### 11.6 dry-run

Optional initial feature:

* render/write plan without file writes

## 12. Python API Feature Breakdown

### 12.1 Parse API

* Load SVD input
* Return parsed model or normalized model

### 12.2 Patch API

* Load patch files
* Apply patch sets
* Report patch results

### 12.3 Validation API

* Validate config and model state
* Return structured diagnostics

### 12.4 Rendering API

* Render one or more targets
* Return generated artifact objects before write

### 12.5 Write API

* Persist generated artifacts to disk with configured overwrite policy

### 12.6 Extension API

* Register custom Jinja filters
* Register custom preprocessors if allowed by architecture
* Register naming helpers

## 13. Configuration Feature Breakdown

### Required Configuration Sections

* project metadata
* input definitions
* patch definitions
* template paths
* output targets
* global generation options
* validation options

### Required Output Target Fields

* name
* scope
* template
* output path pattern

### Optional Output Target Fields

* condition
* custom variables
* formatting flags
* overwrite policy
* include/exclude filters

## 14. Release Breakdown

## 14.1 OSS MVP

Required for first useful release:

* single CMSIS-SVD input
* normalized internal model
* external patch file support
* Jinja rendering
* multi-file generation
* declarative config
* CLI: generate, validate, inspect
* Python API
* JSON model export
* built-in sample C header templates
* deterministic output
* automated tests

## 14.2 Post-MVP OSS

* layered patch sets
* multi-input composition
* dry-run mode
* diff preview
* shared template libraries
* richer selectors
* incremental regeneration
* additional built-in templates
* richer diagnostics

## 15. Acceptance Criteria

### Parsing

* Given a valid CMSIS-SVD file, the system parses it into the normalized model without manual intervention.
* Given an invalid SVD, the system reports actionable errors.

### Patching

* Given a valid patch set, the system applies changes deterministically.
* Given an invalid patch selector, the system fails with a precise diagnostic.

### Generation

* Given config, templates, and valid inputs, the system generates the expected files in expected locations.
* Multi-file generation works from one run.

### Validation

* Validation mode detects config, patch, and target errors without writing files.

### Determinism

* Repeated runs with unchanged inputs produce byte-identical outputs, excluding explicitly enabled nondeterministic metadata.

### Inspection

* Users can inspect normalized model elements through CLI and machine-readable export.

### API

* Python consumers can perform parse, patch, validate, render, and write flows programmatically.

## 16. Suggested Backlog Structure

### Epic 1 — Parsing

* SVD loader
* parse diagnostics
* source metadata preservation

### Epic 2 — Normalization

* canonical data model
* normalization transforms
* raw-to-normalized mapping

### Epic 3 — Patching

* patch schema
* selector engine
* patch executor
* patch diagnostics

### Epic 4 — Rendering

* Jinja integration
* target scopes
* output path resolution
* helper/filter library

### Epic 5 — Configuration

* config schema
* config loader
* config validation

### Epic 6 — CLI

* generate command
* validate command
* inspect command
* list command

### Epic 7 — Python API

* public API surface
* docs
* examples

### Epic 8 — Quality

* golden tests
* regression corpus
* deterministic write behavior
* CI setup

## 17. Deliverables

* CLI tool
* Python package
* Config schema
* Patch schema
* Built-in example templates
* User documentation
* API documentation
* Test suite
* Example project using a real CMSIS-SVD file

## 18. Recommended Document Identifier

**Project Name:** `svdgen`
**Document Type:** OSS Product Requirements Document
**Version:** 0.1.0
