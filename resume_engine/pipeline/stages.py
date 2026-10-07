"""Pipeline stages — JSON for control flow; tagged/plain text for content."""

from __future__ import annotations

import json
from typing import Any

from resume_engine.ai_client import AIClient
from resume_engine.config import PersonalizationConfig
from resume_engine.console_ui import RunStats
from resume_engine.format_ops import format_experience, format_projects, format_summary
from resume_engine.models import (
    ExperienceRewrite,
    JDJson,
    ProjectsRewrite,
    ResumeSelection,
    SkillsResult,
    SummaryResult,
)
from resume_engine.normalize import (
    clean_skills,
    normalize_experience,
    normalize_projects,
    normalize_summary,
)
from resume_engine.prompt_contract import OUTPUT_CONTRACT
from resume_engine.text_parsers import parse_experience_tagged, parse_projects_tagged
from resume_engine.yaml_ops import clean_markdown_label, clean_project_label, match_project_name


def parse_jd(client: AIClient, job_text: str) -> JDJson:
    system = (
        OUTPUT_CONTRACT
        + "\nYou extract structured fields from a job description.\n"
        "Output format: a single JSON object only."
    )
    user = (
        "Extract resume-useful fields from this job description.\n"
        "Output format: JSON with keys exactly:\n"
        "role, mentioned_skills, keywords, responsibilities, jd_summary_focus.\n"
        "role: concise title reflecting the primary track "
        "(e.g. Backend Engineer, Frontend Engineer, Full Stack Engineer, Data Engineer).\n"
        "mentioned_skills / keywords / responsibilities are string arrays.\n"
        "keywords: role-critical tech and domain terms for ATS (backend vs frontend vs other).\n"
        "jd_summary_focus: one short sentence stating what a Profile summary MUST emphasize "
        "for THIS role only (e.g. backend APIs, databases, services — not unrelated tracks).\n"
        "Unknown values must be empty string or empty array.\n\n"
        f"JOB DESCRIPTION:\n{job_text}"
    )
    return client.complete_json(system=system, user=user, schema=JDJson)


def select_resume(
    client: AIClient,
    jd: JDJson,
    inventory: dict[str, Any],
    personalization: PersonalizationConfig,
) -> ResumeSelection:
    system = (
        OUTPUT_CONTRACT
        + "\nYou select resume projects and build the final Skills section.\n"
        "Output format: a single JSON object only."
    )
    catalog = inventory.get("project_catalog") or []
    user = (
        "Build resume selection for this role.\n"
        "Output format: JSON with keys exactly:\n"
        '{"selected_projects": [str, str], '
        '"skills": [{"label": str, "details": str}]}\n\n'
        "PROJECT RULES:\n"
        "- Choose exactly TWO projects from PROJECT_CATALOG.\n"
        "- Prefer returning the catalog id values (e.g. \"1\", \"3\").\n"
        "- Short plain names are also OK (e.g. \"Mini Tool App\").\n"
        "- Never invent new projects. Never return markdown links.\n"
        "- Do not wrap names in brackets.\n\n"
        "SKILLS RULES:\n"
        "- Return the entire final Skills section (label + details).\n"
        "- Reorder categories for the JD.\n"
        f"- allow_new_technologies={personalization.allow_new_technologies}\n"
        "- If allow_new_technologies is true, you may add JD technologies into details.\n"
        "- If false, only use technologies already in CURRENT_SKILLS.\n"
        "- Remove irrelevant categories/details if needed.\n"
        "- Every skill must have non-empty label and details.\n\n"
        f"MENTIONED_SKILLS:\n{json.dumps(jd.mentioned_skills)}\n"
        f"KEYWORDS:\n{json.dumps(jd.keywords)}\n"
        f"PROJECT_CATALOG:\n{json.dumps(catalog)}\n"
        f"CURRENT_SKILLS:\n{json.dumps(inventory.get('skills', []))}\n"
    )
    return client.complete_json(system=system, user=user, schema=ResumeSelection)


