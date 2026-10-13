"""Parser HTML JobStreet → :class:`Job` (murni, tanpa jaringan).

Modul ini adalah **satu-satunya** tempat selector JobStreet berada. Semua selector
di sini berasal dari hasil investigasi Fase 0 (lihat ``docs/fase0-hasil.md``) dan
diuji dengan fixture asli di ``tests/fixtures/`` — **bukan tebakan**.

Pemisahan tanggung jawab (spec §3): ``scraper.py`` hanya mengambil HTML mentah;
modul ini yang mengubahnya menjadi objek domain. Jadi bila JobStreet mengubah
tampilan, cukup perbaiki file ini (dan perbarui fixture).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from .exceptions import StructureChangedError
from .models import Job, JobDetail

#: Basis URL untuk mengubah link relatif menjadi absolut.
BASE_URL = "https://id.jobstreet.com"

# --- Selector daftar hasil (kartu) — Fase 0 §2 -------------------------- #
_CARD = '[data-automation="normalJob"]'
_TITLE = '[data-automation="jobTitle"]'
_COMPANY = '[data-automation="jobCompany"]'
_LOCATION = '[data-automation="jobLocation"]'
_SALARY = '[data-automation="jobSalary"]'
_POSTED = '[data-automation="jobListingDate"]'

# --- Selector halaman detail — Fase 0 §3 -------------------------------- #
_DETAIL_TITLE = '[data-automation="job-detail-title"]'
_DETAIL_COMPANY = '[data-automation="advertiser-name"]'
_DETAIL_LOCATION = '[data-automation="job-detail-location"]'
_DETAIL_WORK_TYPE = '[data-automation="job-detail-work-type"]'
_DETAIL_SALARY = '[data-automation="job-detail-salary"]'
_DETAIL_DESCRIPTION = '[data-automation="jobAdDetails"]'

_JOB_ID_IN_HREF = re.compile(r"/job/(\d+)")
_AMOUNT = re.compile(r"\d[\d.,]*")
_SEPARATORS = re.compile(r"[.,]")

# Pengganda "juta"/"ribu" yang lazim di JobStreet (urut dari terbesar).
_MULTIPLIERS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(miliar|milyar)\b"), 1_000_000_000),
    (re.compile(r"\b(juta|jt)\b"), 1_000_000),
    (re.compile(r"\b(ribu|rb)\b"), 1_000),
)


def _normalized_text(element: Tag | None) -> str | None:
    """Ambil teks satu elemen, rapikan whitespace; ``None`` bila kosong/absen."""
    if element is None:
        return None
    text = " ".join(element.get_text(" ", strip=True).split())
    return text or None


def _attribute(tag: Tag, name: str) -> str | None:
    """Baca atribut sebagai ``str`` (abaikan nilai non-string)."""
    value = tag.get(name)
    return value if isinstance(value, str) else None


def _job_id_from_href(href: str) -> str | None:
    """Ambil Job ID dari link ``/id/job/<id>`` bila atribut ``data-job-id`` absen."""
    match = _JOB_ID_IN_HREF.search(href)
    return match.group(1) if match else None


def _parse_card(card: Tag, base_url: str) -> Job:
    """Ubah satu elemen kartu menjadi :class:`Job` (tanpa deskripsi/tipe kerja)."""
    title_element = card.select_one(_TITLE)
    title = _normalized_text(title_element)
    if title is None or title_element is None:
        raise StructureChangedError(
            "Kartu lowongan tanpa judul (jobTitle) — struktur JobStreet mungkin berubah."
        )

    href = _attribute(title_element, "href")
    if href is None:
        raise StructureChangedError(
            f"Kartu lowongan {title!r} tanpa atribut href — struktur JobStreet mungkin berubah."
        )

    job_id = _attribute(card, "data-job-id") or _job_id_from_href(href)
    if job_id is None:
        raise StructureChangedError(
            f"Kartu lowongan {title!r} tanpa Job ID — struktur JobStreet mungkin berubah."
        )

    salary_text = _normalized_text(card.select_one(_SALARY))
    return Job(
        job_id=job_id,
        title=title,
        company=_normalized_text(card.select_one(_COMPANY)) or "",
        location=_normalized_text(card.select_one(_LOCATION)) or "",
        url=urljoin(base_url, href),
        salary_text=salary_text,
        salary_min_idr=parse_salary_min_idr(salary_text),
        posted_date=_normalized_text(card.select_one(_POSTED)),
    )


def parse_search_page(html: str, *, base_url: str = BASE_URL) -> list[Job]:
    """Ubah HTML halaman hasil menjadi daftar :class:`Job` (field kartu saja).

    Args:
        html: HTML lengkap halaman hasil pencarian.
        base_url: Basis untuk mengubah link relatif menjadi absolut.

    Returns:
        Daftar lowongan sesuai urutan kemunculan. Kosong bila tidak ada kartu
        (mis. pencarian tanpa hasil).

    Raises:
        StructureChangedError: Kartu ada tetapi field wajibnya (judul/link/ID)
            tidak ditemukan — indikasi struktur situs berubah.
    """
    soup = BeautifulSoup(html, "html.parser")
    return [_parse_card(card, base_url) for card in soup.select(_CARD)]


def _description(element: Tag | None) -> str | None:
    """Ambil deskripsi penuh sebagai teks satu baris (whitespace dirapikan)."""
    if element is None:
        return None
    text = " ".join(element.get_text(" ").split())
    return text or None


def parse_detail_page(html: str) -> JobDetail:
    """Ubah HTML halaman detail menjadi :class:`JobDetail`.

    Field yang tidak ada cukup dibiarkan ``None`` (banyak lowongan tidak
    mencantumkan gaji/tipe kerja) — bukan error.
    """
    soup = BeautifulSoup(html, "html.parser")
    salary_text = _normalized_text(soup.select_one(_DETAIL_SALARY))
    return JobDetail(
        title=_normalized_text(soup.select_one(_DETAIL_TITLE)),
        company=_normalized_text(soup.select_one(_DETAIL_COMPANY)),
        location=_normalized_text(soup.select_one(_DETAIL_LOCATION)),
        work_type=_normalized_text(soup.select_one(_DETAIL_WORK_TYPE)),
        salary_text=salary_text,
        salary_min_idr=parse_salary_min_idr(salary_text),
        description=_description(soup.select_one(_DETAIL_DESCRIPTION)),
    )


def _decimal_value(raw: str) -> float:
    """Ubah angka bergaya 'juta' (mis. ``4,5`` / ``4.5``) menjadi float."""
    if "," in raw and "." in raw:
        # "." pemisah ribuan, "," desimal: 1.500,5 -> 1500.5
        return float(raw.replace(".", "").replace(",", "."))
    return float(raw.replace(",", "."))


def parse_salary_min_idr(text: str | None) -> int | None:
    """Ambil batas bawah gaji (Rupiah) dari teks gaji JobStreet.

    Contoh: ``"Rp 4.000.000 - Rp 6.000.000 per month"`` → ``4000000``.
    Mendukung angka penuh (pemisah ribuan ``.`` atau ``,``) dan bentuk
    ``juta``/``ribu``. Mengembalikan ``None`` bila tidak ada angka
    (mis. "Competitive"/gaji disembunyikan).

    Catatan: nilai dianggap **per bulan** seperti asumsi config
    ``filters.min_salary_idr``; konversi periode (per tahun/jam) tidak dilakukan.
    """
    if not text:
        return None
    lowered = text.lower()
    match = _AMOUNT.search(lowered)
    if match is None:
        return None

    raw = match.group(0).rstrip(".,")
    for pattern, factor in _MULTIPLIERS:
        if pattern.search(lowered):
            return int(_decimal_value(raw) * factor)
    return int(_SEPARATORS.sub("", raw))


def apply_detail(job: Job, detail: JobDetail) -> Job:
    """Gabungkan :class:`JobDetail` ke :class:`Job` (mengembalikan salinan).

    Hanya field yang terisi di ``detail`` yang menimpa; partial detail tidak
    mengosongkan data dari kartu.
    """
    updates: dict[str, Any] = {}
    if detail.description is not None:
        updates["description"] = detail.description
    if detail.work_type is not None:
        updates["work_type"] = detail.work_type
    if detail.salary_text is not None:
        updates["salary_text"] = detail.salary_text
        updates["salary_min_idr"] = detail.salary_min_idr
    return job.model_copy(update=updates)
