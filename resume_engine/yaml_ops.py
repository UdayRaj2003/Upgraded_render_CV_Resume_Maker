"""Read-only master YAML handling: copy to temp and patch personalized sections."""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from resume_engine.config import EngineConfig, SectionsConfig
from resume_engine.models import (
    ExperienceRewrite,
    ProjectsRewrite,
    SkillsResult,
    SummaryResult,
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_master_readonly(master_path: Path) -> dict[str, Any]:
    if not master_path.is_file():
        raise FileNotFoundError(f"Master YAML not found: {master_path}")
    yaml = YAML(typ="rt")
    with master_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        raise ValueError("Master YAML root must be a mapping")
    return data


def create_temp_copy(master_path: Path, temp_dir: Path) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    dest = temp_dir / f"working_{stamp}.yaml"
    # Byte-for-byte copy first so master is never opened for write
    dest.write_bytes(master_path.read_bytes())
    return dest


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def get_sections(data: dict[str, Any]) -> dict[str, Any]:
    cv = data.get("cv")
    if not isinstance(cv, dict):
        raise ValueError("Master YAML missing cv mapping")
    sections = cv.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("Master YAML missing cv.sections")
    return sections


def inventory_from_master(data: dict[str, Any], sections_cfg: SectionsConfig) -> dict[str, Any]:
    sections = get_sections(data)
    experience = sections.get(sections_cfg.experience) or []
    projects = sections.get(sections_cfg.projects) or []
    skills = sections.get(sections_cfg.skills) or []

    companies: list[str] = []
    for entry in experience:
        if isinstance(entry, dict) and entry.get("company"):
            companies.append(str(entry["company"]))

    project_names: list[str] = []
    project_catalog: list[dict[str, str]] = []
    for idx, entry in enumerate(projects, start=1):
        if not isinstance(entry, dict) or entry.get("name") is None:
            continue
        raw_name = str(entry["name"])
        project_names.append(raw_name)
        short = clean_markdown_label(raw_name)
        project_catalog.append(
            {
                "id": str(idx),
                "name": short,
            }
        )

    skill_rows: list[dict[str, str]] = []
    for entry in skills:
        if isinstance(entry, dict):
            skill_rows.append(
                {
                    "label": str(entry.get("label", "")),
                    "details": str(entry.get("details", "")),
                }
            )

    summary_entries = sections.get(sections_cfg.summary_title) or []
    master_summary = ""
    if isinstance(summary_entries, list) and summary_entries:
        first = summary_entries[0]
        if isinstance(first, str):
            master_summary = clean_markdown_label(first)
        elif isinstance(first, dict):
            master_summary = clean_markdown_label(str(first.get("bullet") or first.get("summary") or ""))

    return {
        "companies": companies,
        "project_names": project_names,
        "project_catalog": project_catalog,
        "skills": skill_rows,
        "master_summary": master_summary,
        "experience_titles": [
            f"{e.get('position', '')} @ {e.get('company', '')}".strip(" @")
            for e in experience
            if isinstance(e, dict)
        ],
    }


def clean_markdown_label(name: str) -> str:
    """Strip markdown link/bracket wrappers to a plain display name."""
    text = name.strip().strip('"').strip("'")
    # [Label](url)
    match = re.match(r"\[([^\]]+)\]\([^)]*\)", text)
    if match:
        return match.group(1).strip()
    # [Label] without URL (common AI mistake)
    match = re.match(r"^\[([^\]]+)\]$", text)
    if match:
        return match.group(1).strip()
    return text


def clean_project_label(name: str) -> str:
    return clean_markdown_label(name)


def match_project_name(candidate: str, master_names: list[str]) -> str | None:
    """Resolve AI project id/short name/markdown to an exact master name."""
    cand = candidate.strip().strip('"').strip("'")
    if not cand:
        return None

    # Numeric id: "1", "2", ...
    if cand.isdigit():
        idx = int(cand) - 1
        if 0 <= idx < len(master_names):
            return master_names[idx]

    # id:N / project-N
    id_match = re.match(r"^(?:id|project)[\s:_-]*(\d+)$", cand, flags=re.IGNORECASE)
    if id_match:
        idx = int(id_match.group(1)) - 1
        if 0 <= idx < len(master_names):
            return master_names[idx]

    cand_clean = clean_markdown_label(cand).lower()
    # Exact clean match
    for name in master_names:
        if name == cand or clean_markdown_label(name).lower() == cand_clean:
            return name

    # Contains / prefix match (unique only)
    contains_hits = [
        name
        for name in master_names
        if cand_clean in clean_markdown_label(name).lower()
        or clean_markdown_label(name).lower() in cand_clean
    ]
    if len(contains_hits) == 1:
        return contains_hits[0]
    return None


def match_company_name(candidate: str, master_companies: list[str]) -> str | None:
    cand_clean = clean_markdown_label(candidate).lower()
    for company in master_companies:
        if company == candidate.strip() or clean_markdown_label(company).lower() == cand_clean:
            return company
    # Unique contains
    hits = [
        company
        for company in master_companies
        if cand_clean in clean_markdown_label(company).lower()
        or clean_markdown_label(company).lower() in cand_clean
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _extract_link_bullets(highlights: list[Any]) -> list[str]:
    """Extract bullet items from highlights that contain URLs or link labels."""
    link_bullets: list[str] = []
    for item in highlights:
        s = str(item)
        if any(
            kw in s.lower()
            for kw in [
                "http://",
                "https://",
                "experience letter",
                "deployment",
                "live demo",
                "certificate",
            ]
        ):
            link_bullets.append(s)
    return link_bullets


def apply_personalization(
    data: dict[str, Any],
    *,
    cfg: EngineConfig,
    skills: SkillsResult | None,
    summary: SummaryResult | None,
    experience: ExperienceRewrite | None,
    projects: ProjectsRewrite | None,
) -> dict[str, Any]:
    """Return a deep-copied document with personalized sections applied."""
    doc = copy.deepcopy(data)
    sections = get_sections(doc)
    sec = cfg.sections

    if skills is not None:
        sections[sec.skills] = [
            {"label": s.label, "details": s.details} for s in skills.skills
        ]

    if summary is not None:
        # Strict single paragraph (no newlines) as one Profile bullet entry
        paragraph = " ".join(summary.summary.split()).strip()
        sections[sec.summary_title] = [{"bullet": paragraph}]
        # Never set headline from summary (keeps design/header clean)
        if "cv" in doc and isinstance(doc["cv"], dict):
            doc["cv"]["headline"] = None

    if experience is not None:
        original = sections.get(sec.experience) or []
        master_companies = [
            str(e.get("company", ""))
            for e in original
            if isinstance(e, dict) and e.get("company")
        ]
        by_company = {
            clean_markdown_label(e.company).lower(): e for e in experience.entries
        }
        updated = []
        for entry in original:
            if not isinstance(entry, dict):
                updated.append(entry)
                continue
            company = str(entry.get("company", "")).strip()
            rewrite = by_company.get(clean_markdown_label(company).lower())
            new_entry = copy.deepcopy(entry)
            if rewrite is not None and rewrite.highlights:
                new_highlights = list(rewrite.highlights)
                orig_links = _extract_link_bullets(entry.get("highlights") or [])
                for link_bullet in orig_links:
                    if not any(
                        "http" in h.lower() or "experience letter" in h.lower()
                        for h in new_highlights
                    ):
                        new_highlights.append(link_bullet)
                new_entry["highlights"] = new_highlights
            # Keep original markdown company name from master
            updated.append(new_entry)
        sections[sec.experience] = updated

    if projects is not None:
        original = sections.get(sec.projects) or []
        master_names = [
            str(e["name"]) for e in original if isinstance(e, dict) and "name" in e
        ]
        selected: list[Any] = []
        for pref in projects.projects:
            matched = match_project_name(pref.name, master_names)
            if matched is None:
                continue
            base = next(
                copy.deepcopy(e)
                for e in original
                if isinstance(e, dict) and e.get("name") == matched
            )
            if pref.summary:
                base["summary"] = pref.summary
            if pref.highlights:
                new_highlights = list(pref.highlights)
                orig_links = _extract_link_bullets(base.get("highlights") or [])
                for link_bullet in orig_links:
                    if not any(
                        "http" in h.lower() or "deployment" in h.lower()
                        for h in new_highlights
                    ):
                        new_highlights.append(link_bullet)
                base["highlights"] = new_highlights
            # Keep original display name from master
            base["name"] = matched
            selected.append(base)
        if selected:
            sections[sec.projects] = selected

    # Immutable sections are left untouched by construction.
    return doc