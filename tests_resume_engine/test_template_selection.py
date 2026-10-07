"""Unit tests for multi-template selection strategies and isolation rules."""

from __future__ import annotations

from pathlib import Path
import pytest

from resume_engine.templates import (
    BaseTemplateStrategy,
    DefaultTemplateStrategy,
    Template2Strategy,
    get_template_strategy,
)

ROOT = Path(__file__).resolve().parent.parent


def test_template_registry_resolution():
    """Verify registry resolves explicit names and paths correctly."""
    assert isinstance(get_template_strategy("template2"), Template2Strategy)
    assert isinstance(get_template_strategy("Template2_Resume.yaml"), Template2Strategy)
    assert isinstance(get_template_strategy("default"), DefaultTemplateStrategy)
    assert isinstance(get_template_strategy("classic"), DefaultTemplateStrategy)
    assert isinstance(get_template_strategy(None), DefaultTemplateStrategy)
    assert isinstance(get_template_strategy("Uday_Resume.yaml"), DefaultTemplateStrategy)


def test_global_master_default_is_preserved():
    """Verify global default master template remains Uday_Resume.yaml."""
    default_strat = get_template_strategy()
    assert default_strat.default_master_filename == "Uday_Resume.yaml"
    assert default_strat.get_master_yaml_path().name == "Uday_Resume.yaml"

    t2_strat = get_template_strategy("template2")
    assert t2_strat.default_master_filename == "Template2_Resume.yaml"
    assert t2_strat.get_master_yaml_path().name == "Template2_Resume.yaml"


def test_template2_blue_url_normalization():
    """Verify Template 2 post-processing normalizes raw URLs to [URL](URL) markdown links."""
    t2 = Template2Strategy()
    data = {
        "cv": {
            "sections": {
                "Experience": [
                    {
                        "company": "Dice Enterprises",
                        "highlights": [
                            "Experience Letter: https://drive.google.com/file/d/123/view",
                            "Already linked: [https://drive.google.com/file/d/456/](https://drive.google.com/file/d/456/)",
                        ],
                    }
                ],
                "Certifications": [
                    "HackerRank Certification — https://hackerrank.com/certificates/9119dec96173/"
                ],
            }
        }
    }

    processed = t2.post_process_data(data)
    exp_highlights = processed["cv"]["sections"]["Experience"][0]["highlights"]
    cert_items = processed["cv"]["sections"]["Certifications"]

    # Raw URL should be converted to markdown link syntax
    assert exp_highlights[0] == "Experience Letter: [https://drive.google.com/file/d/123/view](https://drive.google.com/file/d/123/view)"
    # Already formatted markdown link should not be double-wrapped
    assert exp_highlights[1] == "Already linked: [https://drive.google.com/file/d/456/](https://drive.google.com/file/d/456/)"
    # String-based list item should be converted
    assert cert_items[0] == "HackerRank Certification — [https://hackerrank.com/certificates/9119dec96173/](https://hackerrank.com/certificates/9119dec96173/)"


def test_default_strategy_does_not_modify_urls():
    """Verify DefaultTemplateStrategy does NOT apply Template 2 specific URL normalization."""
    default_strat = DefaultTemplateStrategy()
    data = {
        "cv": {
            "sections": {
                "Experience": [
                    {
                        "company": "Dice Enterprises",
                        "highlights": [
                            "Experience Letter: https://drive.google.com/file/d/123/view"
                        ],
                    }
                ]
            }
        }
    }

    processed = default_strat.post_process_data(data)
    # Default template leaves text untouched
    assert processed["cv"]["sections"]["Experience"][0]["highlights"][0] == "Experience Letter: https://drive.google.com/file/d/123/view"
