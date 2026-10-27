"""Test config LinkedIn: validasi, default, dan penolakan key salah."""

from __future__ import annotations

from pathlib import Path

import pytest

from linkedin_scraper.config import load_config
from linkedin_scraper.exceptions import ConfigError

EXAMPLE = Path(__file__).resolve().parent.parent / "config_linkedin.example.yaml"

_BASE = """
search:
  keywords: ["Developer"]
  location: "Indonesia"
output:
  type: "excel"
  excel:
    file_path: "data/linkedin_jobs.xlsx"
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_config_is_valid() -> None:
    cfg = load_config(EXAMPLE)
    assert cfg.search.location == "Indonesia"
    assert cfg.output.type == "excel"
    assert cfg.scraper.max_retries >= 0


def test_defaults_are_applied(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, _BASE))
    assert cfg.search.max_pages_per_query == 2
    assert cfg.search.fetch_detail is True
    assert cfg.filters.exclude_title_keywords == []


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="tidak ditemukan"):
        load_config(tmp_path / "absent.yaml")


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="ihwal"):
        load_config(_write(tmp_path, _BASE + "ihwal: 1\n"))


def test_empty_keywords_are_rejected(tmp_path: Path) -> None:
    text = _BASE.replace('["Developer"]', "[]")
    with pytest.raises(ConfigError, match="minimal satu nilai"):
        load_config(_write(tmp_path, text))


def test_delay_order_is_validated(tmp_path: Path) -> None:
    text = _BASE + "scraper:\n  delay_min_sec: 10\n  delay_max_sec: 5\n"
    with pytest.raises(ConfigError, match="delay_min_sec"):
        load_config(_write(tmp_path, text))


def test_google_sheets_requires_real_id(tmp_path: Path) -> None:
    text = _BASE.replace(
        'output:\n  type: "excel"',
        'output:\n  type: "google_sheets"\n  google_sheets:\n    spreadsheet_id: "ISI_ID"',
    )
    with pytest.raises(ConfigError, match="placeholder"):
        load_config(_write(tmp_path, text))


def test_google_sheets_accepts_real_id(tmp_path: Path) -> None:
    text = _BASE.replace(
        'output:\n  type: "excel"',
        'output:\n  type: "google_sheets"\n  google_sheets:\n    spreadsheet_id: "abc123"',
    )
    cfg = load_config(_write(tmp_path, text))
    assert cfg.output.google_sheets is not None
    assert cfg.output.google_sheets.spreadsheet_id == "abc123"
