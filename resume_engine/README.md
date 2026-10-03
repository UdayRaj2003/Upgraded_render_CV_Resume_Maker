# Resume Engine v2

Headless Python API that personalizes a master [RenderCV](https://github.com/rendercv/rendercv) YAML for a job description and renders a PDF. Built for LinkedIn-bot / ATS workflows.

The master resume (`Uday_Resume.yaml`) is **never modified**. Personalization runs on a temp copy; on failure the engine falls back to rendering the master.

## Quick start

```bash
# From repo root, with venv active and RenderCV installed
pip install -r resume_engine/requirements.txt

# Copy and fill AI credentials
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

```python
from resume_engine import generate_resume

result = generate_resume(job_text)
print(result.success, result.pdf_path, result.docx_path)
```

DOCX is built from the same RenderCV YAML as the PDF (classic theme: centered header,
section rules, two-column dates, bullets). Install `python-docx` (`pip install -r resume_engine/requirements.txt`).
Pandoc remains a fallback if YAML→DOCX fails. PDF is always produced.

Smoke test with a sample JD:

```bash
python scripts/test_prismhr_jd.py
```

## Pipeline (4 AI calls)

```text
JDParse (JSON)
    → ResumeSelection (JSON)   # projects + full skills
    → Summary (plain text)
    → Experience (tagged text)
    → Projects (tagged text)
    → normalize → format_ops → patch YAML → RenderCV PDF
```

| Stage | Output | Notes |
|-------|--------|--------|
| JDParse | Slim JSON | `role`, `mentioned_skills`, `keywords`, `responsibilities`, `jd_summary_focus` |
| ResumeSelection | JSON | Prefer project **ids** (`"1"`, `"2"`) or short names from catalog; full skills |
| Summary | Plain text | Role-focused single paragraph (no newlines), ≤4 soft lines; **never** sets `cv.headline` |
| Experience | `[[COMPANY]]` tags | Exactly 5 bullets per company after format |
| Projects | `[[PROJECT]]` tags | Exactly 4 highlights per project after format |

JSON is used only for control flow. Content stages use plain/tagged text (more reliable on weaker free models).

## Console progress

By default the console shows high-level progress (stages, timings, retries, summary). The log file under `logs/` stays detailed.

```text
=========================================================
Resume Engine v2
=========================================================

[1/5] JD Parsing...
✓ Completed (2.31s)
...
=========================================================
Resume Generation Summary
=========================================================
AI Calls:                 4
Result:                   SUCCESS
PDF:
output/.../Uday_Resume.pdf
```

Disable console output:

```python
generate_resume(job_text, console=False)
```

Or set `RESUME_ENGINE_CONSOLE=0` in `.env`.

Console never prints prompts, AI responses, intermediate JSON, or API keys.

## Configuration

### Environment (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `RESUME_ENGINE_API_BASE_URL` | yes | OpenAI-compatible base URL (e.g. OpenRouter) |
| `RESUME_ENGINE_MODEL_NAME` | yes | Model id |
| `RESUME_ENGINE_API_KEYS` | yes* | Comma/semicolon/newline-separated keys (same model) |
| `RESUME_ENGINE_API_KEY` | yes* | Legacy single key; merged with `API_KEYS` if unique |
| `RESUME_ENGINE_MAX_RETRIES` | no | Per-stage attempts (default `3`) |
| `RESUME_ENGINE_CONSOLE` | no | `1`/`0` console UI (default on) |
| `RESUME_ENGINE_OUTPUT_FILENAME` | no | PDF basename (default: master stem) |

\* At least one of `RESUME_ENGINE_API_KEYS` or `RESUME_ENGINE_API_KEY` is required.

Any OpenAI-compatible provider works. No provider is hardcoded.

**API key failover:** all keys share the same base URL and model. The client keeps a sticky key; on `429` / `401` / `403` / `5xx` / network errors it switches to the next key (`key 2/3` in logs/console — never prints the secret). With a single key, the old `2s → 5s → 10s` 429 backoff still applies.

### Engine config (`config/engine.yaml`)

```yaml
master_yaml: Uday_Resume.yaml
cleanup_temp_yaml: false
personalization:
  allow_new_keywords: true
  allow_new_bullets: false
  allow_metric_changes: false
  allow_new_technologies: false
sections:
  experience: Experience
  projects: Projects
  skills: Skills
  summary_title: Profile
  immutable:
    - Education
    - Achievements
    - Certifications
```

Immutable sections are never rewritten by the AI stages.

## API

```python
from pathlib import Path
from resume_engine import generate_resume, GenerateResult

result: GenerateResult = generate_resume(
    job_text,
    config_path=None,          # default: config/engine.yaml
    master_yaml=None,          # override master path
    output_dir=None,           # override output directory
    console=True,              # progress UI
)

result.success   # True if personalized; False if master fallback
result.pdf_path  # Path to generated PDF
```

### Retries and fallback

- Retries are **per-stage only** (a later failure does not re-run earlier stages).
- Multi-key: switch on rate limit / auth / server / network errors; sticky across stages.
- Single-key HTTP 429 backoff: **2s → 5s → 10s**.
- If personalization fails after retries, the master YAML is rendered and `success=False`.

### Outputs

| Path | Purpose |
|------|---------|
| `output/` | Rendered PDF runs |
| `output/temp/` | Working YAML copies (kept if `cleanup_temp_yaml: false`) |
| `logs/run_*.log` | Per-run detailed log (no prompts / secrets) |

## Layout

```text
resume_engine/
  api.py              # generate_resume()
  ai_client.py        # complete_json / complete_text
  console_ui.py       # user-facing progress
  models.py           # Pydantic schemas
  pipeline/stages.py  # AI stages
  text_parsers.py     # [[COMPANY]] / [[PROJECT]] parsers
  normalize.py        # light cleanup
  format_ops.py       # bullet counts, bold lexicon
  yaml_ops.py         # temp copy + patch (headline cleared)
  validate.py         # business rules + with_retries
  prompt_contract.py  # shared OUTPUT CONTRACT
config/engine.yaml
Uday_Resume.yaml      # master resume
scripts/test_prismhr_jd.py
tests_resume_engine/
```

## Tests

```bash
# Avoid upstream pytest-xdist addopts from the RenderCV suite
python -m pytest tests_resume_engine/test_engine.py -o addopts= -q
```

## Design rules

1. Master YAML is read-only (hash-checked each run).
2. ResumeSelection owns the full Skills section; the engine only validates/cleans/patches.
3. Project names must match the master list (never invented/renamed).
4. `cv.headline` is always cleared after personalization.
5. Education / Achievements / Certifications stay untouched.
