"""Test filter & scoring LinkedIn (fungsi murni)."""

from __future__ import annotations

from linkedin_scraper.config import (
    AppConfig,
    ExcelConfig,
    FiltersConfig,
    OutputConfig,
    ScoringConfig,
    SearchConfig,
)
from linkedin_scraper.filters import evaluate, passes_prefilter
from linkedin_scraper.models import JobLinkedIn


def _config(
    *, filters: FiltersConfig | None = None, scoring: ScoringConfig | None = None
) -> AppConfig:
    return AppConfig(
        search=SearchConfig(keywords=["Developer"]),
        filters=filters or FiltersConfig(),
        scoring=scoring or ScoringConfig(),
        output=OutputConfig(type="excel", excel=ExcelConfig()),
    )


def _job(**overrides: object) -> JobLinkedIn:
    data: dict[str, object] = {
        "job_id": "1",
        "title": "Junior Web Developer",
        "company": "PT Contoh",
        "location": "Jakarta",
        "url": "https://www.linkedin.com/jobs/view/1",
    }
    data.update(overrides)
    return JobLinkedIn.model_validate(data)


def test_senior_title_is_rejected() -> None:
    filters = FiltersConfig(exclude_title_keywords=["senior"])
    assert passes_prefilter(_job(title="Senior Developer"), filters) is False


def test_lead_does_not_match_leader() -> None:
    filters = FiltersConfig(exclude_title_keywords=["lead"])
    assert passes_prefilter(_job(title="Team Leader"), filters) is True


def test_lead_matches_whole_word() -> None:
    filters = FiltersConfig(exclude_title_keywords=["lead"])
    assert passes_prefilter(_job(title="Lead Developer"), filters) is False


def test_phrase_title_matches() -> None:
    filters = FiltersConfig(exclude_title_keywords=["head of"])
    assert passes_prefilter(_job(title="Head of Engineering"), filters) is False


def test_excluded_company_matches_partially() -> None:
    filters = FiltersConfig(exclude_companies=["Acme"])
    assert passes_prefilter(_job(company="PT Acme Indonesia"), filters) is False


def test_normal_job_passes_prefilter() -> None:
    filters = FiltersConfig(exclude_title_keywords=["senior"])
    assert passes_prefilter(_job(), filters) is True


def test_excluded_description_phrase() -> None:
    cfg = _config(filters=FiltersConfig(exclude_description_keywords=["minimal 3 tahun"]))
    job = _job(description="Dibutuhkan pengalaman minimal 3 tahun.")
    assert evaluate(job, cfg).reason == "desc_excluded"


def test_score_below_threshold_is_rejected() -> None:
    cfg = _config(
        scoring=ScoringConfig(min_score=50, title_keywords={"developer": 10}),
    )
    result = evaluate(_job(), cfg)
    assert result.passed is False
    assert result.reason == "low_score"
    assert result.score == 10


def test_score_passes_threshold() -> None:
    cfg = _config(scoring=ScoringConfig(min_score=10, title_keywords={"developer": 25}))
    result = evaluate(_job(), cfg)
    assert result.passed is True
    assert result.score == 25


def test_location_bonus_is_added() -> None:
    cfg = _config(
        scoring=ScoringConfig(
            min_score=0,
            title_keywords={"developer": 10},
            location_bonus={"jakarta": 5},
        )
    )
    assert evaluate(_job(), cfg).score == 15


def test_score_is_capped_at_100() -> None:
    cfg = _config(
        scoring=ScoringConfig(
            min_score=0,
            title_keywords={"developer": 80},
            description_keywords={"python": 80},
        )
    )
    assert evaluate(_job(description="Python"), cfg).score == 100
