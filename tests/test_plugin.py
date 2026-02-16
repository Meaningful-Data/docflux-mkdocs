from pathlib import Path

from mkdocs.exceptions import PluginError

from docflux_mkdocs.plugin import CollectedPage, ExportPlugin


def _load_plugin_config(plugin: ExportPlugin, **overrides: object) -> None:
    base = {
        "enabled": True,
        "formats": ["docx"],
        "output_dir": "exports",
        "filename": "documentation",
        "single_file": True,
        "command_timeout_seconds": 300,
        "pandoc_path": "pandoc",
        "toc": True,
        "toc_depth": 3,
        "docx_reference_doc": None,
        "docx_extra_args": [],
        "pandoc_extra_args": [],
        "pdf_strategy": "chrome",
        "pdf_engine": None,
        "pdf_css": None,
        "pdf_extra_args": [],
        "chrome_path": "google-chrome",
        "chrome_extra_args": [],
        "mermaid_mode": "preserve",
        "mmdc_path": "mmdc",
        "mermaid_background": "white",
        "mermaid_width": 1600,
        "mermaid_timeout_seconds": 45,
        "mermaid_fail_on_error": False,
        "mermaid_chrome_path": None,
        "mermaid_extra_args": [],
    }
    base.update(overrides)
    errors, warnings = plugin.load_config(base)
    assert errors == [], errors
    assert warnings == [], warnings


def test_build_docx_command_with_reference_doc() -> None:
    plugin = ExportPlugin()
    _load_plugin_config(
        plugin,
        docx_reference_doc="templates/ref.docx",
        pandoc_extra_args=["--toc"],
    )
    plugin._project_root = Path("/workspace")

    command = plugin._build_docx_command(Path("/tmp/in.md"), Path("/tmp/out.docx"))

    assert command[0] == "pandoc"
    assert "--to" in command
    assert "docx" in command
    assert "--reference-doc" in command
    assert str(Path("/workspace/templates/ref.docx")) in command
    assert command[-1] == "--toc"


def test_build_chrome_pdf_command() -> None:
    plugin = ExportPlugin()
    _load_plugin_config(
        plugin,
        formats=["pdf"],
        chrome_path="google-chrome-stable",
        chrome_extra_args=["--virtual-time-budget=1000"],
    )

    command = plugin._build_chrome_pdf_command(
        Path("/tmp/in.html"), Path("/tmp/out.pdf")
    )

    assert command[0] == "google-chrome-stable"
    assert "--headless" in command
    assert "--print-to-pdf=/tmp/out.pdf" in command
    assert command[-1] == "--virtual-time-budget=1000"


def test_build_combined_markdown_preserves_existing_top_heading() -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin)

    combined = plugin._build_combined_markdown(
        [
            CollectedPage("a.md", "A", "# Existing\n\nBody"),
            CollectedPage("b.md", "B", "Body without heading"),
        ],
        Path("/tmp/out"),
    )

    assert combined.startswith("# Existing")
    assert "# B\n\nBody without heading" in combined
    assert "\\newpage" in combined


def test_on_post_build_runs_for_each_requested_format(tmp_path: Path, monkeypatch) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, formats=["docx", "pdf"], filename="guide")
    plugin._pages = [CollectedPage("a.md", "A", "A body")]

    calls: list[tuple[str, str]] = []

    def fake_docx(markdown: str, output_path: Path) -> None:
        assert markdown
        calls.append(("docx", output_path.name))

    def fake_pdf(markdown: str, output_path: Path) -> None:
        assert markdown
        calls.append(("pdf", output_path.name))

    monkeypatch.setattr(plugin, "_export_docx", fake_docx)
    monkeypatch.setattr(plugin, "_export_pdf", fake_pdf)

    plugin.on_post_build(config={"site_dir": str(tmp_path / "site")})

    assert calls == [("docx", "guide.docx"), ("pdf", "guide.pdf")]


def test_replace_mermaid_blocks_creates_image_links(tmp_path: Path, monkeypatch) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, mermaid_mode="pre_render")
    output_dir = tmp_path / "exports"

    rendered: list[Path] = []

    def fake_render(mmd_path: Path, png_path: Path) -> None:
        rendered.append(mmd_path)
        png_path.write_bytes(b"fake")

    monkeypatch.setattr(plugin, "_render_mermaid", fake_render)
    markdown = "```mermaid\ngraph TD\nA-->B\n```\n"

    transformed = plugin._replace_mermaid_blocks(markdown, output_dir)

    assert "![Mermaid diagram]" in transformed
    assert len(rendered) == 1


def test_replace_mermaid_blocks_falls_back_when_render_fails(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, mermaid_mode="pre_render", mermaid_fail_on_error=False)
    output_dir = tmp_path / "exports"

    def fake_render(_mmd_path: Path, _png_path: Path) -> None:
        raise PluginError("boom")

    monkeypatch.setattr(plugin, "_render_mermaid", fake_render)
    markdown = "```mermaid\ngraph TD\nA-->B\n```\n"

    transformed = plugin._replace_mermaid_blocks(markdown, output_dir)

    assert transformed == markdown
