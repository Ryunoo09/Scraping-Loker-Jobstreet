"""Kontrak writer dan pemetaan ``JobLinkedIn`` ke baris spreadsheet."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from ..models import JobLinkedIn

logger = logging.getLogger(__name__)

HEADERS: tuple[str, ...] = (
    "Tanggal Ditemukan",
    "Posisi",
    "Nama Perusahaan",
    "Lokasi",
    "Link Lowongan",
    "Gaji",
    "Tipe Kerja",
    "Tanggal Posting",
    "Skor",
    "Status Lamaran",
    "Catatan",
    "Deskripsi",
    "Kualifikasi",
    "Job ID",
    "Detail Lengkap?",
)

#: Nilai awal kolom "Status Lamaran" — diisi manual oleh pengguna setelahnya.
DEFAULT_APPLICATION_STATUS = "Belum"


class JobWriter(Protocol):
    """Kontrak penulis hasil: append-only, header dibuat sekali."""

    def ensure_header(self) -> None:
        """Pastikan baris header ada; tidak menimpa header/isi yang sudah ada."""
        ...

    def append(self, jobs: Sequence[JobLinkedIn]) -> None:
        """Tambahkan lowongan sebagai baris baru."""
        ...


def job_to_row(job: JobLinkedIn) -> list[str | int]:
    """Petakan satu :class:`JobLinkedIn` menjadi 15 nilai (kolom A-O)."""
    return [
        job.found_date,
        job.title,
        job.company,
        job.location,
        job.url,
        job.salary_text or "",
        job.work_type or "",
        job.posted_at or job.posted_date_text or "",
        job.score,
        DEFAULT_APPLICATION_STATUS,
        "",
        job.description or "",
        job.requirements or "",
        job.job_id,
        "Ya" if job.detail_complete else "Tidak",
    ]


class NullWriter:
    """Writer tanpa efek samping untuk ``--dry-run``."""

    def ensure_header(self) -> None:
        """Tidak melakukan apa-apa (dry-run)."""
        logger.debug("NullWriter: header dilewati (dry-run)")

    def append(self, jobs: Sequence[JobLinkedIn]) -> None:
        """Catat ke log bahwa lowongan tidak ditulis (dry-run)."""
        logger.info("NullWriter: %d lowongan tidak ditulis (dry-run)", len(jobs))
