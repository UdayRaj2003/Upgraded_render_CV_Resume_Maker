"""Template strategies and selection registry for resume_engine.

Provides a clean Strategy pattern separating common JD personalization logic
from template-specific layout, URL formatting, and page-budget enforcement.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from resume_engine.render import render_yaml_to_pdf

# Root directory of RenderCV project
ROOT = Path(__file__).resolve().parent.parent


def _wrap_urls_in_markdown(text: str) -> str:
    """Ensure raw URLs in bullet text are formatted as [URL](URL) markdown links.

    This ensures RenderCV's Typst parser renders visible URL text in blue (#0563C1).
    Does not modify URLs already wrapped in markdown links.
    """
    if not text or not isinstance(text, str):
        return text

    pattern = r"(\[[^\]]+\]\([^)]+\))|(https?://[^\s\)]+)"

    def replace_url(match: re.Match[str]) -> str:
        md_link, raw_url = match.groups()
        if md_link:
            return md_link
        return f"[{raw_url}]({raw_url})"

    return re.sub(pattern, replace_url, text)


class BaseTemplateStrategy:
    """Base class / default strategy for resume templates."""

    name: str = "default"
    default_master_filename: str = "Uday_Resume.yaml"

    def get_master_yaml_path(self, override_path: Path | None = None) -> Path:
        """Resolve the master YAML file path for this template."""
        if override_path is not None:
            return Path(override_path)
        return ROOT / self.default_master_filename

    def post_process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply template-specific post-processing to personalized YAML data."""
        return data

    def post_render_check(
        self,
        pdf_path: Path,
        temp_yaml: Path,
        output_folder: Path,
        output_filename: str | None = None,
    ) -> Path:
        """Hook to validate or adjust rendered PDF layout (e.g. 1-page overflow check)."""
        return pdf_path


class DefaultTemplateStrategy(BaseTemplateStrategy):
    """Default template strategy (Uday_Resume.yaml / Classic)."""

    name: str = "default"
    default_master_filename: str = "Uday_Resume.yaml"


class Template2Strategy(BaseTemplateStrategy):
    """Template 2 strategy (Template2_Resume.yaml).

    Handles Template 2 specific URL blue link formatting and single-page A4
    layout safety checks.
    """

    name: str = "template2"
    default_master_filename: str = "Template2_Resume.yaml"

    def post_process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Wrap all URLs in experience/project highlights with explicit markdown links.

        Ensures RenderCV renders visible link text in blue (#0563C1).
        """
        doc = copy.deepcopy(data)
        cv = doc.get("cv", {})
        sections = cv.get("sections", {})

        for section_name, entries in sections.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    highlights = entry.get("highlights")
                    if isinstance(highlights, list):
                        entry["highlights"] = [
                            _wrap_urls_in_markdown(str(h)) for h in highlights
                        ]
                elif isinstance(entry, str):
                    # Text-based section entries (e.g. Certifications)
                    idx = entries.index(entry)
                    entries[idx] = _wrap_urls_in_markdown(entry)

        return doc

    def post_render_check(
        self,
        pdf_path: Path,
        temp_yaml: Path,
        output_folder: Path,
        output_filename: str | None = None,
    ) -> Path:
        """Check if output spilled onto page 2 and auto-adjust line spacing if needed."""
        pngs = list(output_folder.glob("*.png"))
        has_page2 = any(p.name.endswith("_2.png") for p in pngs)

        if has_page2:
            # Re-render once with slightly tighter line_spacing to guarantee 1 page
            import ruamel.yaml

            yaml = ruamel.yaml.YAML(typ="rt")
            yaml.preserve_quotes = True
            with temp_yaml.open("r", encoding="utf-8") as fh:
                temp_data = yaml.load(fh)

            design = temp_data.get("design", {})
            typography = design.get("typography", {})
            typography["line_spacing"] = "0.20em"

            with temp_yaml.open("w", encoding="utf-8") as fh:
                yaml.dump(temp_data, fh)

            artifacts = render_yaml_to_pdf(
                temp_yaml, output_folder, output_filename=output_filename
            )
            return artifacts.pdf_path

        return pdf_path


# Template Registry
_TEMPLATES: dict[str, type[BaseTemplateStrategy]] = {
    "default": DefaultTemplateStrategy,
    "classic": DefaultTemplateStrategy,
    "template1": DefaultTemplateStrategy,
    "template2": Template2Strategy,
}


def get_template_strategy(
    template_name_or_path: str | Path | None = None,
) -> BaseTemplateStrategy:
    """Resolve a TemplateStrategy instance by name or master YAML path."""
    if template_name_or_path is None:
        return DefaultTemplateStrategy()

    key = str(template_name_or_path).strip().lower()

    # Check registered names
    if key in _TEMPLATES:
        return _TEMPLATES[key]()

    # Check file path match
    path_name = Path(template_name_or_path).name.lower()
    if "template2" in path_name:
        return Template2Strategy()

    return DefaultTemplateStrategy()
