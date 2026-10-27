"""Property-based test untuk komponen LinkedIn (hypothesis)."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from linkedin_scraper.config import (
    AppConfig,
    ExcelConfig,
    OutputConfig,
    ScoringConfig,
    SearchConfig,
)
from linkedin_scraper.filters import evaluate
from linkedin_scraper.models import JobLinkedIn
from linkedin_scraper.parsers import parse_search_page
from linkedin_scraper.utils import normalize_text

_CFG = AppConfig(
    search=SearchConfig(keywords=["x"]),
    scoring=ScoringConfig(
        min_score=0,
        title_keywords={"dev": 60},
        description_keywords={"python": 60},
    ),
    output=OutputConfig(type="excel", excel=ExcelConfig()),
)


@given(st.text())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_parse_search_page_returns_list_for_any_text(text: str) -> None:
    assert isinstance(parse_search_page(text), list)


@given(st.text())
@settings(max_examples=50, deadline=None)
def test_normalize_text_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once


@given(st.text(), st.text())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_score_is_always_between_zero_and_hundred(title: str, description: str) -> None:
    job = JobLinkedIn(
        job_id="1",
        title=title,
        company="",
        location="",
        url="",
        description=description,
    )
    result = evaluate(job, _CFG)
    assert 0 <= result.score <= 100
