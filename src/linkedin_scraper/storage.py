"""Penyimpanan lokal (SQLite) untuk dedup lowongan LinkedIn."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .exceptions import StorageError
from .models import JobLinkedIn

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS linkedin_seen_jobs (
    job_id      TEXT PRIMARY KEY,
    title       TEXT,
    company     TEXT,
    url         TEXT,
    status      TEXT NOT NULL,
    score       INTEGER,
    posted_at   TEXT,
    first_seen  TEXT NOT NULL
);
"""

#: Kolom yang ditambahkan setelah rilis awal; dipakai untuk migrasi DB lama.
_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (("posted_at", "TEXT"),)

_MEMORY = ":memory:"


class SeenJobsDB:
    """Ingatan proyek: setiap lowongan LinkedIn yang pernah dilihat dicatat sekali."""

    def __init__(self, path: Path | str) -> None:
        target = str(path)
        if target != _MEMORY:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(target)
        except sqlite3.Error as exc:
            raise StorageError(f"Tidak bisa membuka database {target}: {exc}") from exc
        self._conn.row_factory = sqlite3.Row
        with self._guard():
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.execute("PRAGMA journal_mode=WAL")

    def __enter__(self) -> SeenJobsDB:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @contextmanager
    def _guard(self) -> Iterator[None]:
        """Terjemahkan error SQLite menjadi :class:`StorageError`."""
        try:
            yield
        except sqlite3.Error as exc:
            raise StorageError(f"Operasi SQLite gagal: {exc}") from exc

    def _migrate(self) -> None:
        """Tambahkan kolom baru ke database lama tanpa menghapus data."""
        columns = {
            str(row["name"]) for row in self._conn.execute("PRAGMA table_info(linkedin_seen_jobs)")
        }
        for column, column_type in _ADDED_COLUMNS:
            if column in columns:
                continue
            self._conn.execute(f"ALTER TABLE linkedin_seen_jobs ADD COLUMN {column} {column_type}")
            logger.info("Migrasi DB: menambah kolom linkedin_seen_jobs.%s", column)

    def has(self, job_id: str) -> bool:
        """Kembalikan ``True`` bila ``job_id`` sudah pernah dilihat."""
        with self._guard():
            row = self._conn.execute(
                "SELECT 1 FROM linkedin_seen_jobs WHERE job_id = ? LIMIT 1", (job_id,)
            ).fetchone()
        return row is not None

    def get_status(self, job_id: str) -> str | None:
        """Kembalikan status tersimpan untuk ``job_id``, atau ``None``."""
        with self._guard():
            row = self._conn.execute(
                "SELECT status FROM linkedin_seen_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return None if row is None else str(row["status"])

    def mark(self, job: JobLinkedIn, status: str) -> None:
        """Catat lowongan beserta statusnya (idempoten per ``job_id``)."""
        first_seen = datetime.now(UTC).isoformat()
        with self._guard(), self._conn:
            self._conn.execute(
                """
                INSERT INTO linkedin_seen_jobs
                    (job_id, title, company, url, status, score, posted_at, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status    = excluded.status,
                    score     = excluded.score,
                    posted_at = COALESCE(excluded.posted_at, linkedin_seen_jobs.posted_at)
                """,
                (
                    job.job_id,
                    job.title,
                    job.company,
                    job.url,
                    status,
                    job.score,
                    job.posted_at,
                    first_seen,
                ),
            )

    def reset_rejected(self) -> int:
        """Hapus semua baris berstatus ``rejected_*``; kembalikan jumlahnya."""
        with self._guard(), self._conn:
            cursor = self._conn.execute(
                "DELETE FROM linkedin_seen_jobs WHERE status LIKE 'rejected_%'"
            )
        return int(cursor.rowcount)

    def close(self) -> None:
        """Tutup koneksi database."""
        with self._guard():
            self._conn.close()
