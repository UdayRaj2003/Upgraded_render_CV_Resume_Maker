"""Schema + business-rule validation and retry wrapper."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import TypeVar

from resume_engine.config import PersonalizationConfig
from resume_engine.console_ui import ConsoleUI, RunStats, friendly_failure_reasons
from resume_engine.logging_util import RunLogger
from resume_engine.models import (
    ExperienceRewrite,
    ProjectsRewrite,
    ResumeSelection,
    SkillsResult,
    SummaryResult,
)
from resume_engine.yaml_ops import (
    clean_markdown_label,
    clean_project_label,
    match_company_name,
    match_project_name,
)

T = TypeVar("T")

# Soft content bounds (format_ops still normalizes toward targets).
SUMMARY_MIN_WORDS = 15
SUMMARY_MAX_WORDS = 120
EXPERIENCE_MIN_BULLETS = 2
EXPERIENCE_MAX_BULLETS = 8
PROJECT_MIN_HIGHLIGHTS = 1
PROJECT_MAX_HIGHLIGHTS = 8


class ValidationError(Exception):
    pass


def validate_selection(
    selection: ResumeSelection, master_project_names: list[str]
) -> None:
    if len(selection.selected_projects) < 1:
        raise ValidationError("selected_projects must not be empty")
    # Prefer exactly 2, but accept 1–2 to reduce hard AI failures
    if len(selection.selected_projects) > 2:
        selection.selected_projects = selection.selected_projects[:2]

    resolved: list[str] = []
    for name in selection.selected_projects:
        matched = match_project_name(name, master_project_names)
        if matched is None:
            raise ValidationError(f"Unknown project: {name}")
        resolved.append(matched)
    if len(set(resolved)) < 1:
        raise ValidationError("selected_projects must resolve to master projects")

    # Normalize selection to resolved short labels for downstream prompts
    selection.selected_projects = [
        clean_project_label(name) for name in resolved
    ]

    if not selection.skills:
        raise ValidationError("skills must not be empty")
    for row in selection.skills:
        if not row.label.strip() or not row.details.strip():
            raise ValidationError("each skill needs non-empty label and details")


def validate_skills(skills: SkillsResult) -> None:
    if not skills.skills:
        raise ValidationError("skills must not be empty")
    for row in skills.skills:
        if not row.label.strip() or not row.details.strip():
            raise ValidationError("each skill needs label and details")


def validate_summary(summary: SummaryResult) -> None:
    text = " ".join(summary.summary.split()).strip()
    if not text:
        raise ValidationError("summary must not be empty")
    # Soft: only reject empty / absurdly short or long
    words = len(text.split())
    if words < SUMMARY_MIN_WORDS:
        raise ValidationError(
            f"summary too short (min {SUMMARY_MIN_WORDS} words)"
        )
    if words > SUMMARY_MAX_WORDS:
        raise ValidationError(
            f"summary too long (max {SUMMARY_MAX_WORDS} words)"
        )


def validate_experience(
    rewrite: ExperienceRewrite,
    master_companies: list[str],
    original_highlights: dict[str, list[str]],
    personalization: PersonalizationConfig,
) -> None:
    if not rewrite.entries:
        raise ValidationError("experience entries must not be empty")
    # Soft: do not require covering every company if AI misses one
    seen: set[str] = set()
    matched_count = 0
    for entry in rewrite.entries:
        matched = match_company_name(entry.company, master_companies)
        if matched is None:
            continue
        matched_count += 1
        key = clean_markdown_label(matched).lower()
        if key in seen:
            continue
        seen.add(key)
        n = len([h for h in entry.highlights if h.strip()])
        if n < EXPERIENCE_MIN_BULLETS:
            raise ValidationError(
                f"{entry.company}: need at least {EXPERIENCE_MIN_BULLETS} bullets"
            )
        if n > EXPERIENCE_MAX_BULLETS:
            entry.highlights = entry.highlights[:EXPERIENCE_MAX_BULLETS]
        # Metric invent check intentionally skipped (too brittle for free models)
    if matched_count < 1:
        raise ValidationError("No experience entries matched master companies")


def validate_projects(
    rewrite: ProjectsRewrite,
    master_project_names: list[str],
    original_highlights: dict[str, list[str]],
    personalization: PersonalizationConfig,
    selected_projects: list[str] | None = None,
) -> None:
    if not rewrite.projects:
        raise ValidationError("projects must not be empty")
    if len(rewrite.projects) > 2:
        rewrite.projects = rewrite.projects[:2]

    selected_resolved: set[str] | None = None
    if selected_projects is not None:
        selected_resolved = set()
        for name in selected_projects:
            matched_sel = match_project_name(name, master_project_names)
            if matched_sel is not None:
                selected_resolved.add(matched_sel)

    matched_count = 0
    for proj in rewrite.projects:
        matched = match_project_name(proj.name, master_project_names)
        if matched is None:
            continue
        if selected_resolved is not None and matched not in selected_resolved:
            # Soft: allow if it still resolves to a master project
            pass
        matched_count += 1
        n = len([h for h in proj.highlights if h.strip()])
        if n < PROJECT_MIN_HIGHLIGHTS:
            raise ValidationError(
                f"{proj.name}: need at least {PROJECT_MIN_HIGHLIGHTS} highlights"
            )
        if n > PROJECT_MAX_HIGHLIGHTS:
            proj.highlights = proj.highlights[:PROJECT_MAX_HIGHLIGHTS]
    if matched_count < 1:
        raise ValidationError("No projects matched master project names")


def with_retries(
    *,
    stage: str,
    max_retries: int,
    logger: RunLogger,
    fn: Callable[[], T],
    detail_fn: Callable[[T], str] | None = None,
    console: ConsoleUI | None = None,
    stats: RunStats | None = None,
    stage_index: int | None = None,
    stage_total: int = 5,
    stage_title: str | None = None,
    on_success: Callable[[T, RunStats | None, ConsoleUI | None], None] | None = None,
    repairs_before: int | None = None,
) -> T:
    """Retry a stage. File logger stays detailed; console stays high-level."""
    title = stage_title or stage
    if console is not None and stage_index is not None:
        console.stage_start(stage_index, stage_total, title)

    last_error: Exception | None = None
    started_stage = time.perf_counter()
    for attempt in range(1, max_retries + 1):
        attempt_started = time.perf_counter()
        repairs_at_start = (
            stats.parser_repairs if stats is not None else (repairs_before or 0)
        )
        try:
            if stats is not None:
                stats.ai_calls += 1
            result = fn()
            if stats is not None:
                stats.successful_calls += 1
            elapsed = time.perf_counter() - attempt_started
            detail = f"  {detail_fn(result)}" if detail_fn else ""
            logger.info(f"{stage:<16} ✓ {elapsed:.1f} s{detail}")
            if attempt > 1:
                logger.info(f"{stage} succeeded on attempt {attempt}/{max_retries}")

            if console is not None:
                repaired_now = (
                    stats is not None and stats.parser_repairs > repairs_at_start
                )
                if repaired_now:
                    console.parser_repaired()
                if on_success is not None:
                    on_success(result, stats, console)
                console.stage_completed(time.perf_counter() - started_stage)
            return result
        except Exception as exc:  # noqa: BLE001 — boundary retry
            last_error = exc
            elapsed = time.perf_counter() - attempt_started
            logger.warning(
                f"{stage:<16} ✗ {elapsed:.1f} s  attempt {attempt}/{max_retries}: {exc}"
            )
            reasons = friendly_failure_reasons(exc)
            if attempt < max_retries:
                if stats is not None:
                    stats.retries += 1
                if console is not None:
                    console.warn(reasons[0])
                    console.retry(attempt, max_retries)

    assert last_error is not None
    logger.error(f"{stage} failed after {max_retries} attempts")
    if console is not None:
        console.stage_failed(max_retries, friendly_failure_reasons(last_error))
    raise last_error
