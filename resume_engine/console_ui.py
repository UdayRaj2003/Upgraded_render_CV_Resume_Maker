"""User-facing console progress. Never prints prompts, AI text, JSON, or secrets."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            return True
        except Exception:  # noqa: BLE001
            return False
    return True


@dataclass
class RunStats:
    ai_calls: int = 0
    successful_calls: int = 0
    retries: int = 0
    parser_repairs: int = 0
    projects_selected: int = 0
    skills_categories: int = 0
    project_names: list[str] = field(default_factory=list)
    company_names: list[str] = field(default_factory=list)


class ConsoleUI:
    """High-level progress printer for generate_resume()."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.color = enabled and _supports_color()
        self._reset = "\033[0m" if self.color else ""
        self._green = "\033[32m" if self.color else ""
        self._yellow = "\033[33m" if self.color else ""
        self._red = "\033[31m" if self.color else ""
        self._cyan = "\033[36m" if self.color else ""
        self._bold = "\033[1m" if self.color else ""

    def _print(self, text: str = "") -> None:
        if self.enabled:
            try:
                print(text, flush=True)
            except UnicodeEncodeError:
                encoding = getattr(sys.stdout, "encoding", None) or "ascii"
                safe_text = text.encode(encoding, errors="replace").decode(encoding)
                print(safe_text, flush=True)

    def blank(self) -> None:
        self._print()

    def _ok(self, text: str) -> str:
        return f"{self._green}✓{self._reset} {text}"

    def _warn(self, text: str) -> str:
        return f"{self._yellow}⚠{self._reset} {text}"

    def _fail(self, text: str) -> str:
        return f"{self._red}✗{self._reset} {text}"

    def banner_start(self) -> None:
        line = "=" * 57
        self._print()
        self._print(f"{self._cyan}{line}{self._reset}")
        self._print(f"{self._bold}Resume Engine v2{self._reset}")
        self._print(f"{self._cyan}{line}{self._reset}")
        self._print()

    def stage_start(self, index: int, total: int, title: str) -> None:
        self._print(f"{self._bold}[{index}/{total}] {title}...{self._reset}")

    def stage_completed(self, elapsed_s: float) -> None:
        self._print(self._ok(f"Completed ({elapsed_s:.2f}s)"))
        self._print()

    def item_ok(self, text: str) -> None:
        self._print(self._ok(text))

    def bullet(self, text: str) -> None:
        self._print(f"  • {text}")

    def warn(self, text: str) -> None:
        self._print(self._warn(text))

    def retry(self, attempt: int, max_attempts: int) -> None:
        self._print(f"{self._yellow}Retry {attempt}/{max_attempts}...{self._reset}")

    def parser_repaired(self) -> None:
        self._print(self._warn("Parsed with minor formatting fixes"))
        self._print(self._ok("Continued"))

    def stage_failed(self, max_attempts: int, reasons: list[str]) -> None:
        self._print(self._fail(f"Failed after {max_attempts} retries"))
        if reasons:
            self._print("Reason:")
            for reason in reasons:
                self._print(f"- {reason}")
        self._print()

    def formatting_start(self) -> None:
        self._print(f"{self._bold}Formatting Resume...{self._reset}")

    def rendering_start(self) -> None:
        self._print(f"{self._bold}Rendering PDF...{self._reset}")

    def fallback_start(self) -> None:
        self._print(f"{self._yellow}Using master resume fallback...{self._reset}")
        self._print()
        self._print(f"{self._bold}Rendering master resume...{self._reset}")

    def total_time(self, elapsed_s: float) -> None:
        self._print(f"Total Time: {elapsed_s:.2f}s")
        self._print()

    def _print_output_paths(
        self, pdf_path: str | Path, docx_path: str | Path | None = None
    ) -> None:
        self._print("Output:")
        self._print(str(pdf_path))
        if docx_path is not None:
            self._print(str(docx_path))

    def banner_success(
        self, pdf_path: str | Path, *, docx_path: str | Path | None = None
    ) -> None:
        line = "=" * 57
        self._print(f"{self._green}{line}{self._reset}")
        self._print(f"{self._green}{self._bold}Resume Generation Successful{self._reset}")
        self._print_output_paths(pdf_path, docx_path)
        self._print(f"{self._green}{line}{self._reset}")
        self._print()

    def banner_fallback(
        self, pdf_path: str | Path, *, docx_path: str | Path | None = None
    ) -> None:
        line = "=" * 57
        self._print(f"{self._yellow}{line}{self._reset}")
        self._print(f"{self._yellow}{self._bold}Fallback Resume Generated{self._reset}")
        self._print_output_paths(pdf_path, docx_path)
        self._print(f"{self._yellow}{line}{self._reset}")
        self._print()

    def banner_error(self) -> None:
        line = "=" * 57
        self._print(f"{self._red}{line}{self._reset}")
        self._print(f"{self._red}{self._bold}Resume Generation Failed{self._reset}")
        self._print(f"{self._red}{line}{self._reset}")
        self._print()

    def summary(
        self,
        stats: RunStats,
        *,
        elapsed_s: float,
        success: bool,
        pdf_path: str | Path,
        docx_path: str | Path | None = None,
    ) -> None:
        line = "=" * 57
        result = "SUCCESS" if success else "FALLBACK"
        result_color = self._green if success else self._yellow
        self._print(f"{self._cyan}{line}{self._reset}")
        self._print(f"{self._bold}Resume Generation Summary{self._reset}")
        self._print(f"{self._cyan}{line}{self._reset}")
        self._print()
        self._print(f"{'AI Calls:':<25}{stats.ai_calls}")
        self._print(f"{'Successful Calls:':<25}{stats.successful_calls}")
        self._print(f"{'Retries:':<25}{stats.retries}")
        self._print(f"{'Parser Repairs:':<25}{stats.parser_repairs}")
        self._print(f"{'Projects Selected:':<25}{stats.projects_selected}")
        self._print(f"{'Skills Categories:':<25}{stats.skills_categories}")
        self._print(f"{'Generation Time:':<25}{elapsed_s:.2f}s")
        self._print(f"{'Result:':<25}{result_color}{result}{self._reset}")
        self._print()
        self._print("PDF:")
        self._print(str(pdf_path))
        if docx_path is not None:
            self._print("DOCX:")
            self._print(str(docx_path))
        self._print(f"{self._cyan}{line}{self._reset}")
        self._print()


