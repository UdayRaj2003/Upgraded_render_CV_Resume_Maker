"""Deterministic formatting after normalize (counts, wrapping, bold)."""

from __future__ import annotations

import re

from resume_engine.models import (
    ExperienceEntryRewrite,
    ExperienceRewrite,
    ProjectRewriteEntry,
    ProjectsRewrite,
    SummaryResult,
)

EXPERIENCE_BULLETS = 5
PROJECT_HIGHLIGHTS = 4
SUMMARY_MAX_LINES = 4
SUMMARY_TARGET_WORDS = (50, 75)
SUMMARY_HARD_MAX_WORDS = 85
LINE_SOFT_CHARS = 95

# Longest-first so Node.js wins over Node, React.js over React.
BOLD_LEXICON = sorted(
    [
        "Node.js",
        "React.js",
        "React Native",
        "Next.js",
        "TypeScript",
        "JavaScript",
        "MongoDB",
        "PostgreSQL",
        "Express.js",
        "Tailwind CSS",
        "REST APIs",
        "REST API",
        "GraphQL",
        "Docker",
        "Kubernetes",
        "AWS",
        "Azure",
        "Python",
        "Django",
        "FastAPI",
        "Flask",
        "Redis",
        "Kafka",
        "Prisma",
        "Selenium",
        "Playwright",
        "Git",
        "CI/CD",
        "SQL",
        "NoSQL",
        "HTML",
        "CSS",
        "Redux",
        "Zustand",
        "JWT",
        "OAuth",
        "Stripe",
        "Firebase",
        "Vercel",
        "Linux",
        "Agile",
        "Scrum",
        "React",
        "Node",
        "Express",
        "Mongo",
        "API",
        "APIs",
    ],
    key=len,
    reverse=True,
)


def apply_bold(text: str, terms: list[str] | None = None) -> str:
    """Bold lexicon terms longest-first; skip already-bold spans."""
    lexicon = [t for t in (terms if terms is not None else BOLD_LEXICON) if t]
    if not lexicon or not text:
        return text

    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\0BOLD{len(protected) - 1}\0"

    work = re.sub(r"\*\*[^*]+\*\*", stash, text)
    # Single alternation pass: left-to-right longest-first avoids Node vs Node.js clash
    pattern = re.compile("|".join(re.escape(t) for t in lexicon), re.IGNORECASE)
    work = pattern.sub(lambda m: f"**{m.group(0)}**", work)
    for idx, chunk in enumerate(protected):
        work = work.replace(f"\0BOLD{idx}\0", chunk)
    work = re.sub(r"\*\*\*\*+", "**", work)
    return work


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",.;:") + "."


def estimated_wrap_lines(text: str, soft_chars: int = LINE_SOFT_CHARS) -> int:
    """How many soft-wrapped lines a single paragraph would need (no newlines)."""
    words = text.split()
    if not words:
        return 0
    lines = 1
    length = 0
    for word in words:
        add = len(word) + (1 if length else 0)
        if length and length + add > soft_chars:
            lines += 1
            length = len(word)
        else:
            length += add
    return lines


def format_summary(text: str) -> SummaryResult:
    """Return one continuous paragraph: no newline characters, fits ~4 soft lines."""
    text = " ".join(text.split())
    if not text:
        raise ValueError("summary empty after format_ops")

    words = text.split()
    if len(words) > SUMMARY_HARD_MAX_WORDS:
        text = _trim_words(text, SUMMARY_HARD_MAX_WORDS)
        words = text.split()
    if len(words) > SUMMARY_TARGET_WORDS[1] + 8:
        text = _trim_words(text, SUMMARY_TARGET_WORDS[1])

    # Strict: keep trimming until soft-wrap estimate is <= SUMMARY_MAX_LINES
    while (
        estimated_wrap_lines(text, LINE_SOFT_CHARS) > SUMMARY_MAX_LINES
        and len(text.split()) > SUMMARY_TARGET_WORDS[0]
    ):
        text = _trim_words(text, len(text.split()) - 5)

    if estimated_wrap_lines(text, LINE_SOFT_CHARS) > SUMMARY_MAX_LINES:
        # Final hard trim by character budget for 4 lines
        max_chars = SUMMARY_MAX_LINES * LINE_SOFT_CHARS
        if len(text) > max_chars:
            clipped = text[:max_chars].rsplit(" ", 1)[0].rstrip(",.;:")
            text = clipped + ("." if clipped and not clipped.endswith(".") else "")

    text = apply_bold(text)
    # Guarantee no newlines survive bold/trim
    text = " ".join(text.split())
    if not text:
        raise ValueError("summary empty after format_ops")
    # Soft post-bold trim if still huge (do not fail)
    if len(text.split()) > SUMMARY_HARD_MAX_WORDS:
        text = _trim_words(text, SUMMARY_HARD_MAX_WORDS)
        text = " ".join(text.split())
    return SummaryResult(summary=text)


def _clip_count(items: list[str], target: int, minimum: int = 1) -> list[str]:
    """Trim to target; keep whatever exists if short (no hard failure)."""
    items = [i for i in items if i.strip()]
    if len(items) >= target:
        return items[:target]
    return items  # allow short lists; validator only enforces a low minimum


def format_experience(exp: ExperienceRewrite) -> ExperienceRewrite:
    out: list[ExperienceEntryRewrite] = []
    for entry in exp.entries:
        bullets = [apply_bold(b) for b in entry.highlights if b.strip()]
        bullets = _clip_count(bullets, EXPERIENCE_BULLETS, minimum=1)
        out.append(ExperienceEntryRewrite(company=entry.company, highlights=bullets))
    return ExperienceRewrite(entries=out)


def format_projects(projects: ProjectsRewrite) -> ProjectsRewrite:
    out: list[ProjectRewriteEntry] = []
    for p in projects.projects:
        summary = apply_bold(p.summary) if p.summary else None
        highlights = [apply_bold(h) for h in p.highlights if h.strip()]
        highlights = _clip_count(highlights, PROJECT_HIGHLIGHTS, minimum=1)
        out.append(
            ProjectRewriteEntry(name=p.name, summary=summary, highlights=highlights)
        )
    return ProjectsRewrite(projects=out)
