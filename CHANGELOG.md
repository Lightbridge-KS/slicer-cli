# Changelog

All notable changes to `slicer-cli` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is in `0.x`, breaking changes may occur on minor version bumps.

## [Unreleased]

## [0.1.0] - 2026-05-04

First public alpha. Agent-first CLI surface for 3D Slicer's HTTP server,
plus the companion Agent Skills Spec-compliant skill.

### Added

- Core read/write surface: `status`, `doctor`, `scene`, `node`, `volume`,
  `sample`, `api routes/raw`, `config` (Phases 0–1).
- Render commands: `render slice`, `render threed`, `render screenshot`,
  `render gltf`, with PNG validation (magic-bytes + size + IHDR check)
  (Phase 2).
- DICOMweb: `dicom studies/series/instances/instance/meta` (QIDO/WADO)
  and `dicom pull` for Orthanc imports (Phase 2).
- Markup commands (`markup list`, `markup fiducial-set`, `markup line`),
  formal `exec` with audit log, and `gui layout` (Phase 3).
- Companion Agent Skills Spec-compliant skill at
  `.agents/skills/slicer-cli/`, with a `references/` subdirectory
  (`commands`, `errors`, `safety`, `dicomweb`, `troubleshooting`) for
  progressive disclosure (Phase 4).
- Stable error codes (`E_*`) and exit-code mapping per PRD §6.4 / §6.5.
- Layered configuration: flag > env > project `.slicer-cli.toml` > user
  `~/.config/slicer-cli/config.toml` > built-in defaults.
- Reusable typed Python client (`slicer_cli.client.SlicerClient`) on the
  same import surface as the CLI.
- GitHub Actions: CI (lint + format + mypy + unit tests on Python 3.11,
  3.12, 3.13) and Release (wheel + sdist + skill bundle + checksums,
  drafted with notes from this changelog).

### Safety

- Empty MRML selectors refused at the client layer — defends against
  `DELETE /slicer/mrml`'s "clear scene" semantics on missing query args.
- Destructive operations (`scene clear`, `system shutdown`, `exec`)
  gated by named flags (`--confirm`, `--i-understand-the-risk`).
- `/slicer/exec` calls audited to `~/.local/state/slicer-cli/exec.log`.

### Documentation

- README, AGENTS.md, PRD, user manual, surface report, TODOS tracker.
- Companion skill `SKILL.md` plus five focused `references/*.md` files.

[Unreleased]: https://github.com/Lightbridge-KS/slicer-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Lightbridge-KS/slicer-cli/releases/tag/v0.1.0
