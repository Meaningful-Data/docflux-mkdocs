# Architecture (Draft)

## Pipeline
1. Collect page markdown during `on_page_markdown`.
2. Combine markdown into a single intermediate document.
3. Convert intermediate document for each requested target format.
4. Emit artifacts under `site_dir/<output_dir>/` by default.

## Components
- `ExportPlugin`: MkDocs lifecycle integration and orchestration.
- `CollectedPage`: lightweight page DTO for deterministic merge order.
- Pandoc runner (`_run_pandoc`): command construction and process execution.

## Current converter strategy
- Use Pandoc for DOCX.
- Use Pandoc->HTML + headless Chrome for PDF by default.
- Keep direct Pandoc PDF strategy as fallback when LaTeX engines are available.
- Optional Mermaid pre-render: Mermaid fences -> PNG assets via `mmdc`.

## Extension points
- Introduce converter interface (`Pandoc`, `Playwright`, future engines).
- Add format-specific pre-processing passes.
- Add multi-file export mode.

## Error handling
- Converter executable missing => raise `PluginError`.
- Converter exits non-zero => raise `PluginError` with exit code.
- Mermaid rendering can be configured to warn and continue (default) or fail-fast.
- Converter timeouts are enforced to avoid stuck export runs.
