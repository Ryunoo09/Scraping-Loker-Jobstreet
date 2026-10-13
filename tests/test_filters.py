"""Test untuk ``filters``: pra-filter, filter wajib, dan scoring."""

from __future__ import annotations

from collections.abc import Callable

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from job_scraper.config import AppConfig, FiltersConfig, ScoringConfig
from job_scraper.filters import evaluate, passes_prefilter
from job_scraper.models import Job

MakeJob = Callable[..., Job]
MakeConfig = Callable[..., AppConfig]


# --------------------------------------------------------------------------- #
# passes_prefilter
# --------------------------------------------------------------------------- #
def test_senior_title_is_rejected(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_title_keywords=["senior"]))
    assert passes_prefilter(make_job(title="Senior Backend Developer"), cfg.filters) is False


def test_lead_keyword_does_not_match_leader(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_title_keywords=["lead"]))
    assert passes_prefilter(make_job(title="Team Leader"), cfg.filters) is True


def test_lead_keyword_matches_whole_word(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_title_keywords=["lead"]))
    assert passes_prefilter(make_job(title="Lead Developer"), cfg.filters) is False


def test_phrase_title_keyword_matches(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_title_keywords=["head of"]))
    assert passes_prefilter(make_job(title="Head of Engineering"), cfg.filters) is False


def test_excluded_company_matches_partially(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_companies=["Acme"]))
    assert passes_prefilter(make_job(company="PT Acme Indonesia"), cfg.filters) is False


def test_normal_job_passes_prefilter(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_title_keywords=["senior"]))
    assert passes_prefilter(make_job(title="Junior Web Developer"), cfg.filters) is True


# --------------------------------------------------------------------------- #
# evaluate — filter wajib
# --------------------------------------------------------------------------- #
def test_excluded_description_phrase(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(exclude_description_keywords=["minimal 3 tahun"]))
    job = make_job(description="Dibutuhkan pengalaman minimal 3 tahun.")

    assert evaluate(job, cfg).reason == "desc_excluded"


def test_work_type_not_allowed_is_rejected(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(work_types=["magang"]))
    job = make_job(work_type="Full time")

    assert evaluate(job, cfg).reason == "work_type"


def test_work_type_allowed_passes(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(
        filters=FiltersConfig(work_types=["full time"]),
        scoring=ScoringConfig(min_score=0),
    )
    assert evaluate(make_job(work_type="Full time"), cfg).passed is True


def test_unknown_work_type_is_kept(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(
        filters=FiltersConfig(work_types=["magang"]),
        scoring=ScoringConfig(min_score=0),
    )
    assert evaluate(make_job(work_type=None), cfg).passed is True


def test_salary_below_minimum_is_rejected(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(filters=FiltersConfig(min_salary_idr=5_000_000))
    job = make_job(salary_min_idr=3_000_000)

    assert evaluate(job, cfg).reason == "salary_low"


def test_salary_above_minimum_passes(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(
        filters=FiltersConfig(min_salary_idr=5_000_000),
        scoring=ScoringConfig(min_score=0),
    )
    assert evaluate(make_job(salary_min_idr=7_000_000), cfg).passed is True


def test_unknown_salary_is_kept_by_default(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(
        filters=FiltersConfig(min_salary_idr=5_000_000),
        scoring=ScoringConfig(min_score=0),
    )
    assert evaluate(make_job(salary_min_idr=None), cfg).passed is True


def test_unknown_salary_rejected_when_configured(
    make_job: MakeJob, make_config: MakeConfig
) -> None:
    cfg = make_config(filters=FiltersConfig(min_salary_idr=5_000_000, keep_if_salary_unknown=False))
    assert evaluate(make_job(salary_min_idr=None), cfg).reason == "salary_unknown"


# --------------------------------------------------------------------------- #
# evaluate — scoring
# --------------------------------------------------------------------------- #
def test_fresh_graduate_scores_above_threshold(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(
        scoring=ScoringConfig(
            min_score=40,
            title_keywords={"developer": 25},
            description_keywords={"fresh graduate": 20},
            location_bonus={"Semarang": 10},
        )
    )
    job = make_job(
        title="Junior Web Developer",
        description="Fresh graduate welcome. Python, FastAPI.",
        location="Semarang",
    )

    result = evaluate(job, cfg)

    assert result.passed is True
    assert result.score >= cfg.scoring.min_score


def test_low_score_is_rejected(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(scoring=ScoringConfig(min_score=40, title_keywords={"developer": 25}))
    job = make_job(title="Backend Developer", description="")

    result = evaluate(job, cfg)

    assert result.passed is False
    assert result.reason == "low_score"
    assert result.score == 25


def test_score_is_capped_at_100(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(scoring=ScoringConfig(min_score=0, title_keywords={"developer": 200}))
    assert evaluate(make_job(title="Backend Developer"), cfg).score == 100


def test_location_bonus_is_applied(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(scoring=ScoringConfig(min_score=0, location_bonus={"Semarang": 10}))
    assert evaluate(make_job(location="Semarang, Jawa Tengah"), cfg).score == 10


def test_title_scoring_is_case_insensitive(make_job: MakeJob, make_config: MakeConfig) -> None:
    cfg = make_config(scoring=ScoringConfig(min_score=0, title_keywords={"developer": 10}))
    assert evaluate(make_job(title="BACKEND DEVELOPER"), cfg).score == 10


def test_description_scoring_is_case_insensitive(
    make_job: MakeJob, make_config: MakeConfig
) -> None:
    cfg = make_config(scoring=ScoringConfig(min_score=0, description_keywords={"python": 10}))
    assert evaluate(make_job(description="Butuh PYTHON dan SQL"), cfg).score == 10


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    title=st.text(max_size=80),
    description=st.text(max_size=200),
    location=st.text(max_size=80),
)
def test_score_is_always_between_0_and_100(
    make_job: MakeJob,
    make_config: MakeConfig,
    title: str,
    description: str,
    location: str,
) -> None:
    cfg = make_config(
        scoring=ScoringConfig(
            min_score=30,
            title_keywords={"dev": 40, "lead": 40},
            description_keywords={"python": 40},
            location_bonus={"jakarta": 40},
        )
    )
    job = make_job(title=title, description=description, location=location)

    result = evaluate(job, cfg)

    assert 0 <= result.score <= 100