def generate_summary(
    client: AIClient,
    jd: JDJson,
    selection: ResumeSelection,
    skills: SkillsResult,
    inventory: dict[str, Any],
) -> SummaryResult:
    system = (
        OUTPUT_CONTRACT
        + "\nYou write a role-targeted resume Profile summary.\n"
        "Output format: plain text only (no JSON, no tags)."
    )
    role = (jd.role or "").strip() or "Software Engineer"
    user = (
        "Write the Profile summary as ONE continuous paragraph of plain text only.\n"
        "STRICT FORMAT:\n"
        "- Single paragraph only.\n"
        "- No newline characters.\n"
        "- No bullet lists.\n"
        "- About 40–80 words.\n"
        "Third person implied (no I/me/my). No markdown fences.\n"
        "Do not invent employers, degrees, or metrics.\n\n"
        "ROLE ALIGNMENT & CANDIDATE GROUNDING (mandatory):\n"
        f"- Target ROLE context: {role}\n"
        "- Candidate evidence = SOURCE OF TRUTH. JD = relevance/emphasis signal ONLY.\n"
        "- Candidate evidence (MASTER_PROFILE_SUMMARY, FINAL_SKILLS, EXPERIENCE_TITLES, SELECTED_PROJECTS) is the sole basis of truth.\n"
        "- Do NOT rename or relabel the candidate with the target ROLE if it differs from their actual background (e.g. do not call the candidate a 'GTM Engineer Intern' or invent roles not in their profile).\n"
        "- JD keywords, responsibilities, tools, and technologies can ONLY be included in the Profile when they are explicitly supported by the candidate's actual resume/profile data.\n"
        "- The JD may influence what genuine experience is emphasized, but it MUST NEVER introduce a new candidate capability, tool, technology, or domain experience.\n"
        "- FOR EXAMPLE: If the JD mentions HubSpot, CRM integrations, or sales-ops tooling and those are not present in candidate evidence, the Profile MUST NOT claim experience with them.\n"
        "- Use ROLE_KEYWORDS and MENTIONED_SKILLS ONLY if they are explicitly supported by candidate evidence and FINAL_SKILLS.\n"
        "- If ROLE is Backend: emphasize APIs, services, databases, servers, "
        "performance, reliability — do NOT mention frontend/UI/CSS/design.\n"
        "- If ROLE is Frontend: emphasize UI, React/components, UX, client apps — "
        "do NOT emphasize backend infrastructure unless clearly required.\n"
        "- If ROLE is Full Stack: balance both sides briefly; still prioritize JD keywords.\n"
        "- If there is weak overlap between candidate profile and target ROLE, emphasize candidate's closest genuine experience instead of fabricating alignment.\n"
        "- Drop unrelated skills from FINAL_SKILLS; do not force every skill into the summary.\n\n"
        f"MASTER_PROFILE_SUMMARY:\n{inventory.get('master_summary', '')}\n"
        f"JD_SUMMARY_FOCUS:\n{jd.jd_summary_focus}\n"
        f"ROLE_KEYWORDS:\n{json.dumps(jd.keywords)}\n"
        f"MENTIONED_SKILLS:\n{json.dumps(jd.mentioned_skills)}\n"
        f"FINAL_SKILLS:\n{json.dumps([s.model_dump() for s in skills.skills])}\n"
        f"SELECTED_PROJECTS:\n{json.dumps(selection.selected_projects)}\n"
        f"EXPERIENCE_TITLES:\n{json.dumps(inventory.get('experience_titles', []))}\n"
    )
    raw = client.complete_text(system=system, user=user)
    normalized = normalize_summary(raw)
    return format_summary(normalized)


