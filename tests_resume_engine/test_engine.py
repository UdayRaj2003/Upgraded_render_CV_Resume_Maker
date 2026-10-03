"""Smoke tests for resume_engine v2 validators, parsers, YAML patching, fallback."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from resume_engine.config import PersonalizationConfig, SectionsConfig  # noqa: E402
from resume_engine.format_ops import apply_bold  # noqa: E402
from resume_engine.models import (  # noqa: E402
    ExperienceEntryRewrite,
    ExperienceRewrite,
    ProjectRewriteEntry,
    ProjectsRewrite,
    ResumeSelection,
    SkillCategory,
    SkillsResult,
    SummaryResult,
)
from resume_engine.normalize import clean_skills, normalize_summary  # noqa: E402
from resume_engine.text_parsers import (  # noqa: E402
    ParseError,
    parse_experience_tagged,
    parse_projects_tagged,
)
from resume_engine.validate import (  # noqa: E402
    ValidationError,
    validate_selection,
    validate_skills,
    validate_summary,
)
from resume_engine.yaml_ops import (  # noqa: E402
    apply_personalization,
    clean_project_label,
    create_temp_copy,
    file_sha256,
    get_sections,
    inventory_from_master,
    load_master_readonly,
    match_project_name,
    write_yaml,
)

MASTER = ROOT / "Uday_Resume.yaml"


def test_master_exists():
    assert MASTER.is_file()


def test_clean_and_match_project_name():
    names = ["[FlashInfer](https://github.com/)", "[NeuralPrune](https://github.com/)"]
    assert match_project_name("FlashInfer", names) == names[0]
    assert clean_project_label(names[0]) == "FlashInfer"
    # Bracket-only AI mistake
    assert match_project_name("[FlashInfer]", names) == names[0]
    # Catalog id
    assert match_project_name("1", names) == names[0]
    assert match_project_name("2", names) == names[1]


def test_validate_selection_rejects_unknown_project():
    selection = ResumeSelection(
        selected_projects=["DoesNotExist", "AlsoFake"],
        skills=[SkillCategory(label="Languages", details="Python")],
    )
    with pytest.raises(ValidationError):
        validate_selection(selection, ["[FlashInfer](https://github.com/)"])


def test_validate_selection_accepts_ids_and_brackets():
    names = ["[FlashInfer](https://github.com/)", "[NeuralPrune](https://github.com/)"]
    selection = ResumeSelection(
        selected_projects=["1", "[NeuralPrune]"],
        skills=[SkillCategory(label="Languages", details="Python, TypeScript")],
    )
    validate_selection(selection, names)
    assert selection.selected_projects == ["FlashInfer", "NeuralPrune"]


def test_validate_selection_accepts_clean_names():
    names = ["[FlashInfer](https://github.com/)", "[NeuralPrune](https://github.com/)"]
    selection = ResumeSelection(
        selected_projects=["FlashInfer", "NeuralPrune"],
        skills=[SkillCategory(label="Languages", details="Python, TypeScript")],
    )
    validate_selection(selection, names)


def test_clean_skills_dedupes():
    result = clean_skills(
        [
            SkillCategory(label="Languages", details="Python, python, TypeScript"),
            SkillCategory(label="Languages", details="Rust"),
            SkillCategory(label="Web", details="React"),
            SkillCategory(label="", details="x"),
        ]
    )
    assert len(result.skills) == 2
    assert result.skills[0].details == "Python, TypeScript"


def test_validate_skills_and_summary():
    validate_skills(
        SkillsResult(skills=[SkillCategory(label="Languages", details="Python")])
    )
    with pytest.raises(ValidationError):
        validate_skills(SkillsResult(skills=[]))

    ok = SummaryResult(
        summary=(
            "Backend engineer focused on scalable APIs, data systems, and reliable services. "
            "Experienced with Node.js, MongoDB, and cloud deployments across product teams. "
            "Strong interest in FinTech reliability, developer experience, and maintainable code. "
            "Comfortable owning services from design through production support."
        )
    )
    validate_summary(ok)

    with pytest.raises(ValidationError):
        validate_summary(SummaryResult(summary="Too short."))


def test_parse_experience_case_insensitive():
    text = """
