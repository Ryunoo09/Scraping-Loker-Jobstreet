"""Parser HTML guest LinkedIn → :class:`JobLinkedIn` (murni, tanpa jaringan).

Modul ini adalah **satu-satunya** tempat selector LinkedIn berada. Semua selector
berasal dari Fase 0 (``docs/fase0-linkedin.md``) dan diuji dengan fixture asli di
``tests/fixtures/linkedin/``.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from .exceptions import StructureChangedError
from .models import JobDetail, JobLinkedIn

BASE_URL = "https://www.linkedin.com"

# --- Selector kartu (Fase 0 §3) ----------------------------------------- #
_CARD = "div.base-card"
_CARD_TITLE = ".base-search-card__title"
_CARD_COMPANY = ".base-search-card__subtitle"
_CARD_LOCATION = ".job-search-card__location"
_CARD_LINK = "a.base-card__full-link"
_CARD_TIME = "time"

# --- Selector detail (Fase 0 §4) ---------------------------------------- #
_DETAIL_TITLE = ".top-card-layout__title"
_DETAIL_COMPANY = ".topcard__org-name-link"
_DETAIL_LOCATION = ".topcard__flavor--bullet"
_DETAIL_POSTED_TEXT = ".posted-time-ago__text"
_DETAIL_DESCRIPTION = ".show-more-less-html__markup"

_JOB_URN = re.compile(r"urn:li:jobPosting:(\d+)")
_JOB_ID_IN_HREF = re.compile(r"/jobs/view/[^?]*-(\d+)(?:\?|$)")


def _normalized_text(element: Tag | None) -> str | None:
    """Ambil teks satu elemen, rapikan whitespace; ``None`` bila kosong/absen."""
    if element is None:
        return None
    text = " ".join(element.get_text(" ", strip=True).split())
    return text or None


def _description(element: Tag | None) -> str | None:
    """Ambil deskripsi penuh sebagai teks satu baris."""
    if element is None:
        return None
    text = " ".join(element.get_text(" ").split())
    return text or None


def _attribute(tag: Tag, name: str) -> str | None:
    """Baca atribut sebagai ``str`` (abaikan nilai non-string)."""
    value = tag.get(name)
    return value if isinstance(value, str) else None


def _job_id(card: Tag, href: str) -> str | None:
    """Ambil Job ID dari ``data-entity-urn`` atau link detail."""
    urn = _attribute(card, "data-entity-urn")
    if urn is not None:
        match = _JOB_URN.search(urn)
        if match is not None:
            return match.group(1)
    match = _JOB_ID_IN_HREF.search(href)
    return match.group(1) if match is not None else None


def _parse_card(card: Tag, base_url: str) -> JobLinkedIn:
    """Ubah satu elemen kartu menjadi :class:`JobLinkedIn`."""
    title = _normalized_text(card.select_one(_CARD_TITLE))
    title_element = card.select_one(_CARD_TITLE)
    if title is None or title_element is None:
        raise StructureChangedError(
            "Kartu lowongan tanpa judul (.base-search-card__title) — struktur LinkedIn berubah."
        )

    link = card.select_one(_CARD_LINK)
    href = _attribute(link, "href") if link is not None else None
    if href is None:
        raise StructureChangedError(
            f"Kartu lowongan {title!r} tanpa link detail — struktur LinkedIn berubah."
        )

    job_id = _job_id(card, href)
    if job_id is None:
        raise StructureChangedError(
            f"Kartu lowongan {title!r} tanpa Job ID — struktur LinkedIn berubah."
        )

    time_element = card.select_one(_CARD_TIME)
    posted_at = _attribute(time_element, "datetime") if time_element is not None else None

    return JobLinkedIn(
        job_id=job_id,
        title=title,
        company=_normalized_text(card.select_one(_CARD_COMPANY)) or "",
        location=_normalized_text(card.select_one(_CARD_LOCATION)) or "",
        url=urljoin(base_url, href),
        posted_at=posted_at,
        posted_date_text=_normalized_text(time_element),
    )


def parse_search_page(html: str, *, base_url: str = BASE_URL) -> list[JobLinkedIn]:
    """Ubah HTML halaman kartu menjadi daftar :class:`JobLinkedIn`.

    Raises:
        StructureChangedError: Kartu ada tetapi field wajibnya (judul/link/ID)
            tidak ditemukan.
    """
    soup = BeautifulSoup(html, "html.parser")
    return [_parse_card(card, base_url) for card in soup.select(_CARD)]


def _extract_requirements(desc_element: Tag | None) -> str | None:
    """Ambil daftar ``<li>`` pada deskripsi (penanda kualifikasi/poin)."""
    if desc_element is None:
        return None
    parts = [_description(item) for item in desc_element.find_all("li")]
    text = " ".join(part for part in parts if part)
    return text or None


def parse_detail_page(html: str) -> JobDetail:
    """Ubah HTML detail guest menjadi :class:`JobDetail`. Field absen = ``None``."""
    soup = BeautifulSoup(html, "html.parser")
    desc_element = soup.select_one(_DETAIL_DESCRIPTION)
    return JobDetail(
        title=_normalized_text(soup.select_one(_DETAIL_TITLE)),
        company=_normalized_text(soup.select_one(_DETAIL_COMPANY)),
        location=_normalized_text(soup.select_one(_DETAIL_LOCATION)),
        posted_date_text=_normalized_text(soup.select_one(_DETAIL_POSTED_TEXT)),
        description=_description(desc_element),
        requirements=_extract_requirements(desc_element),
    )


def apply_detail(job: JobLinkedIn, detail: JobDetail) -> JobLinkedIn:
    """Gabungkan :class:`JobDetail` ke :class:`JobLinkedIn` (kembalikan salinan).

    Detail guest sering terpotong/gagal. Field yang kosong **tidak** menimpa data
    kartu, dan ``detail_complete`` hanya ``True`` bila deskripsi berhasil diambil.
    """
    updates: dict[str, Any] = {}
    if detail.description is not None:
        updates["description"] = detail.description
        updates["detail_complete"] = True
    if detail.requirements is not None:
        updates["requirements"] = detail.requirements
    return job.model_copy(update=updates)
