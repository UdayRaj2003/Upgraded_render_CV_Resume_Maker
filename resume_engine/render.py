"""Render a RenderCV YAML file to PDF and a classic-theme DOCX."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from resume_engine.docx_classic import render_yaml_to_docx, render_yaml_to_pdf_ats


class RenderError(Exception):
    pass


@dataclass(frozen=True)
class RenderArtifacts:
    pdf_path: Path
    docx_path: Path | None = None


def _convert_markdown_to_docx(md_path: Path, docx_path: Path) -> Path | None:
    """Convert RenderCV Markdown to DOCX. Returns None if Pandoc is missing or fails."""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        print(
            "Pandoc not on PATH; skipping DOCX. Install: winget install JohnMacFarlane.Pandoc",
            file=sys.stderr,
            flush=True,
        )
        return None
    try:
        completed = subprocess.run(
            [pandoc, str(md_path), "-o", str(docx_path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        print(f"Pandoc launch failed: {exc}", file=sys.stderr, flush=True)
        return None
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        print(f"Pandoc failed ({completed.returncode}): {detail[:400]}", file=sys.stderr, flush=True)
        return None
    if not docx_path.is_file() or docx_path.stat().st_size <= 0:
        print(f"Pandoc produced no DOCX at {docx_path}", file=sys.stderr, flush=True)
        return None
    return docx_path


def render_yaml_to_pdf(
    yaml_path: Path,
    output_folder: Path,
    *,
    output_filename: str | None = None,
) -> RenderArtifacts:
    """Render YAML to PDF (and Markdown). Optionally convert Markdown to DOCX via Pandoc."""
    output_folder.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [
        sys.executable,
        "-m",
        "rendercv",
        "render",
        str(yaml_path),
        "--output-folder",
        str(output_folder),
        "--dont-generate-html",
        "--dont-generate-png",
        "--quiet",
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(yaml_path.parent),
        )
    except OSError as exc:
        raise RenderError(f"Failed to launch RenderCV: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RenderError(f"RenderCV failed ({completed.returncode}): {detail[:500]}")

    pdfs = sorted(
        output_folder.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not pdfs:
        raise RenderError(f"No PDF produced in {output_folder}")

    produced = pdfs[0]
    if not output_filename:
        pdf_path = produced
    else:
        name = Path(output_filename).name
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        pdf_path = output_folder / name
        if produced.resolve() != pdf_path.resolve():
            if pdf_path.exists():
                pdf_path.unlink()
            shutil.move(str(produced), str(pdf_path))

    docx_path: Path | None = None
    target_docx = output_folder / f"{pdf_path.stem}.docx"
    converted = render_yaml_to_docx(yaml_path, target_docx)
    if converted is None:
        mds = sorted(
            output_folder.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if mds:
            converted = _convert_markdown_to_docx(mds[0], target_docx)
    if converted is not None:
        docx_path = converted
        target_ats_pdf = output_folder / f"{pdf_path.stem}_ats.pdf"
        render_yaml_to_pdf_ats(yaml_path, target_ats_pdf)

    return RenderArtifacts(pdf_path=pdf_path, docx_path=docx_path)