[[company]]
Dice Enterprises
- Built APIs
- Shipped features
- Improved latency
- Mentored juniors
- Owned releases

[[COMPANY]]
Acme Corp
- Did A
- Did B
- Did C
- Did D
- Did E
"""
    parsed = parse_experience_tagged(text)
    assert isinstance(parsed.value, ExperienceRewrite)
    assert len(parsed.value.entries) == 2
    assert parsed.value.entries[0].company == "Dice Enterprises"
    assert len(parsed.value.entries[0].highlights) == 5


def test_parse_projects_tagged():
    text = """
[[project]]
StudyNotion
SUMMARY:
EdTech platform
HIGHLIGHTS:
- One
- Two
- Three
- Four
"""
    parsed = parse_projects_tagged(text)
    assert isinstance(parsed.value, ProjectsRewrite)
    assert len(parsed.value.projects) == 1
    assert parsed.value.projects[0].name == "StudyNotion"
    assert parsed.value.projects[0].summary == "EdTech platform"
    assert len(parsed.value.projects[0].highlights) == 4


def test_parse_experience_auto_repairs_loose_tags():
    text = """
[COMPANY]
Dice Enterprises
Built APIs without a dash
Shipped features without a dash
Improved latency
Mentored juniors
Owned releases
"""
    parsed = parse_experience_tagged(text)
    assert parsed.repairs
    assert len(parsed.value.entries) == 1
    assert len(parsed.value.entries[0].highlights) == 5


def test_parse_experience_missing_tag_raises():
    with pytest.raises(ParseError):
        parse_experience_tagged("no tags here\n- bullet")


def test_normalize_summary_strips_first_person():
    text = normalize_summary("I built APIs and I've shipped products for my team.")
    assert "I " not in text
    assert "I've" not in text.lower() or "ive" not in text.lower()
    assert "my" not in text.lower().split()


def test_bold_longest_first():
    out = apply_bold("Built Node.js and React.js services with Node helpers")
    assert "**Node.js**" in out
    assert "**React.js**" in out
    # Should not produce nested **Node**.**js**
    assert "**Node**.**js**" not in out


def test_yaml_patch_never_sets_headline(tmp_path: Path):
    before = file_sha256(MASTER)
    data = load_master_readonly(MASTER)
    inv = inventory_from_master(data, SectionsConfig())

    from resume_engine.config import AIConfig, EngineConfig

    cfg = EngineConfig(
        master_yaml=MASTER,
        personalization=PersonalizationConfig(),
        sections=SectionsConfig(),
        ai=AIConfig(api_base_url="http://x", api_keys=["k"], model_name="m"),
    )
    # Ensure master starts without headline text (or clear it)
    if isinstance(data.get("cv"), dict):
        data["cv"]["headline"] = "Should be cleared"

    skills = SkillsResult(
        skills=[SkillCategory(label="Languages", details="Python, Rust")]
    )
    summary = SummaryResult(
        summary=(
            "Engineer with experience building ML systems and production infrastructure.\n"
            "Focused on efficient inference, scalable APIs, and reliable cloud services.\n"
            "Comfortable collaborating across research, platform, and product engineering teams."
        )
    )
    experience = ExperienceRewrite(
        entries=[
            ExperienceEntryRewrite(
                company=c,
                highlights=[f"Bullet {i}" for i in range(1, 6)],
            )
            for c in inv["companies"]
        ]
    )
    projects = ProjectsRewrite(
        projects=[
            ProjectRewriteEntry(
                name=inv["project_names"][0],
                summary="Relevant project",
                highlights=[f"H{i}" for i in range(1, 5)],
            ),
            ProjectRewriteEntry(
                name=inv["project_names"][1],
                summary="Second project",
                highlights=[f"H{i}" for i in range(1, 5)],
            ),
        ]
    )
    personalized = apply_personalization(
        data,
        cfg=cfg,
        skills=skills,
        summary=summary,
        experience=experience,
        projects=projects,
    )
    assert personalized["cv"].get("headline") is None
    sections = get_sections(personalized)
    profile = sections[cfg.sections.summary_title]
    assert isinstance(profile, list) and len(profile) == 1
    assert "bullet" in profile[0]
    assert "\n" not in profile[0]["bullet"]

    temp = create_temp_copy(MASTER, tmp_path)
    write_yaml(temp, personalized)
    after = file_sha256(MASTER)
    assert before == after
    assert hashlib.sha256(temp.read_bytes()).hexdigest() != before


def test_parse_api_keys_from_env():
    from resume_engine.config import parse_api_keys

    keys = parse_api_keys(
        keys_raw="sk-a, sk-b;sk-c\nsk-a",
        single_key="sk-d",
    )
    assert keys == ["sk-a", "sk-b", "sk-c", "sk-d"]

    legacy_only = parse_api_keys(keys_raw="", single_key="only")
    assert legacy_only == ["only"]

    with pytest.raises(ValueError):
        parse_api_keys(keys_raw="  ", single_key="")


def test_ai_client_switches_key_on_429():
    from resume_engine.ai_client import AIClient, AIClientError
    from resume_engine.config import AIConfig

    switches: list[str] = []
    cfg = AIConfig(
        api_base_url="https://example.com/v1",
        api_keys=["secret-key-one", "secret-key-two"],
        model_name="test-model",
    )
    client = AIClient(cfg, on_key_switch=switches.append)

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.headers: dict[str, str] = {}
            self.request = object()

        def json(self) -> dict:
            return self._payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError(
                    "error",
                    request=self.request,  # type: ignore[arg-type]
                    response=self,  # type: ignore[arg-type]
                )

    calls: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            auth = (headers or {}).get("Authorization", "")
            calls.append(auth)
            if "secret-key-one" in auth:
                return FakeResponse(429)
            return FakeResponse(
                200,
                {
                    "choices": [{"message": {"content": "ok summary text"}}],
                    "usage": {"total_tokens": 3},
                },
            )

    with patch("resume_engine.ai_client.httpx.Client", FakeClient):
        with patch("resume_engine.ai_client.time.sleep", return_value=None):
            text = client.complete_text(system="s", user="u")

    assert text == "ok summary text"
    assert client.active_key_index == 1
    assert client.last_key_label == "2/2"
    assert len(calls) == 2
    assert any("switching to key 2/2" in m for m in switches)
    joined = " ".join(switches)
    assert "secret-key-one" not in joined
    assert "secret-key-two" not in joined


def test_ai_client_all_keys_fail():
    from resume_engine.ai_client import AIClient, AIClientError
    from resume_engine.config import AIConfig

    cfg = AIConfig(
        api_base_url="https://example.com/v1",
        api_keys=["k1", "k2"],
        model_name="test-model",
    )
    client = AIClient(cfg)

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = 429
            self.headers: dict[str, str] = {}
            self.request = object()

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            return FakeResponse()

    with patch("resume_engine.ai_client.httpx.Client", FakeClient):
        with patch("resume_engine.ai_client.time.sleep", return_value=None):
            with pytest.raises(AIClientError):
                client.complete_text(system="s", user="u")


def test_ai_client_single_key_retries_429():
    from resume_engine.ai_client import AIClient
    from resume_engine.config import AIConfig

    cfg = AIConfig(
        api_base_url="https://example.com/v1",
        api_keys=["only-key"],
        model_name="test-model",
    )
    client = AIClient(cfg)
    attempts = {"n": 0}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict | None = None) -> None:
            self.status_code = status_code
            self._payload = payload or {}
            self.headers: dict[str, str] = {}
            self.request = object()

        def json(self) -> dict:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            attempts["n"] += 1
            if attempts["n"] < 2:
                return FakeResponse(429)
            return FakeResponse(
                200,
                {"choices": [{"message": {"content": "recovered"}}]},
            )

    sleeps: list[float] = []

    with patch("resume_engine.ai_client.httpx.Client", FakeClient):
        with patch(
            "resume_engine.ai_client.time.sleep",
            side_effect=lambda s: sleeps.append(s),
        ):
            text = client.complete_text(system="s", user="u")

    assert text == "recovered"
    assert attempts["n"] == 2
    assert sleeps  # backoff used on single-key 429


def test_fallback_when_ai_fails(tmp_path: Path):
    os.environ["RESUME_ENGINE_API_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["RESUME_ENGINE_API_KEY"] = "test-key"
    os.environ.pop("RESUME_ENGINE_API_KEYS", None)
    os.environ["RESUME_ENGINE_MODEL_NAME"] = "test-model"
    os.environ["RESUME_ENGINE_MAX_RETRIES"] = "1"

    before = file_sha256(MASTER)
    from resume_engine.api import generate_resume

    out = tmp_path / "output"
    logs = tmp_path / "logs"
    with patch("resume_engine.api.load_engine_config") as load_cfg:
        from resume_engine.config import EngineConfig, load_ai_config

        cfg = EngineConfig(
            master_yaml=MASTER,
            personalization=PersonalizationConfig(),
            sections=SectionsConfig(),
            ai=load_ai_config(),
            logs_dir=logs,
            output_dir=out,
            temp_dir=out / "temp",
        )
        load_cfg.return_value = cfg
        result = generate_resume(
            "Backend engineer with Node.js and MongoDB experience.",
            console=False,
        )

    assert result.success is False
    assert result.pdf_path is not None
    assert Path(result.pdf_path).is_file()
    pdf = Path(result.pdf_path)
    assert list(pdf.parent.glob("*.md")), "RenderCV markdown should be generated"
    if result.docx_path is not None:
        import zipfile

        docx = Path(result.docx_path)
        assert docx.is_file()
        with zipfile.ZipFile(docx, "r") as zf:
            assert any(name.startswith("word/") for name in zf.namelist())
    assert file_sha256(MASTER) == before
    log_files = list(logs.glob("run_*.log"))
    assert len(log_files) == 1
    text = log_files[0].read_text(encoding="utf-8")
    assert "Fallback" in text
    assert "JOB DESCRIPTION" not in text


def test_classic_docx_matches_yaml_structure(tmp_path: Path):
    import zipfile

    from resume_engine.docx_classic import render_yaml_to_docx

    out = tmp_path / "Uday_Resume.docx"
    path = render_yaml_to_docx(MASTER, out)
    assert path is not None
    assert path.is_file()
    with zipfile.ZipFile(path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Uday Raj Gupta" in xml
    assert "PROFESSIONAL SUMMARY" in xml
    assert "Dice Enterprises" in xml
    assert "Java Ping Relay Server" in xml
    assert "w:tbl" not in xml
    assert "w:smallCaps" not in xml

    from resume_engine.docx_classic import render_yaml_to_pdf_ats

    pdf = tmp_path / "Uday_Resume.pdf"
    pdf_path = render_yaml_to_pdf_ats(MASTER, pdf)
    assert pdf_path is not None
    raw = pdf_path.read_bytes()
    assert raw[:5] == b"%PDF-"
    assert pdf_path.stat().st_size > 1000


def test_pandoc_missing_skips_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from resume_engine.render import _convert_markdown_to_docx

    monkeypatch.setattr("resume_engine.render.shutil.which", lambda _name: None)
    md = tmp_path / "Uday_Resume.md"
    md.write_text("# Resume\n", encoding="utf-8")
    assert _convert_markdown_to_docx(md, tmp_path / "Uday_Resume.docx") is None