def rewrite_experience(
    client: AIClient,
    jd: JDJson,
    experience_entries: list[dict[str, Any]],
    personalization: PersonalizationConfig,
    stats: RunStats | None = None,
) -> ExperienceRewrite:
    compact = [
        {
            "company": e.get("company"),
            "position": e.get("position"),
            "highlights": list(e.get("highlights") or []),
        }
        for e in experience_entries
        if isinstance(e, dict)
    ]
    system = (
        OUTPUT_CONTRACT
        + "\nYou rewrite experience bullets for ATS alignment.\n"
        "Output format: tagged text only (no JSON)."
    )
    user = (
        "Rewrite experience highlights for every company.\n"
        "Keep EVERY company. Do not add or remove companies.\n"
        "Write exactly 5 bullets per company when possible (3+ is acceptable).\n"
        f"allow_new_bullets={personalization.allow_new_bullets}\n"
        f"allow_metric_changes={personalization.allow_metric_changes}\n"
        f"allow_new_keywords={personalization.allow_new_keywords}\n"
        "If allow_metric_changes is false, do not invent or change numeric metrics.\n"
        "No first person (I/me/my).\n\n"
        "Output format (repeat for each company):\n"
        "[[COMPANY]]\n"
        "Company Name Exactly As Given\n"
        "- Bullet 1\n"
        "- Bullet 2\n"
        "- Bullet 3\n"
        "- Bullet 4\n"
        "- Bullet 5\n\n"
        f"KEYWORDS:\n{json.dumps(jd.keywords)}\n"
        f"RESPONSIBILITIES:\n{json.dumps(jd.responsibilities)}\n"
        f"EXPERIENCE:\n{json.dumps(compact)}\n"
    )
    raw = client.complete_text(system=system, user=user)
    parsed = parse_experience_tagged(raw)
    if stats is not None and parsed.repairs:
        stats.parser_repairs += 1
    assert isinstance(parsed.value, ExperienceRewrite)
    return format_experience(normalize_experience(parsed.value))


def rewrite_projects(
    client: AIClient,
    jd: JDJson,
    selection: ResumeSelection,
    project_entries: list[dict[str, Any]],
    personalization: PersonalizationConfig,
    stats: RunStats | None = None,
) -> ProjectsRewrite:
    master_names = [
        str(e["name"]) for e in project_entries if isinstance(e, dict) and "name" in e
    ]
    selected_rows: list[dict[str, Any]] = []
    for pref in selection.selected_projects:
        matched = match_project_name(pref, master_names)
        if matched is None:
            continue
        base = next(
            e
            for e in project_entries
            if isinstance(e, dict) and e.get("name") == matched
        )
        selected_rows.append(
            {
                "name": base.get("name"),
                "summary": base.get("summary"),
                "highlights": list(base.get("highlights") or []),
            }
        )
    if not selected_rows:
        selected_rows = [
            {
                "name": e.get("name"),
                "summary": e.get("summary"),
                "highlights": list(e.get("highlights") or []),
            }
            for e in project_entries
            if isinstance(e, dict)
        ][:2]

    system = (
        OUTPUT_CONTRACT
        + "\nYou rewrite selected project entries for ATS alignment.\n"
        "Output format: tagged text only (no JSON)."
    )
    user = (
        "Rewrite exactly the selected projects.\n"
        f"MUST use these project names/ids: {json.dumps(selection.selected_projects)}\n"
        "Return short project names only (no markdown links).\n"
        "Write about 4 highlight bullets per project when possible.\n"
        f"allow_new_bullets={personalization.allow_new_bullets}\n"
        f"allow_metric_changes={personalization.allow_metric_changes}\n"
        f"allow_new_keywords={personalization.allow_new_keywords}\n"
        "If allow_metric_changes is false, do not invent or change numeric metrics.\n"
        "No first person (I/me/my).\n\n"
        "Output format (repeat for each project):\n"
        "[[PROJECT]]\n"
        "Project Name Exactly As Given\n"
        "SUMMARY:\n"
        "One short summary sentence\n"
        "HIGHLIGHTS:\n"
        "- Bullet 1\n"
        "- Bullet 2\n"
        "- Bullet 3\n"
        "- Bullet 4\n\n"
        f"KEYWORDS:\n{json.dumps(jd.keywords)}\n"
        f"PROJECTS:\n{json.dumps(selected_rows)}\n"
    )
    raw = client.complete_text(system=system, user=user)
    parsed = parse_projects_tagged(raw)
    if stats is not None and parsed.repairs:
        stats.parser_repairs += 1
    assert isinstance(parsed.value, ProjectsRewrite)
    return format_projects(normalize_projects(parsed.value))


def skills_from_selection(selection: ResumeSelection) -> SkillsResult:
    """Engine pass-through: validate/clean only — no skill rebuild."""
    return clean_skills(selection.skills)


def display_company_names(experience: ExperienceRewrite) -> list[str]:
    return [clean_markdown_label(e.company) for e in experience.entries]


def display_project_names(projects: ProjectsRewrite) -> list[str]:
    return [clean_project_label(p.name) for p in projects.projects]
