"""Model domain untuk lowongan LinkedIn (guest)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class JobLinkedIn(BaseModel):
    """Satu lowongan LinkedIn yang sudah dinormalisasi.

    Catatan mode guest: gaji dan tipe kerja tidak tersedia, jadi keduanya biasanya
    ``None`` (lihat ``docs/fase0-linkedin.md`` §5).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    job_id: str
    title: str
    company: str
    location: str
    url: str
    salary_text: str | None = None
    work_type: str | None = None
    posted_at: str | None = None  # tanggal saja: YYYY-MM-DD
    posted_date_text: str | None = None  # teks relatif, mis. "2 bulan yang lalu"
    description: str | None = None
    requirements: str | None = None
    found_date: str = Field(default_factory=lambda: date.today().isoformat())
    score: int = 0
    detail_complete: bool = False


class JobDetail(BaseModel):
    """Field yang hanya tersedia di halaman detail guest."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str | None = None
    company: str | None = None
    location: str | None = None
    posted_date_text: str | None = None
    description: str | None = None
    requirements: str | None = None


class EvalResult(BaseModel):
    """Hasil filter + scoring untuk satu :class:`JobLinkedIn`."""

    passed: bool
    score: int = 0
    reason: str = ""
