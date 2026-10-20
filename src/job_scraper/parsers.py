"""Parser HTML JobStreet → :class:`Job` (murni, tanpa jaringan).

Modul ini adalah **satu-satunya** tempat selector JobStreet berada. Semua selector
di sini berasal dari hasil investigasi Fase 0 (lihat ``docs/fase0-hasil.md``) dan
diuji dengan fixture asli di ``tests/fixtures/`` — **bukan tebakan**.

Pemisahan tanggung jawab (spec §3): ``scraper.py`` hanya mengambil HTML mentah;
modul ini yang mengubahnya menjadi objek domain. Jadi bila JobStreet mengubah
tampilan, cukup perbaiki file ini (dan perbarui fixture).
"""

from __future__ import annotations

import json
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

# --- Data server-state: waktu posting pasti — Fase 0 §2.1 ---------------- #
# Blok JSON di dalam <script data-automation="server-state"> memuat
# window.SEEK_REDUX_DATA; tiap lowongan punya "id" + "listingDate" (ISO 8601 UTC).
# Ini sumber **waktu posting pasti**, berbeda dari jobListingDate yang relatif.
_SERVER_STATE = re.compile(
    r'<script[^>]*data-automation="server-state"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_REDUX_ASSIGN = re.compile(r"window\.SEEK_REDUX_DATA\s*=\s*")
_DIGITS = re.compile(r"^\d+$")

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


def _balanced_object(text: str, start: int) -> str | None:
    """Ambil literal objek JSON seimbang mulai ``{`` pertama pada/atau setelah ``start``.

    Dipakai karena ``window.SEEK_REDUX_DATA = {...};`` diikuti pernyataan JavaScript
    lain, jadi regex sederhana tidak aman (kurung kurawal bersarang & string).
    """
    index = text.find("{", start)
    if index < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for position in range(index, len(text)):
        char = text[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[index : position + 1]
    return None


def _collect_listing_dates(node: Any, found: dict[str, str]) -> None:
    """Telusuri struktur JSON rekursif dan kumpulkan ``{job_id: listingDate}``.

    Pencarian rekursif (bukan jalur kaku seperti ``results.results.jobs``) supaya
    tetap berfungsi bila JobStreet mengubah kedalaman atau menambah pembungkus.
    """
    if isinstance(node, dict):
        job_id = str(node.get("id", ""))
        listed_at = node.get("listingDate")
        if _DIGITS.match(job_id) and isinstance(listed_at, str) and listed_at:
            found.setdefault(job_id, listed_at)
        for value in node.values():
            _collect_listing_dates(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_listing_dates(value, found)


def parse_listing_dates(html: str) -> dict[str, str]:
    """Petakan ``job_id -> listingDate`` (ISO 8601 UTC) dari HTML halaman hasil.

    Membaca blok ``window.SEEK_REDUX_DATA`` pada
    ``<script data-automation="server-state">`` (Fase 0 §2.1). Nilai ini adalah
    **waktu posting pasti**; ``jobListingDate`` di kartu hanya teks relatif.

    Args:
        html: HTML lengkap halaman hasil pencarian.

    Returns:
        Pemetaan Job ID → stempel waktu ISO 8601 UTC. **Kosong** bila blok tidak
        ditemukan atau JSON-nya rusak — pemanggil cukup memakai teks relatif.

    Notes:
        Sengaja tidak melempar error: struktur situs bisa berubah tanpa peringatan,
        dan tanggal relatif tetap fallback yang valid.
    """
    script = _SERVER_STATE.search(html)
    if script is None:
        return {}
    assignment = _REDUX_ASSIGN.search(script.group(1))
    if assignment is None:
        return {}
    literal = _balanced_object(script.group(1), assignment.end())
    if literal is None:
        return {}
    try:
        data = json.loads(literal)
    except json.JSONDecodeError:
        return {}
    found: dict[str, str] = {}
    _collect_listing_dates(data, found)
    return found


def parse_search_page(html: str, *, base_url: str = BASE_URL) -> list[Job]:
    """Ubah HTML halaman hasil menjadi daftar :class:`Job` (field kartu saja).

    Tanggal posting pasti (``posted_at``) diambil dari blok server-state via
    :func:`parse_listing_dates`; bila tidak tersedia, ``posted_at`` tetap ``None``
    dan ``posted_date`` (teks relatif dari kartu) dipakai sebagai fallback.

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
    listing_dates = parse_listing_dates(html)

    jobs: list[Job] = []
    for card in soup.select(_CARD):
        job = _parse_card(card, base_url)
        listed_at = listing_dates.get(job.job_id)
        if listed_at is not None:
            job = job.model_copy(update={"posted_at": listed_at})
        jobs.append(job)
    return jobs


def _description(element: Tag | None) -> str | None:
    """Ambil deskripsi penuh sebagai teks satu baris (whitespace dirapikan)."""
    if element is None:
        return None
    text = " ".join(element.get_text(" ").split())
    return text or None


#: Kata kunci header seksi kualifikasi/persyaratan (case-insensitive).
_REQUIREMENT_HEADERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"kualifikasi"),
    re.compile(r"persyaratan"),
    re.compile(r"requirements?"),
    re.compile(r"keterampilan\s+(dan\s+)?(kualifikasi|syarat)"),
    re.compile(r"syarat\s+(?!(utama|tanggung|pekerjaan|umum))?"),
    re.compile(r"skills?\s+(and\s+)?(qualifications?|requirements?)"),
)

#: Kata kunci header yang menandai akhir seksi kualifikasi (apa pun setelah ini bukan kualifikasi).
_END_SECTION_HEADERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"manfaat"),
    re.compile(r"benefits?"),
    re.compile(r"tentang\s+(perusahaan|kami)"),
    re.compile(r"about\s+(the\s+)?(company|us)"),
    re.compile(r"cara\s+(melamar|mendaftar)"),
    re.compile(r"how\s+to\s+(apply|join)"),
    re.compile(r"informasi\s+(tambahan|lainnya)"),
    re.compile(r"additional\s+information"),
    re.compile(r"tanggung\s+jawab"),
    re.compile(r"responsibilities?"),
)


def _extract_requirements(element: Tag | None) -> str | None:
    """Ambil teks kualifikasi/persyaratan dari elemen deskripsi HTML.

    Mencari seksi dengan header seperti "Kualifikasi", "Persyaratan",
    "Keterampilan dan Kualifikasi", lalu mengumpulkan teks dari elemen
    setelahnya (biasanya ``<ul>``) hingga header seksi lain ditemukan.

    Args:
        element: Elemen ``[data-automation="jobAdDetails"]``.

    Returns:
        Teks kualifikasi dalam satu baris, atau ``None`` bila tidak ditemukan.
    """
    if element is None:
        return None

    def _header_text(tag: Tag) -> str:
        return " ".join(tag.get_text(" ", strip=True).split()).lower()

    # Cari semua <strong>/<b> secara rekursif sebagai calon header seksi.
    all_strong = element.find_all(["strong", "b"])

    # Cari header kualifikasi pertama.
    target: Tag | None = None
    for tag in all_strong:
        txt = _header_text(tag)
        if any(p.search(txt) for p in _REQUIREMENT_HEADERS):
            target = tag
            break

    if target is None:
        return None

    # Mulai dari parent target, kumpulkan elemen setelah header.
    # Struktur tipikal:
    #   <p><strong>Kualifikasi</strong></p>
    #   <ul><li>...</li></ul>
    #   <p><strong>Manfaat</strong></p>

    parent = target.parent
    if parent is None:
        return None

    # Cari parent container (biasanya <div> di dalam jobAdDetails).
    container = parent.parent
    if container is None:
        return None

    siblings = list(container.find_all(recursive=False))
    try:
        start_idx = siblings.index(parent)
    except ValueError:
        return None

    end_idx: int | None = None
    for sib in siblings[start_idx + 1 :]:
        header = sib.find(["strong", "b"])
        if header is not None:
            txt = _header_text(header)
            if any(p.search(txt) for p in _END_SECTION_HEADERS):
                end_idx = siblings.index(sib)
                break

    parts: list[str] = []
    for sib in siblings[start_idx + 1 :]:
        if end_idx is not None and siblings.index(sib) >= end_idx:
            break
        text_content = _description(sib)
        if text_content:
            parts.append(text_content)

    if not parts:
        return None
    return " ".join(parts)


def parse_detail_page(html: str) -> JobDetail:
    """Ubah HTML halaman detail menjadi :class:`JobDetail`.

    Field yang tidak ada cukup dibiarkan ``None`` (banyak lowongan tidak
    mencantumkan gaji/tipe kerja) — bukan error.
    """
    soup = BeautifulSoup(html, "html.parser")
    salary_text = _normalized_text(soup.select_one(_DETAIL_SALARY))
    desc_element = soup.select_one(_DETAIL_DESCRIPTION)
    return JobDetail(
        title=_normalized_text(soup.select_one(_DETAIL_TITLE)),
        company=_normalized_text(soup.select_one(_DETAIL_COMPANY)),
        location=_normalized_text(soup.select_one(_DETAIL_LOCATION)),
        work_type=_normalized_text(soup.select_one(_DETAIL_WORK_TYPE)),
        salary_text=salary_text,
        salary_min_idr=parse_salary_min_idr(salary_text),
        description=_description(desc_element),
        requirements=_extract_requirements(desc_element),
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
    if detail.requirements is not None:
        updates["requirements"] = detail.requirements
    if detail.work_type is not None:
        updates["work_type"] = detail.work_type
    if detail.salary_text is not None:
        updates["salary_text"] = detail.salary_text
        updates["salary_min_idr"] = detail.salary_min_idr
    return job.model_copy(update=updates)
