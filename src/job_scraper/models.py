"""Model domain: satu lowongan dan hasil evaluasinya."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """Satu lowongan kerja yang sudah dinormalisasi.

    Attributes:
        job_id: ID unik dari JobStreet (atau hash fallback).
        title: Judul lowongan.
        company: Nama perusahaan.
        location: Kota/area.
        url: URL halaman detail lowongan.
        salary_text: Teks gaji apa adanya, bila ada.
        salary_min_idr: Batas bawah gaji dalam Rupiah, bila bisa diparse.
        work_type: Full time / Magang / kontrak / dll.
        posted_date: Tanggal posting (ISO date) bila tersedia.
        description: Deskripsi lengkap dari halaman detail.
        found_date: Tanggal lowongan ditemukan (ISO date).
        score: Skor kecocokan 0-100 dari tahap scoring.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    job_id: str
    title: str
    company: str
    location: str
    url: str
    salary_text: str | None = None
    salary_min_idr: int | None = None
    work_type: str | None = None
    posted_date: str | None = None
    description: str | None = None
    found_date: str = Field(default_factory=lambda: date.today().isoformat())
    score: int = 0


class EvalResult(BaseModel):
    """Hasil evaluasi filter + scoring untuk satu :class:`Job`."""

    passed: bool
    score: int = 0
    reason: str = ""
