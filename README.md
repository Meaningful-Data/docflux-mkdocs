# DocFlux MkDocs

DocFlux MkDocs is a MkDocs plugin that exports documentation to **DOCX** and **PDF** with one configuration surface.

Status: early MVP scaffold. The current implementation focuses on a reliable single-file export path with:

- Pandoc DOCX export.
- Pandoc HTML + headless Chrome PDF export.
- Optional Mermaid pre-render (`mmdc`) into PNG for DOCX/PDF compatibility.

## Goals

- Provide first-class DOCX export for MkDocs projects.
- Provide a pragmatic PDF export path in the same plugin.
- Keep configuration simple and reproducible in CI.

## License

This project is licensed under Apache-2.0. See `LICENSE`.

## Installation (development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Pandoc is required at runtime for the MVP exporter.

## MkDocs configuration

```yaml
plugins:
  - search
  - docflux-mkdocs:
      formats: [docx, pdf]
      output_dir: exports
      filename: project-docs
      single_file: true
      command_timeout_seconds: 300
      pandoc_path: pandoc
      toc: true
      toc_depth: 3
      docx_reference_doc: templates/reference.docx
      docx_extra_args: []
      pdf_strategy: chrome
      pdf_engine: xelatex
      pdf_css: scripts/pdf-style.css
      chrome_path: google-chrome
      chrome_extra_args: []
      mermaid_mode: pre_render
      mmdc_path: mmdc
      mermaid_background: white
      mermaid_width: 1600
      mermaid_timeout_seconds: 45
      mermaid_fail_on_error: false
      mermaid_chrome_path: /usr/bin/google-chrome
      mermaid_extra_args: []
      pandoc_extra_args: []
      pdf_extra_args: []
```

Legacy alias: `mkdocs-export` is still available for backward compatibility.

## Notes on PDF strategies

- `pdf_strategy: chrome` is recommended when no LaTeX engine is installed.
- `pdf_strategy: pandoc` uses Pandoc PDF conversion directly and usually requires a LaTeX engine (`xelatex`, `pdflatex`, etc.).

## Notes on Mermaid

- `mermaid_mode: pre_render` replaces fenced Mermaid blocks with PNG images before export.
- If Mermaid rendering fails and `mermaid_fail_on_error: false`, the plugin keeps the original Mermaid code block and continues.

## Development

```bash
pytest
```

## Planning docs

- Product spec: `docs/spec/product-spec.md`
- Architecture: `docs/spec/architecture.md`
- Roadmap: `docs/spec/roadmap.md`
- Open questions: `docs/spec/open-questions.md`
- Fixture report: `docs/spec/fixture-report-2026-02-16.md`
