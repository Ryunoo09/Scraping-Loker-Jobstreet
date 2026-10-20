"""Test untuk :class:`SeenJobsDB` (dedup berbasis SQLite)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NoReturn

import pytest

from job_scraper.exceptions import StorageError
from job_scraper.models import Job
from job_scraper.storage import SeenJobsDB


@pytest.fixture
def db() -> Iterator[SeenJobsDB]:
    with SeenJobsDB(":memory:") as database:
        yield database


def test_new_job_is_not_seen(db: SeenJobsDB) -> None:
    assert db.has("123456") is False


def test_mark_then_has(db: SeenJobsDB, make_job: Callable[..., Job]) -> None:
    job = make_job()
    db.mark(job, status="matched")

    assert db.has(job.job_id) is True
    assert db.get_status(job.job_id) == "matched"


def test_reject_all_statuses_are_recorded(db: SeenJobsDB, make_job: Callable[..., Job]) -> None:
    job = make_job(job_id="999")
    db.mark(job, status="rejected_title")

    assert db.has("999") is True
    assert db.get_status("999") == "rejected_title"


def test_mark_updates_status_without_duplicating(
    db: SeenJobsDB, make_job: Callable[..., Job]
) -> None:
    job = make_job()
    db.mark(job, status="rejected_low_score")
    db.mark(job, status="matched")

    assert db.get_status(job.job_id) == "matched"


def test_reset_rejected_removes_only_rejected(db: SeenJobsDB, make_job: Callable[..., Job]) -> None:
    db.mark(make_job(job_id="keep"), status="matched")
    db.mark(make_job(job_id="drop1"), status="rejected_title")
    db.mark(make_job(job_id="drop2"), status="rejected_low_score")

    removed = db.reset_rejected()

    assert removed == 2
    assert db.has("keep") is True
    assert db.has("drop1") is False
    assert db.has("drop2") is False


def test_reset_rejected_with_nothing_to_remove(db: SeenJobsDB) -> None:
    assert db.reset_rejected() == 0


def test_file_database_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "seen_jobs.db"

    with SeenJobsDB(path) as database:
        assert database.has("anything") is False

    assert path.is_file()


def test_data_persists_across_connections(tmp_path: Path, make_job: Callable[..., Job]) -> None:
    path = tmp_path / "seen_jobs.db"
    job = make_job(job_id="persisted")

    with SeenJobsDB(path) as first:
        first.mark(job, status="matched")

    with SeenJobsDB(path) as second:
        assert second.has("persisted") is True
        assert second.get_status("persisted") == "matched"


def test_get_status_unknown_job_returns_none(db: SeenJobsDB) -> None:
    assert db.get_status("tidak-ada") is None


def test_mark_stores_posted_at(db: SeenJobsDB, make_job: Callable[..., Job]) -> None:
    job = make_job(posted_at="2026-10-13T02:58:53.000Z")

    db.mark(job, status="matched")

    assert db.get_posted_at(job.job_id) == "2026-10-13T02:58:53.000Z"


def test_get_posted_at_unknown_job_returns_none(db: SeenJobsDB) -> None:
    assert db.get_posted_at("tidak-ada") is None


def test_get_posted_at_without_value_returns_none(
    db: SeenJobsDB, make_job: Callable[..., Job]
) -> None:
    job = make_job()
    db.mark(job, status="matched")

    assert db.get_posted_at(job.job_id) is None


def test_mark_without_posted_at_keeps_existing_value(
    db: SeenJobsDB, make_job: Callable[..., Job]
) -> None:
    job = make_job(posted_at="2026-10-13T02:58:53.000Z")
    db.mark(job, status="matched")

    db.mark(job.model_copy(update={"posted_at": None}), status="matched")

    assert db.get_posted_at(job.job_id) == "2026-10-13T02:58:53.000Z"


def test_migration_adds_posted_at_to_old_database(tmp_path: Path) -> None:
    """DB skema lama (tanpa kolom posted_at) harus dibuka & dimigrasi otomatis."""
    path = tmp_path / "seen_jobs.db"
    old_schema = """
    CREATE TABLE seen_jobs (
        job_id      TEXT PRIMARY KEY,
        title       TEXT,
        company     TEXT,
        url         TEXT,
        status      TEXT NOT NULL,
        score       INTEGER,
        first_seen  TEXT NOT NULL
    );
    """
    connection = sqlite3.connect(path)
    connection.executescript(old_schema)
    connection.execute(
        "INSERT INTO seen_jobs (job_id, status, first_seen) VALUES ('lama', 'matched', 'x')"
    )
    connection.commit()
    connection.close()

    with SeenJobsDB(path) as database:
        columns = {
            str(row["name"])
            for row in database._conn.execute("PRAGMA table_info(seen_jobs)").fetchall()
        }
        assert "posted_at" in columns
        assert database.has("lama") is True  # data lama tidak hilang

    with SeenJobsDB(path) as database:  # migrasi kedua kali tidak error (idempoten)
        assert database.has("lama") is True


def test_operations_after_close_raise_storage_error(db: SeenJobsDB) -> None:
    db.close()

    with pytest.raises(StorageError):
        db.has("x")


def test_connect_failure_raises_storage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> NoReturn:
        raise sqlite3.OperationalError("tidak bisa connect")

    monkeypatch.setattr("job_scraper.storage.sqlite3.connect", boom)

    with pytest.raises(StorageError):
        SeenJobsDB(":memory:")
