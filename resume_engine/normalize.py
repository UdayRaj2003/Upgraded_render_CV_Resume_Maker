"""Light cleanup of AI content before format_ops."""

from __future__ import annotations

import re

from resume_engine.models import (
    ExperienceRewrite,
    ProjectRewriteEntry,
    ProjectsRewrite,
    SkillCategory,
    SkillsResult,
)

FIRST_PERSON_RE = re.compile(
    r"\b(I|I'm|I've|I'd|I'll|me|my|mine|we|we're|we've|we'd|we'll|our|ours)\b",
    re.IGNORECASE,
)
SPACE_RE = re.compile(r"[ \t]+")
DUP_COMMA_RE = re.compile(r"\s*,\s*,+")


def strip_first_person(text: str) -> str:
    return FIRST_PERSON_RE.sub("", text)


def clean_spaces(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = SPACE_RE.sub(" ", text)
    text = DUP_COMMA_RE.sub(",", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def normalize_summary(text: str) -> str:
    text = strip_first_person(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse to single paragraph for later line wrapping
    text = " ".join(ln.strip() for ln in text.splitlines() if ln.strip())
    return clean_spaces(text)


def normalize_bullet(text: str) -> str:
    text = strip_first_person(text)
    text = text.lstrip("-*• ").strip()
    return clean_spaces(text)


def normalize_experience(exp: ExperienceRewrite) -> ExperienceRewrite:
    entries = []
    for entry in exp.entries:
        highlights = [normalize_bullet(h) for h in entry.highlights if normalize_bullet(h)]
        entries.append(
            type(entry)(company=clean_spaces(entry.company), highlights=highlights)
        )
    return ExperienceRewrite(entries=entries)


def normalize_projects(projects: ProjectsRewrite) -> ProjectsRewrite:
    out: list[ProjectRewriteEntry] = []
    for p in projects.projects:
        summary = normalize_summary(p.summary) if p.summary else None
        highlights = [normalize_bullet(h) for h in p.highlights if normalize_bullet(h)]
        out.append(
            ProjectRewriteEntry(
                name=clean_spaces(p.name),
                summary=summary,
                highlights=highlights,
            )
        )
    return ProjectsRewrite(projects=out)


def clean_skills(skills: list[SkillCategory]) -> SkillsResult:
    """Validate and lightly clean skills from ResumeSelection (no rebuild)."""
    cleaned: list[SkillCategory] = []
    seen_labels: set[str] = set()
    for skill in skills:
        label = clean_spaces(skill.label)
        details = clean_spaces(skill.details)
        details = re.sub(r"\s*,\s*", ", ", details)
        # Drop duplicate detail tokens (case-insensitive)
        parts: list[str] = []
        seen_parts: set[str] = set()
        for part in details.split(","):
            token = part.strip()
            if not token:
                continue
            key = token.lower()
            if key in seen_parts:
                continue
            seen_parts.add(key)
            parts.append(token)
        details = ", ".join(parts)
        label_key = label.lower()
        if not label or not details:
            continue
        if label_key in seen_labels:
            continue
        seen_labels.add(label_key)
        cleaned.append(SkillCategory(label=label, details=details))
    return SkillsResult(skills=cleaned)
