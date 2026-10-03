"""Public orchestration: generate_resume(job_text) -> GenerateResult."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from resume_engine.ai_client import AIClient
from resume_engine.config import EngineConfig, load_engine_config
from resume_engine.console_ui import ConsoleUI, RunStats
from resume_engine.logging_util import RunLogger
from resume_engine.models import (
    ExperienceRewrite,
    GenerateResult,
    JDJson,
    ProjectsRewrite,
    ResumeSelection,
    SkillsResult,
    SummaryResult,
)
from resume_engine.pipeline import (
    generate_summary,
    parse_jd,
    rewrite_experience,
    rewrite_projects,
    select_resume,
    skills_from_selection,
)
from resume_engine.pipeline.stages import display_company_names, display_project_names
from resume_engine.render import RenderError, render_yaml_to_pdf
from resume_engine.validate import (
    validate_experience,
    validate_projects,
    validate_selection,
    validate_skills,
    validate_summary,
    with_retries,
)
from resume_engine.yaml_ops import (
    apply_personalization,
    clean_markdown_label,
    clean_project_label,
    create_temp_copy,
    file_sha256,
    get_sections,
    inventory_from_master,
    load_master_readonly,
    write_yaml,
)


def generate_resume(
    job_text: str,
    *,
    config_path: Path | None = None,
    master_yaml: Path | None = None,
    output_dir: Path | None = None,
    console: bool | None = None,
) -> GenerateResult:
    """Personalize a temp copy of the master RenderCV YAML and render a PDF.

    Never modifies the master YAML. On personalization failure after retries,
    renders the original master YAML and returns success=False.

    Console progress is on by default. Disable with ``console=False`` or
    ``RESUME_ENGINE_CONSOLE=0``.
    """
    if not job_text or not str(job_text).strip():
        raise ValueError("job_text must be a non-empty string")

    cfg = load_engine_config(config_path)
    if master_yaml is not None:
        cfg.master_yaml = Path(master_yaml)
    if output_dir is not None:
        cfg.output_dir = Path(output_dir)
        cfg.temp_dir = cfg.output_dir / "temp"

    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.temp_dir.mkdir(parents=True, exist_ok=True)

    logger = RunLogger(cfg.logs_dir)
    ui = ConsoleUI(enabled=_console_enabled(console))
    stats = RunStats()
    started = time.perf_counter()
    master_hash_before = file_sha256(cfg.master_yaml)

    try:
        return _run_pipeline(
            job_text, cfg, logger, ui, stats, started, master_hash_before
        )
    finally:
        master_hash_after = file_sha256(cfg.master_yaml)
        if master_hash_before != master_hash_after:
            logger.error("CRITICAL: master YAML hash changed during run")
        logger.close()


def _console_enabled(console: bool | None) -> bool:
    if console is not None:
        return console
    env = os.environ.get("RESUME_ENGINE_CONSOLE", "").strip().lower()
    if env in {"0", "false", "off", "no"}:
        return False
    if env in {"1", "true", "on", "yes"}:
        return True
    return True


def _run_pipeline(
    job_text: str,
    cfg: EngineConfig,
    logger: RunLogger,
    ui: ConsoleUI,
    stats: RunStats,
    started: float,
    master_hash_before: str,
) -> GenerateResult:
    def on_key_switch(message: str) -> None:
        logger.warning(message)
        # Console-friendly short form without secrets
        if "rate-limited" in message:
            reason = "Rate limited"
        elif "unauthorized" in message:
            reason = "Unauthorized"
        elif "server error" in message:
            reason = "Server error"
        else:
            reason = "Request failed"
        # message ends with "switching to key N/M"
        label = message.rsplit("key ", 1)[-1].strip()
        ui.warn(f"{reason} — switched API key ({label})")

    client = AIClient(cfg.ai, on_key_switch=on_key_switch)
    master_data = load_master_readonly(cfg.master_yaml)
    inventory = inventory_from_master(master_data, cfg.sections)
    sections = get_sections(master_data)
    experience_entries = list(sections.get(cfg.sections.experience) or [])
    project_entries = list(sections.get(cfg.sections.projects) or [])
    master_companies = inventory["companies"]
    master_projects = inventory["project_names"]

    original_exp_highlights = {
        clean_markdown_label(str(e.get("company", ""))).lower(): list(
            e.get("highlights") or []
        )
        for e in experience_entries
        if isinstance(e, dict)
    }
    original_proj_highlights = {
        clean_project_label(str(e.get("name", ""))).lower(): list(
            e.get("highlights") or []
        )
        for e in project_entries
        if isinstance(e, dict)
    }

    retries = cfg.ai.max_retries
    ui.banner_start()

    try:
        jd = with_retries(
            stage="JDParse",
            stage_title="JD Parsing",
            stage_index=1,
            max_retries=retries,
            logger=logger,
            console=ui,
            stats=stats,
            fn=lambda: parse_jd(client, job_text),
        )

        selection = with_retries(
            stage="ResumeSelection",
            stage_title="Resume Selection",
            stage_index=2,
            max_retries=retries,
            logger=logger,
            console=ui,
            stats=stats,
            fn=lambda: _selection_and_validate(
                client, jd, inventory, master_projects, cfg
            ),
            on_success=_on_selection_success,
        )

        skills = skills_from_selection(selection)
        validate_skills(skills)
        stats.skills_categories = len(skills.skills)
        logger.info(f"Skills               cleaned ({len(skills.skills)} categories)")

        summary = with_retries(
            stage="Summary",
            stage_title="Summary Generation",
            stage_index=3,
            max_retries=retries,
            logger=logger,
            console=ui,
            stats=stats,
            fn=lambda: _summary_and_validate(
                client, jd, selection, skills, inventory
            ),
        )

        experience = with_retries(
            stage="Experience",
            stage_title="Experience Rewrite",
            stage_index=4,
            max_retries=retries,
            logger=logger,
            console=ui,
            stats=stats,
            fn=lambda: _experience_and_validate(
                client,
                jd,
                experience_entries,
                master_companies,
                original_exp_highlights,
                cfg,
                stats,
            ),
            on_success=_on_experience_success,
        )

        projects = with_retries(
            stage="Projects",
            stage_title="Project Rewrite",
            stage_index=5,
            max_retries=retries,
            logger=logger,
            console=ui,
            stats=stats,
            fn=lambda: _projects_and_validate(
                client,
                jd,
                selection,
                project_entries,
                master_projects,
                original_proj_highlights,
                cfg,
                stats,
            ),
            on_success=_on_projects_success,
        )

        ui.formatting_start()
        ui.item_ok("Summary normalized")
        ui.item_ok("Bullet counts fixed")
        ui.item_ok("Keywords highlighted")
        ui.item_ok("Headline removed")
        ui.blank()

        personalized = apply_personalization(
            master_data,
            cfg=cfg,
            skills=skills,
            summary=summary,
            experience=experience,
            projects=projects,
        )
        temp_yaml = create_temp_copy(cfg.master_yaml, cfg.temp_dir)
        write_yaml(temp_yaml, personalized)

        if file_sha256(cfg.master_yaml) != master_hash_before:
            raise RuntimeError("Master YAML was modified unexpectedly")

        ui.rendering_start()
        try:
            run_out = cfg.output_dir / f"run_{temp_yaml.stem}"
            artifacts = render_yaml_to_pdf(
                temp_yaml,
                run_out,
                output_filename=cfg.output_filename,
            )
        finally:
            _maybe_cleanup_temp_yaml(temp_yaml, cfg, logger)

        pdf_path = artifacts.pdf_path
        docx_path = artifacts.docx_path
        ui.item_ok("PDF Generated")
        if docx_path is not None:
            ui.item_ok("DOCX Generated")
        ui.blank()

        elapsed_s = time.perf_counter() - started
        logger.info(f"Processing time: {int(elapsed_s * 1000)} ms")
        logger.info(f"PDF: {pdf_path}")
        if docx_path is not None:
            logger.info(f"DOCX: {docx_path}")
        logger.info("Final outcome: Success")

        ui.total_time(elapsed_s)
        ui.banner_success(pdf_path, docx_path=docx_path)
        ui.summary(
            stats,
            elapsed_s=elapsed_s,
            success=True,
            pdf_path=pdf_path,
            docx_path=docx_path,
        )
        return GenerateResult(success=True, pdf_path=pdf_path, docx_path=docx_path)

    except Exception as exc:  # noqa: BLE001 — fallback boundary
        logger.error(f"Personalization failed: {exc}")
        logger.info("Fallback to Master Resume")
        ui.fallback_start()
        try:
            fallback_out = cfg.output_dir / "fallback_master"
            artifacts = render_yaml_to_pdf(
                cfg.master_yaml,
                fallback_out,
                output_filename=cfg.output_filename,
            )
            pdf_path = artifacts.pdf_path
            docx_path = artifacts.docx_path
            ui.item_ok("Done")
            ui.blank()

            elapsed_s = time.perf_counter() - started
            logger.info(f"Processing time: {int(elapsed_s * 1000)} ms")
            logger.info(f"PDF: {pdf_path}")
            if docx_path is not None:
                logger.info(f"DOCX: {docx_path}")
            logger.info("Final outcome: Fallback")

            ui.total_time(elapsed_s)
            ui.banner_fallback(pdf_path, docx_path=docx_path)
            ui.summary(
                stats,
                elapsed_s=elapsed_s,
                success=False,
                pdf_path=pdf_path,
                docx_path=docx_path,
            )
            return GenerateResult(success=False, pdf_path=pdf_path, docx_path=docx_path)
        except RenderError as render_exc:
            logger.error(f"Fallback render failed: {render_exc}")
            elapsed_s = time.perf_counter() - started
            logger.info(f"Processing time: {int(elapsed_s * 1000)} ms")
            logger.info("Final outcome: Error")
            ui.banner_error()
            raise


def _maybe_cleanup_temp_yaml(
    temp_yaml: Path, cfg: EngineConfig, logger: RunLogger
) -> None:
    if cfg.cleanup_temp_yaml:
        try:
            temp_yaml.unlink(missing_ok=True)
            logger.info("Temp YAML deleted after rendering")
        except OSError as exc:
            logger.warning(f"Could not delete temp YAML: {exc}")
    else:
        logger.info(f"Temp YAML kept for debugging: {temp_yaml}")


def _on_selection_success(
    selection: ResumeSelection, stats: RunStats | None, console: ConsoleUI | None
) -> None:
    names = list(selection.selected_projects)
    if stats is not None:
        stats.projects_selected = len(names)
        stats.project_names = names
        stats.skills_categories = len(selection.skills)
    if console is None:
        return
    console.item_ok("Selected Projects:")
    for name in names:
        console.bullet(clean_project_label(name))
    console.item_ok("Skills Updated")


def _on_experience_success(
    experience: ExperienceRewrite, stats: RunStats | None, console: ConsoleUI | None
) -> None:
    names = display_company_names(experience)
    if stats is not None:
        stats.company_names = names
    if console is None:
        return
    for name in names:
        console.item_ok(name)


def _on_projects_success(
    projects: ProjectsRewrite, stats: RunStats | None, console: ConsoleUI | None
) -> None:
    names = display_project_names(projects)
    if stats is not None:
        stats.project_names = names
        stats.projects_selected = len(names)
    if console is None:
        return
    for name in names:
        console.item_ok(name)


def _selection_and_validate(
    client: AIClient,
    jd: JDJson,
    inventory: dict[str, Any],
    master_projects: list[str],
    cfg: EngineConfig,
) -> ResumeSelection:
    selection = select_resume(client, jd, inventory, cfg.personalization)
    validate_selection(selection, master_projects)
    return selection


def _summary_and_validate(
    client: AIClient,
    jd: JDJson,
    selection: ResumeSelection,
    skills: SkillsResult,
    inventory: dict[str, Any],
) -> SummaryResult:
    summary = generate_summary(client, jd, selection, skills, inventory)
    validate_summary(summary)
    return summary


def _experience_and_validate(
    client: AIClient,
    jd: JDJson,
    experience_entries: list[Any],
    master_companies: list[str],
    original_highlights: dict[str, list[str]],
    cfg: EngineConfig,
    stats: RunStats,
) -> ExperienceRewrite:
    rewrite = rewrite_experience(
        client, jd, experience_entries, cfg.personalization, stats=stats
    )
    validate_experience(
        rewrite, master_companies, original_highlights, cfg.personalization
    )
    return rewrite


def _projects_and_validate(
    client: AIClient,
    jd: JDJson,
    selection: ResumeSelection,
    project_entries: list[Any],
    master_projects: list[str],
    original_highlights: dict[str, list[str]],
    cfg: EngineConfig,
    stats: RunStats,
) -> ProjectsRewrite:
    rewrite = rewrite_projects(
        client, jd, selection, project_entries, cfg.personalization, stats=stats
    )
    validate_projects(
        rewrite,
        master_projects,
        original_highlights,
        cfg.personalization,
        selected_projects=selection.selected_projects,
    )
    return rewrite
