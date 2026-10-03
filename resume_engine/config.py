"""Load engine.yaml and AI settings from environment variables only."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from ruamel.yaml import YAML

# Project root = parent of resume_engine/
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


@dataclass
class PersonalizationConfig:
    allow_new_keywords: bool = True
    allow_new_bullets: bool = False
    allow_metric_changes: bool = False
    allow_new_technologies: bool = False


@dataclass
class SectionsConfig:
    experience: str = "Experience"
    projects: str = "Projects"
    skills: str = "Skills"
    summary_title: str = "Profile"
    immutable: list[str] = field(
        default_factory=lambda: [
            "Education",
            "Achievements",
            "Certifications",
        ]
    )


@dataclass
class AIConfig:
    api_base_url: str
    api_keys: list[str]
    model_name: str
    max_retries: int = 3

    @property
    def api_key(self) -> str:
        """First configured key (compat for single-key callers)."""
        if not self.api_keys:
            raise ValueError("No API keys configured")
        return self.api_keys[0]


@dataclass
class EngineConfig:
    master_yaml: Path
    personalization: PersonalizationConfig
    sections: SectionsConfig
    ai: AIConfig
    cleanup_temp_yaml: bool = True
    output_filename: str = "Uday_Resume.pdf"
    logs_dir: Path = field(default_factory=lambda: ROOT / "logs")
    output_dir: Path = field(default_factory=lambda: ROOT / "output")
    temp_dir: Path = field(default_factory=lambda: ROOT / "output" / "temp")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_output_filename(master_yaml: Path) -> str:
    """Generated PDF basename from env, defaulting to master stem (.pdf)."""
    raw = os.getenv("RESUME_ENGINE_OUTPUT_FILENAME", "").strip()
    if not raw:
        return f"{master_yaml.stem}.pdf"
    name = Path(raw).name  # ignore any directory components
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name


def parse_api_keys(
    keys_raw: str | None = None,
    single_key: str | None = None,
) -> list[str]:
    """Build ordered unique API keys from API_KEYS list + legacy API_KEY."""
    if keys_raw is None:
        keys_raw = os.getenv("RESUME_ENGINE_API_KEYS", "")
    if single_key is None:
        single_key = os.getenv("RESUME_ENGINE_API_KEY", "")

    keys: list[str] = []
    seen: set[str] = set()

    for part in re_split_keys(keys_raw):
        if part not in seen:
            seen.add(part)
            keys.append(part)

    legacy = single_key.strip()
    if legacy and legacy not in seen:
        keys.append(legacy)

    if not keys:
        raise ValueError(
            "Missing API key: set RESUME_ENGINE_API_KEYS and/or RESUME_ENGINE_API_KEY"
        )
    return keys


def re_split_keys(raw: str) -> list[str]:
    parts = re.split(r"[,;\n]+", raw or "")
    return [p.strip() for p in parts if p.strip()]


def load_ai_config() -> AIConfig:
    retries_raw = os.getenv("RESUME_ENGINE_MAX_RETRIES", "3").strip()
    try:
        max_retries = max(1, int(retries_raw))
    except ValueError as exc:
        raise ValueError("RESUME_ENGINE_MAX_RETRIES must be an integer") from exc

    return AIConfig(
        api_base_url=_require_env("RESUME_ENGINE_API_BASE_URL").rstrip("/"),
        api_keys=parse_api_keys(),
        model_name=_require_env("RESUME_ENGINE_MODEL_NAME"),
        max_retries=max_retries,
    )


def load_engine_config(config_path: Path | None = None) -> EngineConfig:
    path = config_path or (ROOT / "config" / "engine.yaml")
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.load(fh) or {}

    master = Path(raw.get("master_yaml", "Uday_Resume.yaml"))
    if not master.is_absolute():
        master = ROOT / master

    pers_raw = raw.get("personalization") or {}
    personalization = PersonalizationConfig(
        allow_new_keywords=bool(pers_raw.get("allow_new_keywords", True)),
        allow_new_bullets=bool(pers_raw.get("allow_new_bullets", False)),
        allow_metric_changes=bool(pers_raw.get("allow_metric_changes", False)),
        allow_new_technologies=bool(pers_raw.get("allow_new_technologies", False)),
    )

    sec_raw = raw.get("sections") or {}
    sections = SectionsConfig(
        experience=str(sec_raw.get("experience", "Experience")),
        projects=str(sec_raw.get("projects", "Projects")),
        skills=str(sec_raw.get("skills", "Skills")),
        summary_title=str(sec_raw.get("summary_title", "Profile")),
        immutable=list(
            sec_raw.get(
                "immutable",
                [
                    "Education",
                    "Achievements",
                    "Certifications",
                ],
            )
        ),
    )

    return EngineConfig(
        master_yaml=master,
        personalization=personalization,
        sections=sections,
        ai=load_ai_config(),
        cleanup_temp_yaml=bool(raw.get("cleanup_temp_yaml", True)),
        output_filename=load_output_filename(master),
    )