def friendly_failure_reasons(exc: BaseException) -> list[str]:
    """Map exceptions to short user-facing bullets (no prompts/JSON dumps)."""
    msg = str(exc).strip()
    lower = msg.lower()
    reasons: list[str] = []

    if "429" in msg or "too many requests" in lower:
        reasons.append("Rate limited by AI provider")
    if "json" in lower or "schema validation" in lower:
        reasons.append("Invalid JSON received")
    if "[[company]]" in lower or "company blocks" in lower or "no [[company]]" in lower:
        reasons.append("Missing company blocks")
    if "company tag" in lower or "missing company name" in lower:
        reasons.append("Missing COMPANY tag")
    if "[[project]]" in lower or "project blocks" in lower or "no [[project]]" in lower:
        reasons.append("Missing project blocks")
    if "project tag" in lower or "missing project name" in lower:
        reasons.append("Missing PROJECT tag")
    if "parseerror" in type(exc).__name__.lower() or (
        "tagged" in lower or ("parse" in lower and "json" not in lower)
    ):
        if "Invalid tagged format" not in reasons:
            reasons.append("Invalid tagged format")
    if "unknown project" in lower:
        reasons.append("Unknown project name")
    if "unknown company" in lower:
        reasons.append("Unknown company name")
    if "selected_projects" in lower or "exactly 2" in lower:
        reasons.append("Invalid project selection")
    if "skills" in lower and ("empty" in lower or "label" in lower):
        reasons.append("Invalid skills section")
    if "summary" in lower and ("range" in lower or "lines" in lower or "empty" in lower):
        reasons.append("Summary length/format invalid")
    if "exactly" in lower and "bullet" in lower:
        reasons.append("Incorrect bullet count")
    if "metric" in lower:
        reasons.append("Metric changes not allowed")
    if "http" in lower or "connection" in lower or "timeout" in lower:
        reasons.append("AI request failed")

    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            out.append(reason)

    if not out:
        compact = msg.replace("\n", " ").strip()
        if len(compact) > 100:
            compact = compact[:97] + "..."
        out.append(compact or "Unknown error")
    return out[:5]
