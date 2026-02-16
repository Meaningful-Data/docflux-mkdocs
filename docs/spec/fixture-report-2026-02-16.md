# Fixture Report (2026-02-16)

## Fixtures used

- `/home/aolle/pillar3`
- `/home/aolle/wp-sdmx-dpm`

## Export command path

- Plugin run via MkDocs with temporary config overlays in `/tmp/mkdocs-export-tests/*/mkdocs.export.yml`.
- Plugin settings used for fixtures:
  - `formats: [docx, pdf]`
  - `pdf_strategy: chrome`
  - `mermaid_mode: pre_render`
  - `mermaid_chrome_path: /usr/bin/google-chrome`

## Generated artifacts

### Pillar3 (plugin)

- `/tmp/mkdocs-export-tests/pillar3/exports/pillar3.docx`
- `/tmp/mkdocs-export-tests/pillar3/exports/pillar3.pdf`
- Mermaid assets: 3 PNG files under `/tmp/mkdocs-export-tests/pillar3/exports/_mermaid/`

Metrics:
- DOCX size: 340K
- PDF size: 2.4M
- PDF pages: 139 (A4)

### WP-SDMX-DPM (plugin)

- `/tmp/mkdocs-export-tests/wp-sdmx-dpm/exports/wp-sdmx-dpm.docx`
- `/tmp/mkdocs-export-tests/wp-sdmx-dpm/exports/wp-sdmx-dpm.pdf`
- Mermaid assets: 51 PNG files under `/tmp/mkdocs-export-tests/wp-sdmx-dpm/exports/_mermaid/`

Metrics:
- DOCX size: 1.4M
- PDF size: 3.2M
- PDF pages: 136 (Letter, no custom CSS provided)

## Baseline comparison (existing pillar3 script)

Baseline script: `/home/aolle/pillar3/scripts/export.py`

Produced section-based artifacts:
- `pillar3-home.{docx,pdf}`
- `pillar3-foundation.{docx,pdf}`
- `pillar3-data-model.{docx,pdf}`

PDF pages:
- Home: 3
- Foundation: 26
- Data Model: 88
- Total: 117

## Findings

1. Mermaid compatibility improved significantly with pre-render mode.
- No Mermaid syntax tokens found in extracted DOCX/PDF text for generated plugin artifacts.
- Diagrams are embedded as images and preserved in both formats.

2. Table conversion works and is extensive in both fixtures.
- DOCX table elements are present at large volume in both outputs.
- Additional visual tuning still depends on CSS/template configuration.

3. Runtime is currently high for Mermaid-heavy projects.
- WP-SDMX-DPM full export took about 419 seconds.
- Rendering many Mermaid blocks via `mmdc` dominates runtime.

4. Reliability improved with timeout/fallback logic.
- Mermaid rendering can hang on individual diagrams in this environment.
- `mermaid_timeout_seconds` + `mermaid_fail_on_error: false` avoids full-run failure.

## Tuning backlog from fixtures

1. Add export mode: one output per top-level nav section (to mirror pillar3 baseline behavior).
2. Add Mermaid cache strategy across runs (content hash is present; add reusable cache location option).
3. Add explicit PDF page format option (`A4`, `Letter`) independent of CSS.
4. Add default print CSS for projects without custom stylesheet.
5. Add option to include only nav pages (exclude files outside nav).
