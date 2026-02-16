import urllib.error
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
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
        "docx_update_fields_on_open": True,
        "pandoc_extra_args": [],
        "pdf_strategy": "chrome",
        "pdf_engine": None,
        "pdf_css": None,
        "pdf_extra_args": [],
        "chrome_path": "google-chrome",
        "chrome_extra_args": [],
        "mermaid_mode": "preserve",
        "mermaid_renderer": "mmdc",
        "mmdc_path": "mmdc",
        "mermaid_kroki_url": "https://kroki.io",
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

    command = plugin._build_chrome_pdf_command(Path("/tmp/in.html"), Path("/tmp/out.pdf"))

    assert command[0] == "google-chrome-stable"
    assert "--headless" in command
    assert "--print-to-pdf=/tmp/out.pdf" in command
    assert command[-1] == "--virtual-time-budget=1000"


def test_enable_docx_update_fields_sets_update_flag(tmp_path: Path) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin)

    docx_path = tmp_path / "out.docx"
    settings_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<w:settings xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:zoom w:percent=\"100\"/>"
        "</w:settings>"
    )
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/settings.xml", settings_xml)
        archive.writestr("docProps/core.xml", "<core/>")

    plugin._enable_docx_update_fields(docx_path)

    with zipfile.ZipFile(docx_path, "r") as archive:
        updated_settings = archive.read("word/settings.xml")

    root = ET.fromstring(updated_settings)
    update_fields = root.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}updateFields")
    assert update_fields is not None
    assert update_fields.attrib["{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"] == "true"


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


def test_on_post_build_split_by_top_level_nav_group(tmp_path: Path, monkeypatch) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, single_file=False, formats=["docx"], filename="guide")
    plugin._pages = [
        CollectedPage("index.md", "Home", "Welcome"),
        CollectedPage("foundation/intro.md", "Intro", "Foundation intro"),
        CollectedPage("foundation/model.md", "Model", "Foundation model"),
        CollectedPage("notes.md", "Notes", "Hidden page"),
    ]

    home_page = SimpleNamespace(
        is_page=True, title="Home", file=SimpleNamespace(src_path="index.md")
    )
    intro_page = SimpleNamespace(
        is_page=True,
        title="Intro",
        file=SimpleNamespace(src_path="foundation/intro.md"),
    )
    model_page = SimpleNamespace(
        is_page=True,
        title="Model",
        file=SimpleNamespace(src_path="foundation/model.md"),
    )
    foundation_section = SimpleNamespace(
        is_page=False,
        title="Foundation",
        children=[intro_page, model_page],
    )
    fake_nav = SimpleNamespace(items=[home_page, foundation_section])
    plugin.on_nav(fake_nav)

    calls: list[tuple[str, str, str]] = []

    def fake_docx(markdown: str, output_path: Path) -> None:
        calls.append(("docx", output_path.name, markdown))

    monkeypatch.setattr(plugin, "_export_docx", fake_docx)

    plugin.on_post_build(config={"site_dir": str(tmp_path / "site")})

    assert [item[1] for item in calls] == ["guide-home.docx", "guide-foundation.docx"]
    assert "Welcome" in calls[0][2]
    assert "Foundation intro" in calls[1][2]
    assert "Foundation model" in calls[1][2]
    assert "Hidden page" not in calls[1][2]


def test_on_post_build_split_mode_requires_nav_groups(tmp_path: Path) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, single_file=False, formats=["docx"], filename="guide")
    plugin._pages = [CollectedPage("a.md", "A", "A body")]

    with pytest.raises(PluginError, match="single_file=false requires navigation data"):
        plugin.on_post_build(config={"site_dir": str(tmp_path / "site")})


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


def test_replace_mermaid_blocks_falls_back_when_render_fails(tmp_path: Path, monkeypatch) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, mermaid_mode="pre_render", mermaid_fail_on_error=False)
    output_dir = tmp_path / "exports"

    def fake_render(_mmd_path: Path, _png_path: Path) -> None:
        raise PluginError("boom")

    monkeypatch.setattr(plugin, "_render_mermaid", fake_render)
    markdown = "```mermaid\ngraph TD\nA-->B\n```\n"

    transformed = plugin._replace_mermaid_blocks(markdown, output_dir)

    assert transformed == markdown


def test_render_mermaid_via_kroki_writes_png(tmp_path: Path, monkeypatch) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(
        plugin,
        mermaid_mode="pre_render",
        mermaid_renderer="kroki",
        mermaid_kroki_url="https://kroki.example",
    )

    mmd_path = tmp_path / "diagram.mmd"
    png_path = tmp_path / "diagram.png"
    mmd_path.write_text("graph TD\nA-->B\n", encoding="utf-8")

    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return b"fake-png-bytes"

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    plugin._render_mermaid(mmd_path, png_path)

    assert png_path.read_bytes() == b"fake-png-bytes"
    request = captured["request"]
    assert request.full_url == "https://kroki.example/mermaid/png"
    assert request.data == b"graph TD\nA-->B\n"
    assert captured["timeout"] == 45


def test_render_mermaid_via_kroki_raises_plugin_error_on_http_failure(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = ExportPlugin()
    _load_plugin_config(plugin, mermaid_mode="pre_render", mermaid_renderer="kroki")

    mmd_path = tmp_path / "diagram.mmd"
    png_path = tmp_path / "diagram.png"
    mmd_path.write_text("graph TD\nA-->B\n", encoding="utf-8")

    def fake_urlopen(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://kroki.io/mermaid/png",
            500,
            "Internal Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(PluginError, match="Kroki request failed with HTTP 500"):
        plugin._render_mermaid(mmd_path, png_path)
