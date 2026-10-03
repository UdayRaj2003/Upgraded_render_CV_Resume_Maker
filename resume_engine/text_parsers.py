"""Deterministic parsers for tagged AI text outputs (with light auto-repair)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from resume_engine.models import (
    ExperienceEntryRewrite,
    ExperienceRewrite,
    ProjectRewriteEntry,
    ProjectsRewrite,
)

COMPANY_TAG_RE = re.compile(r"^\[\[\s*company\s*\]\]\s*$", re.IGNORECASE)
PROJECT_TAG_RE = re.compile(r"^\[\[\s*project\s*\]\]\s*$", re.IGNORECASE)
# Also accept single-bracket typos: [COMPANY]
COMPANY_TAG_LOOSE_RE = re.compile(r"^\[\s*company\s*\]\s*$", re.IGNORECASE)
PROJECT_TAG_LOOSE_RE = re.compile(r"^\[\s*project\s*\]\s*$", re.IGNORECASE)
BULLET_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^```(?:\w+)?\s*|\s*```$", re.MULTILINE)


class ParseError(Exception):
    pass


@dataclass
class ParseResult:
    """Parsed value plus optional auto-repair notes (user-safe, no raw AI text)."""

    value: ExperienceRewrite | ProjectsRewrite
    repairs: list[str] = field(default_factory=list)


def _preprocess(text: str) -> tuple[list[str], list[str]]:
    repairs: list[str] = []
    raw = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "```" in raw:
        cleaned = FENCE_RE.sub("", raw).strip()
        if cleaned != raw:
            repairs.append("Removed markdown fences")
            raw = cleaned
    lines = raw.split("\n")
    return lines, repairs


def _is_company_tag(line: str, repairs: list[str]) -> bool:
    text = line.strip()
    if COMPANY_TAG_RE.match(text):
        return True
    if COMPANY_TAG_LOOSE_RE.match(text):
        if "Normalized COMPANY tag" not in repairs:
            repairs.append("Normalized COMPANY tag")
        return True
    return False


def _is_project_tag(line: str, repairs: list[str]) -> bool:
    text = line.strip()
    if PROJECT_TAG_RE.match(text):
        return True
    if PROJECT_TAG_LOOSE_RE.match(text):
        if "Normalized PROJECT tag" not in repairs:
            repairs.append("Normalized PROJECT tag")
        return True
    return False


def _clean_name(name: str, repairs: list[str]) -> str:
    text = name.strip().strip("*").strip()
    # Strip wrapping bold/italics leftovers
    if text.startswith("**") and text.endswith("**") and len(text) > 4:
        text = text[2:-2].strip()
        repairs.append("Cleaned name formatting")
    return text


def _as_bullet(raw: str, repairs: list[str]) -> str | None:
    text = raw.strip()
    if not text:
        return None
    match = BULLET_RE.match(text)
    if match:
        return match.group(1).strip()
    # Auto-repair: treat plain content lines as bullets
    if (
        not _is_company_tag(text, repairs)
        and not _is_project_tag(text, repairs)
        and not text.upper().startswith("SUMMARY")
        and not text.upper().startswith("HIGHLIGHTS")
        and not text.startswith("[")
    ):
        if "Accepted unbulleted lines" not in repairs:
            repairs.append("Accepted unbulleted lines")
        return text
    return None


def parse_experience_tagged(text: str) -> ParseResult:
    lines, repairs = _preprocess(text)
    entries: list[ExperienceEntryRewrite] = []
    i = 0
    while i < len(lines):
        if not _is_company_tag(lines[i], repairs):
            i += 1
            continue
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            raise ParseError("[[COMPANY]] tag missing company name")
        company = _clean_name(lines[i], repairs)
        i += 1
        bullets: list[str] = []
        while i < len(lines):
            raw = lines[i].strip()
            if _is_company_tag(raw, repairs) or _is_project_tag(raw, repairs):
                break
            bullet = _as_bullet(raw, repairs)
            if bullet:
                bullets.append(bullet)
            i += 1
        if not company:
            raise ParseError("Empty company name after [[COMPANY]]")
        entries.append(ExperienceEntryRewrite(company=company, highlights=bullets))
    if not entries:
        raise ParseError("No [[COMPANY]] blocks found")
    return ParseResult(value=ExperienceRewrite(entries=entries), repairs=repairs)


def parse_projects_tagged(text: str) -> ParseResult:
    lines, repairs = _preprocess(text)
    projects: list[ProjectRewriteEntry] = []
    i = 0
    while i < len(lines):
        if not _is_project_tag(lines[i], repairs):
            i += 1
            continue
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            raise ParseError("[[PROJECT]] tag missing project name")
        name = _clean_name(lines[i], repairs)
        i += 1
        summary: str | None = None
        highlights: list[str] = []
        mode: str | None = None
        while i < len(lines):
            raw = lines[i].strip()
            if _is_project_tag(raw, repairs) or _is_company_tag(raw, repairs):
                break
            upper = raw.upper()
            if upper.startswith("SUMMARY"):
                # SUMMARY: or SUMMARY on its own line
                if ":" in raw:
                    rest = raw.split(":", 1)[1].strip()
                    summary = rest if rest else ""
                else:
                    summary = ""
                    if "Normalized SUMMARY label" not in repairs:
                        repairs.append("Normalized SUMMARY label")
                mode = "summary"
                i += 1
                continue
            if upper.startswith("HIGHLIGHTS"):
                mode = "highlights"
                if not upper.startswith("HIGHLIGHTS:"):
                    if "Normalized HIGHLIGHTS label" not in repairs:
                        repairs.append("Normalized HIGHLIGHTS label")
                i += 1
                continue
            if mode == "summary":
                if raw:
                    summary = (summary + " " + raw).strip() if summary else raw
                i += 1
                continue
            if mode == "highlights":
                bullet = _as_bullet(raw, repairs)
                if bullet:
                    highlights.append(bullet)
                i += 1
                continue
            bullet = _as_bullet(raw, repairs)
            if bullet:
                mode = "highlights"
                highlights.append(bullet)
            i += 1
        if not name:
            raise ParseError("Empty project name after [[PROJECT]]")
        projects.append(
            ProjectRewriteEntry(name=name, summary=summary or None, highlights=highlights)
        )
    if not projects:
        raise ParseError("No [[PROJECT]] blocks found")
    return ParseResult(value=ProjectsRewrite(projects=projects[:2]), repairs=repairs)
