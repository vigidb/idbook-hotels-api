"""HTML → PDF for invoices, service agreements, and receipts.

1. **wkhtmltopdf** (via pdfkit) when the binary is on ``PATH`` or ``WKHTMLTOPDF_CMD``.
2. **Google Chrome, Microsoft Edge, or Chromium** (headless ``--print-to-pdf``) when
   wkhtmltopdf is unavailable (Homebrew no longer ships ``wkhtmltopdf``).

Optional env: ``WKHTMLTOPDF_CMD``, ``CHROME_CMD`` (any Chromium-based browser binary;
see ``IDBOOKAPI.settings``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def resolve_wkhtmltopdf_path() -> str | None:
    from django.conf import settings

    explicit = getattr(settings, "WKHTMLTOPDF_CMD", None)
    if isinstance(explicit, str):
        explicit = explicit.strip() or None
    if explicit and os.path.isfile(explicit):
        if os.name == "nt" or os.access(explicit, os.X_OK):
            return explicit

    found = shutil.which("wkhtmltopdf")
    if found and (os.name == "nt" or os.access(found, os.X_OK)):
        return found

    for candidate in (
        "/opt/homebrew/bin/wkhtmltopdf",
        "/usr/local/bin/wkhtmltopdf",
        "/usr/bin/wkhtmltopdf",
    ):
        if os.path.isfile(candidate) and (
            os.name == "nt" or os.access(candidate, os.X_OK)
        ):
            return candidate
    return None


def resolve_chrome_executable() -> str | None:
    """Chromium-based browser for headless PDF; respects ``settings.CHROME_CMD``."""
    from django.conf import settings

    explicit = getattr(settings, "CHROME_CMD", None)
    if isinstance(explicit, str):
        explicit = explicit.strip() or None
    if explicit and os.path.isfile(explicit):
        if os.name == "nt" or os.access(explicit, os.X_OK):
            return explicit

    if os.name == "nt":
        for base in (
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        ):
            for rel in (
                ("Google", "Chrome", "Application", "chrome.exe"),
                ("Microsoft", "Edge", "Application", "msedge.exe"),
            ):
                candidate = os.path.join(base, *rel)
                if os.path.isfile(candidate):
                    return candidate
    else:
        # Standard install locations (isfile only — X_OK is unreliable on some macOS setups)
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ):
            if os.path.isfile(candidate):
                return candidate

    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "msedge",
    ):
        found = shutil.which(name)
        if found and (os.name == "nt" or os.access(found, os.X_OK)):
            return found
    return None


def _chrome_html_to_pdf_bytes(html: str, chrome_exe: str) -> bytes:
    """Render HTML to PDF using a headless Chromium-based browser (Chrome, Edge, …)."""
    html_path = None
    pdf_path = None
    try:
        fd, html_path = tempfile.mkstemp(suffix=".html", prefix="idbook_pdf_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(html)
        except Exception:
            os.close(fd)
            raise

        pdf_path = html_path + ".pdf"
        abs_html = Path(html_path).resolve()
        file_url = abs_html.as_uri()
        pdf_abs = str(Path(pdf_path).resolve())

        result = subprocess.run(
            [
                chrome_exe,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--print-to-pdf={pdf_abs}",
                file_url,
            ],
            capture_output=True,
            timeout=180,
        )
        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Chrome headless PDF failed (exit {result.returncode}): {err or 'no stderr'}"
            )
        if not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) == 0:
            raise RuntimeError(
                "Chrome did not produce a PDF file (empty or missing output)."
            )
        with open(pdf_path, "rb") as pdf_fh:
            return pdf_fh.read()
    finally:
        for path in (pdf_path, html_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def html_to_pdf_bytes(html: str, options: dict | None = None) -> bytes:
    """
    Render HTML string to PDF bytes.

    Uses wkhtmltopdf + pdfkit when available; otherwise headless Chrome/Chromium.
    ``options`` is only applied for the wkhtmltopdf path (pdfkit API).
    """
    options = options or {}
    wk = resolve_wkhtmltopdf_path()
    if wk:
        import pdfkit

        config = pdfkit.configuration(wkhtmltopdf=wk)
        return pdfkit.from_string(
            html, False, options=options, configuration=config
        )

    chrome = resolve_chrome_executable()
    if chrome:
        return _chrome_html_to_pdf_bytes(html, chrome)

    raise RuntimeError(
        "No HTML→PDF engine found. Either:\n"
        "  • Install Google Chrome, Microsoft Edge, or Chromium, or set CHROME_CMD to "
        "the browser binary; or\n"
        "  • Install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html and set "
        "WKHTMLTOPDF_CMD to the full path of the binary."
    )

