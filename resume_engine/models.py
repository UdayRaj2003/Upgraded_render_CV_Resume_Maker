"""Pydantic schemas for AI JSON boundaries and engine structs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        import re

        parts = [p.strip() for p in re.split(r"[,;\n]", value) if p.strip()]
        return parts
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


class JDJson(BaseModel):
    """Slim JD fields used by downstream stages."""

    role: str = ""
    mentioned_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    jd_summary_focus: str = ""

    @field_validator(
        "mentioned_skills",
        "keywords",
        "responsibilities",
        mode="before",
    )
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _coerce_str_list(value)


class SkillCategory(BaseModel):
    label: str
    details: str

    @field_validator("label", "details", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        return str(value or "").strip()


class ResumeSelection(BaseModel):
    selected_projects: list[str] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)

    @field_validator("selected_projects", mode="before")
    @classmethod
    def coerce_projects(cls, value: Any) -> list[str]:
        return _coerce_str_list(value)[:2]


class SkillsResult(BaseModel):
    """Engine-facing skills container (from ResumeSelection)."""

    skills: list[SkillCategory] = Field(default_factory=list)
    skills_added: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    summary: str

    @field_validator("summary")
    @classmethod
    def non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("summary must be non-empty")
        return text


class ExperienceEntryRewrite(BaseModel):
    company: str
    highlights: list[str] = Field(default_factory=list)


class ExperienceRewrite(BaseModel):
    entries: list[ExperienceEntryRewrite] = Field(default_factory=list)


class ProjectRewriteEntry(BaseModel):
    name: str
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProjectsRewrite(BaseModel):
    projects: list[ProjectRewriteEntry] = Field(default_factory=list)

    @field_validator("projects")
    @classmethod
    def max_two(cls, value: list[ProjectRewriteEntry]) -> list[ProjectRewriteEntry]:
        return value[:2]


class GenerateResult:
    """Minimal public result object."""

    __slots__ = ("success", "pdf_path", "docx_path")

    def __init__(self, success: bool, pdf_path, docx_path=None) -> None:
        self.success = success
        self.pdf_path = pdf_path
        self.docx_path = docx_path

    def __repr__(self) -> str:
        return (
            f"GenerateResult(success={self.success!r}, "
            f"pdf_path={self.pdf_path!r}, docx_path={self.docx_path!r})"
        )
