"""Fixture bersama untuk seluruh test."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from job_scraper.config import (
    AppConfig,
    ExcelConfig,
    FiltersConfig,
    OutputConfig,
    ScoringConfig,
    ScraperConfig,
    SearchConfig,
    load_config,
)
from job_scraper.models import Job

VALID_CONFIG_TEXT = """\
search:
  keywords:
    - "Backend Developer"
  locations:
    - "Semarang"
filters: {}
scoring:
  min_score: 40
output:
  type: "excel"
  excel:
    file_path: "data/jobs_local.xlsx"
scraper:
  delay_min_sec: 1
  delay_max_sec: 2
"""


@pytest.fixture
def valid_config_text() -> str:
    """YAML config yang valid untuk dipakai/dimodifikasi test."""
    return VALID_CONFIG_TEXT


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[[str], Path]:
    """Kembalikan fungsi penulis config ke file sementara."""

    def _write(text: str, name: str = "config.yaml") -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def cfg(write_config: Callable[[str], Path], valid_config_text: str) -> AppConfig:
    """AppConfig tervalidasi dari config minimal yang valid."""
    return load_config(write_config(valid_config_text))


@pytest.fixture
def make_job() -> Callable[..., Job]:
    """Factory pembuat Job dengan nilai default, mudah di-override."""

    def _make(**overrides: object) -> Job:
        data: dict[str, object] = {
            "job_id": "123456",
            "title": "Backend Developer",
            "company": "PT Contoh",
            "location": "Semarang",
            "url": "https://id.jobstreet.com/job/123456",
        }
        data.update(overrides)
        return Job.model_validate(data)

    return _make


@pytest.fixture
def make_config() -> Callable[..., AppConfig]:
    """Factory :class:`AppConfig` dengan nilai default wajar, mudah di-override."""

    def _make(
        *,
        filters: FiltersConfig | None = None,
        scoring: ScoringConfig | None = None,
        output: OutputConfig | None = None,
    ) -> AppConfig:
        return AppConfig(
            search=SearchConfig(keywords=["developer"], locations=["Semarang"]),
            filters=filters if filters is not None else FiltersConfig(),
            scoring=scoring if scoring is not None else ScoringConfig(),
            output=(
                output if output is not None else OutputConfig(type="excel", excel=ExcelConfig())
            ),
            scraper=ScraperConfig(),
        )

    return _make
