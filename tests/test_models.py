"""Test untuk model domain ``Job`` dan ``EvalResult``."""

from __future__ import annotations

from collections.abc import Callable

from job_scraper.models import EvalResult, Job


def test_job_defaults(make_job: Callable[..., Job]) -> None:
    job = make_job()
    assert job.score == 0
    assert job.description is None
    assert job.salary_min_idr is None
    assert job.posted_at is None
    assert job.found_date  # terisi otomatis


def test_job_json_roundtrip_keeps_posted_at(make_job: Callable[..., Job]) -> None:
    job = make_job(posted_at="2026-10-13T02:58:53.000Z")
    restored = Job.model_validate_json(job.model_dump_json())
    assert restored.posted_at == "2026-10-13T02:58:53.000Z"


def test_job_strips_whitespace(make_job: Callable[..., Job]) -> None:
    job = make_job(title="  Backend Developer  ")
    assert job.title == "Backend Developer"


def test_job_json_roundtrip(make_job: Callable[..., Job]) -> None:
    job = make_job(description="Remote friendly", score=70)
    restored = Job.model_validate_json(job.model_dump_json())
    assert restored == job


def test_eval_result_defaults() -> None:
    result = EvalResult(passed=True)
    assert result.score == 0
    assert result.reason == ""
