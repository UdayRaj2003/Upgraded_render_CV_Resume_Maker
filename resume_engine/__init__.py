"""Headless Resume Engine — personalize RenderCV YAML copies for a job description."""

from resume_engine.api import generate_resume
from resume_engine.models import GenerateResult

__all__ = ["generate_resume", "GenerateResult"]
