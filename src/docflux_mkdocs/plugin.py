from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin
from mkdocs.structure.pages import Page

LOG = logging.getLogger("mkdocs.plugins.mkdocs_export")
MERMAID_BLOCK_RE: Final[re.Pattern[str]] = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
PANDOC_FROM_FORMAT: Final[str] = "markdown+pipe_tables+grid_tables+table_captions+fenced_divs"


@dataclass
class CollectedPage:
    src_path: str
    title: str
    markdown: str


class ExportPlugin(BasePlugin):
    """Export MkDocs content to DOCX/PDF after build."""

    config_scheme = (
        ("enabled", config_options.Type(bool, default=True)),
        (
            "formats",
            config_options.ListOfItems(
                config_options.Choice(("docx", "pdf")),
                default=["docx"],
            ),
        ),
        ("output_dir", config_options.Type(str, default="exports")),
        ("filename", config_options.Type(str, default="documentation")),
        ("single_file", config_options.Type(bool, default=True)),
        ("command_timeout_seconds", config_options.Type(int, default=300)),
        ("pandoc_path", config_options.Type(str, default="pandoc")),
        ("toc", config_options.Type(bool, default=True)),
        ("toc_depth", config_options.Type(int, default=3)),
        (
            "docx_reference_doc",
            config_options.Optional(config_options.Type(str)),
        ),
        (
            "docx_extra_args",
            config_options.ListOfItems(config_options.Type(str), default=[]),
        ),
        (
            "pandoc_extra_args",
            config_options.ListOfItems(config_options.Type(str), default=[]),
        ),
        (
            "pdf_strategy",
            config_options.Choice(("pandoc", "chrome"), default="chrome"),
        ),
        (
            "pdf_engine",
            config_options.Optional(config_options.Type(str)),
        ),
        (
            "pdf_css",
            config_options.Optional(config_options.Type(str)),
        ),
        (
            "pdf_extra_args",
            config_options.ListOfItems(config_options.Type(str), default=[]),
        ),
        ("chrome_path", config_options.Type(str, default="google-chrome")),
        (
            "chrome_extra_args",
            config_options.ListOfItems(config_options.Type(str), default=[]),
        ),
        (
            "mermaid_mode",
            config_options.Choice(("preserve", "pre_render"), default="preserve"),
        ),
        (
            "mermaid_renderer",
            config_options.Choice(("mmdc", "kroki"), default="mmdc"),
        ),
        ("mmdc_path", config_options.Type(str, default="mmdc")),
        ("mermaid_kroki_url", config_options.Type(str, default="https://kroki.io")),
        ("mermaid_background", config_options.Type(str, default="white")),
        ("mermaid_width", config_options.Type(int, default=1600)),
        ("mermaid_timeout_seconds", config_options.Type(int, default=45)),
        ("mermaid_fail_on_error", config_options.Type(bool, default=False)),
        (
            "mermaid_chrome_path",
            config_options.Optional(config_options.Type(str)),
        ),
        (
            "mermaid_extra_args",
            config_options.ListOfItems(config_options.Type(str), default=[]),
        ),
    )

    def __init__(self) -> None:
        super().__init__()
        self._pages: list[CollectedPage] = []
        self._project_root = Path.cwd()

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        if not self.config["enabled"]:
            return config

        self._pages = []
        docs_dir = Path(config["docs_dir"])
        if docs_dir.is_absolute():
            self._project_root = docs_dir.resolve().parent
        elif config.config_file_path:
            self._project_root = Path(config.config_file_path).resolve().parent

        if not self.config["single_file"]:
            raise PluginError("single_file=false is not implemented yet")

        return config

    def on_page_markdown(self, markdown: str, page: Page, **kwargs: object) -> str:
        if not self.config["enabled"]:
            return markdown

        title = page.title or self._title_from_src_path(page.file.src_path)
        self._pages.append(
            CollectedPage(
                src_path=page.file.src_path,
                title=title,
                markdown=markdown,
            )
        )
        return markdown

    def on_post_build(self, *, config: MkDocsConfig) -> None:
        if not self.config["enabled"]:
            return

        if not self._pages:
            LOG.warning("No pages were collected for export")
            return

        output_dir = self._resolve_output_dir(Path(config["site_dir"]))
        output_dir.mkdir(parents=True, exist_ok=True)

        combined_markdown = self._build_combined_markdown(self._pages, output_dir)
        for fmt in self.config["formats"]:
            target = output_dir / f"{self.config['filename']}.{fmt}"
            if fmt == "docx":
                self._export_docx(combined_markdown, target)
                continue
            self._export_pdf(combined_markdown, target)

    def _export_docx(self, markdown: str, output_path: Path) -> None:
        with TemporaryDirectory(prefix="mkdocs-export-") as temp_dir:
            input_path = Path(temp_dir) / "combined.md"
            input_path.write_text(markdown, encoding="utf-8")
            command = self._build_docx_command(input_path, output_path)
            self._run_command(command, "DOCX export")

    def _export_pdf(self, markdown: str, output_path: Path) -> None:
        strategy = self.config["pdf_strategy"]
        with TemporaryDirectory(prefix="mkdocs-export-") as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "combined.md"
            input_path.write_text(markdown, encoding="utf-8")

            if strategy == "pandoc":
                command = self._build_pandoc_pdf_command(input_path, output_path)
                self._run_command(command, "PDF export (pandoc)")
                return

            html_path = temp_root / "combined.html"
            html_command = self._build_html_command(input_path, html_path)
            self._run_command(html_command, "PDF export HTML generation")

            chrome_command = self._build_chrome_pdf_command(html_path, output_path)
            self._run_command(chrome_command, "PDF export (chrome)")

    def _build_docx_command(self, input_path: Path, output_path: Path) -> list[str]:
        command = [
            self.config["pandoc_path"],
            str(input_path),
            "--from",
            PANDOC_FROM_FORMAT,
            "--to",
            "docx",
            "--standalone",
            "-o",
            str(output_path),
        ]
        command.extend(self._build_toc_args())

        reference_doc = self.config["docx_reference_doc"]
        if reference_doc:
            command.extend(["--reference-doc", str(self._resolve_project_path(reference_doc))])

        command.extend(self.config["docx_extra_args"])
        command.extend(self.config["pandoc_extra_args"])
        return command

    def _build_pandoc_pdf_command(self, input_path: Path, output_path: Path) -> list[str]:
        command = [
            self.config["pandoc_path"],
            str(input_path),
            "--from",
            PANDOC_FROM_FORMAT,
            "--to",
            "pdf",
            "--standalone",
            "-o",
            str(output_path),
        ]
        command.extend(self._build_toc_args())
        pdf_engine = self.config["pdf_engine"]
        if pdf_engine:
            command.extend(["--pdf-engine", pdf_engine])
        command.extend(self.config["pdf_extra_args"])
        command.extend(self.config["pandoc_extra_args"])
        return command

    def _build_html_command(self, input_path: Path, html_path: Path) -> list[str]:
        command = [
            self.config["pandoc_path"],
            str(input_path),
            "--from",
            PANDOC_FROM_FORMAT,
            "--to",
            "html5",
            "--standalone",
            "--embed-resources",
            "-o",
            str(html_path),
        ]
        command.extend(self._build_toc_args())

        pdf_css = self.config["pdf_css"]
        if pdf_css:
            command.extend(["--css", str(self._resolve_project_path(pdf_css))])

        command.extend(self.config["pdf_extra_args"])
        command.extend(self.config["pandoc_extra_args"])
        return command

    def _build_chrome_pdf_command(self, html_path: Path, output_path: Path) -> list[str]:
        command = [
            self.config["chrome_path"],
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_path}",
            str(html_path),
        ]
        command.extend(self.config["chrome_extra_args"])
        return command

    def _build_toc_args(self) -> list[str]:
        if not self.config["toc"]:
            return []
        return ["--toc", "--toc-depth", str(self.config["toc_depth"])]

    def _run_command(self, command: list[str], context: str, timeout: int | None = None) -> None:
        try:
            subprocess.run(
                command,
                cwd=self._project_root,
                check=True,
                text=True,
                capture_output=True,
                timeout=timeout or self.config["command_timeout_seconds"],
            )
        except FileNotFoundError as exc:
            raise PluginError(f"Executable not found: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise PluginError(f"{context} timed out after {exc.timeout} seconds.") from exc
        except subprocess.CalledProcessError as exc:
            diagnostics = self._extract_diagnostics(exc)
            raise PluginError(
                f"{context} failed with exit code {exc.returncode}. {diagnostics}"
            ) from exc

    @staticmethod
    def _extract_diagnostics(exc: subprocess.CalledProcessError) -> str:
        output = (exc.stderr or exc.stdout or "").strip()
        if not output:
            return "No additional diagnostics from process."
        last_line = output.splitlines()[-1].strip()
        return f"Last log line: {last_line}"

    def _resolve_output_dir(self, site_dir: Path) -> Path:
        configured = Path(self.config["output_dir"])
        return configured if configured.is_absolute() else site_dir / configured

    def _resolve_project_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (self._project_root / path).resolve()

    @staticmethod
    def _title_from_src_path(src_path: str) -> str:
        stem = Path(src_path).stem
        return stem.replace("-", " ").replace("_", " ").title()

    def _build_combined_markdown(self, pages: list[CollectedPage], output_dir: Path) -> str:
        chunks: list[str] = []
        for page in pages:
            content = page.markdown.strip()
            if self.config["mermaid_mode"] == "pre_render":
                content = self._replace_mermaid_blocks(content, output_dir)
            if not content.lstrip().startswith("#"):
                content = f"# {page.title}\n\n{content}" if content else f"# {page.title}"
            chunks.append(content)
        separator = '\n\n\\newpage\n<div style="page-break-before: always;"></div>\n\n'
        return separator.join(chunks) + "\n"

    def _replace_mermaid_blocks(self, markdown: str, output_dir: Path) -> str:
        if "```mermaid" not in markdown:
            return markdown

        asset_dir = output_dir / "_mermaid"
        asset_dir.mkdir(parents=True, exist_ok=True)

        def _replace(match: re.Match[str]) -> str:
            mermaid_content = match.group(1).strip()
            if not mermaid_content:
                return match.group(0)
            digest = hashlib.sha256(mermaid_content.encode("utf-8")).hexdigest()[:16]
            mmd_path = asset_dir / f"{digest}.mmd"
            png_path = asset_dir / f"{digest}.png"
            if not png_path.exists():
                mmd_path.write_text(mermaid_content + "\n", encoding="utf-8")
                try:
                    self._render_mermaid(mmd_path, png_path)
                except PluginError as exc:
                    if self.config["mermaid_fail_on_error"]:
                        raise
                    LOG.warning("Mermaid render failed for %s: %s", mmd_path.name, exc)
                    return match.group(0)
            return f"![Mermaid diagram]({png_path})"

        return MERMAID_BLOCK_RE.sub(_replace, markdown)

    def _render_mermaid(self, mmd_path: Path, png_path: Path) -> None:
        if self.config["mermaid_renderer"] == "kroki":
            self._render_mermaid_via_kroki(mmd_path, png_path)
            return

        command = [
            self.config["mmdc_path"],
            "-i",
            str(mmd_path),
            "-o",
            str(png_path),
            "-b",
            self.config["mermaid_background"],
            "-w",
            str(self.config["mermaid_width"]),
        ]
        command.extend(self.config["mermaid_extra_args"])

        mermaid_chrome_path = self.config["mermaid_chrome_path"]
        if mermaid_chrome_path:
            with TemporaryDirectory(prefix="mkdocs-export-mermaid-") as temp_dir:
                pptr_cfg = Path(temp_dir) / "puppeteer-config.json"
                pptr_cfg.write_text(
                    (
                        "{"
                        f'"executablePath":"{mermaid_chrome_path}",'
                        '"args":["--no-sandbox","--disable-setuid-sandbox"]'
                        "}"
                    ),
                    encoding="utf-8",
                )
                command_with_cfg = [*command, "-p", str(pptr_cfg)]
                self._run_command(
                    command_with_cfg,
                    "Mermaid pre-render",
                    timeout=self.config["mermaid_timeout_seconds"],
                )
                return

        self._run_command(
            command,
            "Mermaid pre-render",
            timeout=self.config["mermaid_timeout_seconds"],
        )

    def _render_mermaid_via_kroki(self, mmd_path: Path, png_path: Path) -> None:
        mermaid_source = mmd_path.read_text(encoding="utf-8")
        endpoint = f"{self.config['mermaid_kroki_url'].rstrip('/')}/mermaid/png"
        request = urllib.request.Request(
            endpoint,
            data=mermaid_source.encode("utf-8"),
            method="POST",
            headers={
                "Accept": "image/png",
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "docflux-mkdocs",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config["mermaid_timeout_seconds"],
            ) as response:
                status_code = response.getcode()
                if status_code != 200:
                    raise PluginError(f"Kroki returned unexpected status code {status_code}.")
                png_path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            raise PluginError(f"Kroki request failed with HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise PluginError(f"Kroki request failed: {exc.reason}") from exc
