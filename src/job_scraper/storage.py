"""Penyimpanan lokal (SQLite) untuk dedup lowongan yang sudah pernah dilihat."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .exceptions import StorageError
from .models import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    job_id      TEXT PRIMARY KEY,
    title       TEXT,
    company     TEXT,
    url         TEXT,
    status      TEXT NOT NULL,
    score       INTEGER,
    first_seen  TEXT NOT NULL
);
"""

_MEMORY = ":memory:"


class SeenJobsDB:
    """Ingatan proyek: setiap lowongan yang pernah dilihat dicatat sekali.

    Lowongan yang ditolak pun dicatat agar tidak diproses ulang setiap run
    (spec §10). Gunakan :meth:`reset_rejected` untuk menilai ulang lowongan lama
    setelah mengubah kriteria.

    Args:
        path: Lokasi file SQLite, atau ``":memory:"`` untuk database sementara
            (dipakai saat test).
    """

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

    def has(self, job_id: str) -> bool:
        """Kembalikan ``True`` bila ``job_id`` sudah pernah dilihat."""
        with self._guard():
            row = self._conn.execute(
                "SELECT 1 FROM seen_jobs WHERE job_id = ? LIMIT 1", (job_id,)
            ).fetchone()
        return row is not None

    def get_status(self, job_id: str) -> str | None:
        """Kembalikan status tersimpan untuk ``job_id``, atau ``None``."""
        with self._guard():
            row = self._conn.execute(
                "SELECT status FROM seen_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return None if row is None else str(row["status"])

    def mark(self, job: Job, status: str) -> None:
        """Catat lowongan beserta statusnya.

        ``first_seen`` hanya diisi saat pertama kali; pemanggilan berikutnya untuk
        ``job_id`` yang sama hanya memperbarui ``status`` dan ``score``.
        """
        first_seen = datetime.now(UTC).isoformat()
        with self._guard(), self._conn:
            self._conn.execute(
                """
                INSERT INTO seen_jobs
                    (job_id, title, company, url, status, score, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    score  = excluded.score
                """,
                (job.job_id, job.title, job.company, job.url, status, job.score, first_seen),
            )

    def reset_rejected(self) -> int:
        """Hapus semua baris berstatus ``rejected_*``; kembalikan jumlah yang dihapus."""
        with self._guard(), self._conn:
            cursor = self._conn.execute("DELETE FROM seen_jobs WHERE status LIKE 'rejected_%'")
        return int(cursor.rowcount)

    def close(self) -> None:
        """Tutup koneksi database."""
        with self._guard():
            self._conn.close()
