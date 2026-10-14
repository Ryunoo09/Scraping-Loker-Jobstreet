"""Kontrak writer dan pemetaan ``Job`` ke baris spreadsheet (spec §7).

Header kolom adalah **sumber tunggal** di sini supaya Excel dan Google Sheets
selalu konsisten (14 kolom, urutan sesuai spec §7).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from ..models import Job

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
)

#: Nilai awal kolom "Status Lamaran" — diisi manual oleh pengguna setelahnya.
DEFAULT_APPLICATION_STATUS = "Belum"


class JobWriter(Protocol):
    """Kontrak penulis hasil: header dibuat sekali, lalu append per batch.

    Penulisan hanya boleh **menambah** baris; tidak pernah menimpa atau menghapus
    baris yang sudah ada (spec §7).
    """

    def ensure_header(self) -> None:
        """Pastikan baris header ada; tidak menimpa header/isi yang sudah ada."""
        ...

    def append(self, jobs: Sequence[Job]) -> None:
        """Tambahkan lowongan sebagai baris baru (sekali per run, batch)."""
        ...


def job_to_row(job: Job) -> list[str | int]:
    """Petakan satu :class:`Job` menjadi baris sesuai urutan kolom spec §7.

    Args:
        job: Lowongan yang sudah tervalidasi.

    Returns:
        Daftar 14 nilai, urut kolom A-N. Field opsional yang kosong menjadi ``""``.
    """
    return [
        job.found_date,
        job.title,
        job.company,
        job.location,
        job.url,
        job.salary_text or "",
        job.work_type or "",
        job.posted_date or "",
        job.score,
        DEFAULT_APPLICATION_STATUS,
        "",
        job.description or "",
        job.requirements or "",
        job.job_id,
    ]


class NullWriter:
    """Writer tanpa efek samping untuk uji ``--dry-run`` (spec §8.1)."""

    def ensure_header(self) -> None:
        """Tidak melakukan apa-apa (dry-run)."""
        logger.debug("NullWriter: header dilewati (dry-run)")

    def append(self, jobs: Sequence[Job]) -> None:
        """Catat ke log bahwa lowongan tidak ditulis (dry-run)."""
        logger.info("NullWriter: %d lowongan tidak ditulis (dry-run)", len(jobs))
