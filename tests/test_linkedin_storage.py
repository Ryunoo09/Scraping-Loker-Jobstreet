"""Test dedup SQLite LinkedIn."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from linkedin_scraper.exceptions import StorageError
from linkedin_scraper.models import JobLinkedIn
from linkedin_scraper.storage import SeenJobsDB


@pytest.fixture
def db() -> Iterator[SeenJobsDB]:
    with SeenJobsDB(":memory:") as database:
        yield database


def _job(**overrides: object) -> JobLinkedIn:
    data: dict[str, object] = {
        "job_id": "4446754033",
        "title": "Laravel Programmer",
        "company": "PT Contoh",
        "location": "Depok",
        "url": "https://www.linkedin.com/jobs/view/4446754033",
    }
    data.update(overrides)
    return JobLinkedIn.model_validate(data)


def test_new_job_is_not_seen(db: SeenJobsDB) -> None:
    assert db.has("4446754033") is False


def test_mark_then_has(db: SeenJobsDB) -> None:
    job = _job()
    db.mark(job, status="matched")
    assert db.has(job.job_id) is True
    assert db.get_status(job.job_id) == "matched"


def test_rejected_status_is_recorded(db: SeenJobsDB) -> None:
    db.mark(_job(job_id="999"), status="rejected_title")
    assert db.has("999") is True
    assert db.get_status("999") == "rejected_title"


def test_mark_updates_status_without_duplicating(db: SeenJobsDB) -> None:
    job = _job()
    db.mark(job, status="rejected_low_score")
    db.mark(job, status="matched")
    assert db.get_status(job.job_id) == "matched"


def test_reset_rejected_removes_only_rejected(db: SeenJobsDB) -> None:
    db.mark(_job(job_id="keep"), status="matched")
    db.mark(_job(job_id="drop1"), status="rejected_title")
    db.mark(_job(job_id="drop2"), status="rejected_low_score")

    assert db.reset_rejected() == 2
    assert db.has("keep") is True
    assert db.has("drop1") is False
    assert db.has("drop2") is False


def test_posted_at_survives_mark_without_it(db: SeenJobsDB) -> None:
    db.mark(_job(posted_at="2026-10-24"), status="matched")
    db.mark(_job(posted_at=None), status="matched")

    row = db._conn.execute(
        "SELECT posted_at FROM linkedin_seen_jobs WHERE job_id = ?", ("4446754033",)
    ).fetchone()
    assert row is not None
    assert row["posted_at"] == "2026-10-24"


def test_file_database_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "linkedin_seen.db"
    with SeenJobsDB(path) as db:
        db.mark(_job(), status="matched")
    with SeenJobsDB(path) as db:
        assert db.get_status("4446754033") == "matched"


def test_connect_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(target: str) -> None:
        raise sqlite3.OperationalError("nope")

    monkeypatch.setattr(sqlite3, "connect", boom)
    with pytest.raises(StorageError, match="Tidak bisa membuka"):
        SeenJobsDB(":memory:")


def test_operation_after_close_is_wrapped(db: SeenJobsDB) -> None:
    db.close()
    with pytest.raises(StorageError):
        db.has("x")
