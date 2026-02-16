# Product Spec (Draft)

## Problem
MkDocs projects frequently need deliverables beyond HTML. PDF plugins exist, but DOCX support is fragmented and maintenance is inconsistent.

## Goal
Provide one MkDocs plugin that can export documentation into DOCX and PDF in a reproducible way.

## Target users
- Technical writers using MkDocs as source of truth.
- Engineering teams requiring DOCX/PDF artifacts for compliance or customer delivery.

## MVP scope
- Single combined output file per format.
- Formats: DOCX and PDF.
- Execution at `on_post_build`.
- Pandoc-backed conversion.
- Optional DOCX reference template.

## Out of scope for MVP
- Per-page DOCX/PDF output.
- WYSIWYG-perfect parity with browser-rendered theme.
- Rich asset post-processing beyond Pandoc defaults.

## Functional requirements
- Export when `enabled=true`.
- Respect `formats` order from config.
- Write artifacts to configurable output directory.
- Fail fast with clear error when converter is unavailable.

## Non-functional requirements
- Deterministic outputs from same input/config.
- Works in CI and local runs.
- Good diagnostics via MkDocs plugin logs.
