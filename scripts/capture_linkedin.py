"""Skrip sekali-pakai: ambil fixture HTML guest LinkedIn untuk Fase 0.

Jalankan: .\\.venv\\Scripts\\python.exe scripts\\capture_linkedin.py

Endpoint guest LinkedIn mengembalikan HTML polos (tanpa JS), jadi skrip ini cukup
memakai HTTP GET — tidak perlu browser. Seluruh URL & selector dibuktikan dari
respons nyata, bukan tebakan.

Menghasilkan (bersih, aman di-commit):
- tests/fixtures/linkedin/guest_cards_01.html  -> guest API, start=0
- tests/fixtures/linkedin/guest_cards_02.html  -> guest API, start=10 (paginasi)
- tests/fixtures/linkedin/detail_01.html       -> guest API detail lowongan pertama

Catatan: halaman `/jobs/search` penuh memberi HTTP 429 (proteksi bot), sehingga
sumber yang dipakai adalah endpoint guest yang mengembalikan HTML polos.

Salinan mentah disimpan di tests/fixtures/linkedin/_raw/ (gitignored).
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from bs4.element import Tag

BASE_URL = "https://www.linkedin.com"
KEYWORDS = "Junior Web Developer"
LOCATION = "Indonesia"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "linkedin"
RAW_DIR = FIXTURES / "_raw"
DELAY_SEC = 2.0

_JOB_URN = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_TRACKING_ATTR = re.compile(r'\sdata-(?:tracking|impression|reference)[\w-]*="[^"]*"')
_TRACKING_QUERY = re.compile(r"(?:&amp;|&)(?:refId|trackingId)=[^&\"\s]*")
_TRACKING_QUERY_FIRST = re.compile(r"\?(?:refId|trackingId)=[^&\"\s]*(?:&amp;|&)?")
_CSRF_VALUE = re.compile(r'(name="[^"]*[Cc]srf[^"]*"[^>]*?value=")[^"]*"')


def _fetch(url: str, *, retries: int = 3, backoff_sec: float = 15.0) -> str:
    """Ambil HTML dengan User-Agent browser; ulangi sekali-sekian saat kena 429."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
    )
    for attempt in range(retries + 1):
        try:
            # URL selalu https dan berasal dari konstanta di modul ini.
            with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
                raw: bytes = response.read()
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == retries:
                raise
            wait = backoff_sec * (attempt + 1)
            print(f"  429 Too Many Requests — tunggu {wait:.0f}s lalu ulang...", flush=True)
            time.sleep(wait)
    raise RuntimeError("tidak tercapai")


def _sanitize(html: str) -> str:
    """Buang script/style, atribut, dan token pelacakan; pertahankan struktur DOM."""
    html = _SCRIPT.sub("<!-- script removed -->", html)
    html = _STYLE.sub("<!-- style removed -->", html)
    html = _TRACKING_ATTR.sub("", html)
    html = _TRACKING_QUERY.sub("", html)
    html = _TRACKING_QUERY_FIRST.sub("", html)
    return _CSRF_VALUE.sub(r'\1REDACTED"', html)


def _save(name: str, html: str) -> None:
    """Simpan versi mentah ke ``_raw/`` dan versi bersih ke folder fixture."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / name).write_text(html, encoding="utf-8")
    (FIXTURES / name).write_text(_sanitize(html), encoding="utf-8")


def _report(label: str, html: str) -> list[str]:
    """Cetak jumlah kartu + field lowongan pertama; kembalikan daftar Job ID."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.base-card")
    job_ids = _JOB_URN.findall(html)
    print(f"\n== {label} ==")
    print(f"  kartu (div.base-card): {len(cards)}")
    print(f"  Job ID (data-entity-urn): {len(job_ids)}")
    if cards:
        first = cards[0]
        _show(first, "title", ".base-search-card__title")
        _show(first, "company", ".base-search-card__subtitle")
        _show(first, "location", ".job-search-card__location")
        time_tag = first.select_one("time")
        print(f"  posted_at: {time_tag.get('datetime') if time_tag else None}")
    return job_ids


def _show(card: Tag, label: str, selector: str) -> None:
    """Cetak satu field kartu (dipakai hanya untuk laporan)."""
    element = card.select_one(selector)
    text = " ".join(element.get_text(" ", strip=True).split()) if element else None
    print(f"  {label}: {text}")


def _capture(name: str, url: str) -> str | None:
    """Ambil lalu simpan satu fixture; ``None`` bila gagal (mis. kena 429)."""
    print(f"Mengambil {name}: {url}")
    try:
        html = _fetch(url)
    except (urllib.error.URLError, OSError) as exc:
        print(f"  GAGAL: {exc}", flush=True)
        return None
    _save(name, html)
    return html


def main() -> int:
    """Ambil semua fixture guest LinkedIn lalu laporkan hasilnya."""
    guest_cards_url = (
        f"{BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={quote(KEYWORDS)}&location={quote(LOCATION)}&start={{start}}"
    )

    cards_01 = _capture("guest_cards_01.html", guest_cards_url.format(start=0))
    if cards_01 is None:
        return 1
    time.sleep(DELAY_SEC)

    cards_02 = _capture("guest_cards_02.html", guest_cards_url.format(start=10))

    job_ids = _report("guest_cards_01", cards_01)
    if cards_02 is not None:
        _report("guest_cards_02", cards_02)
    if not job_ids:
        print("Tidak ada Job ID — endpoint guest mungkin berubah.", flush=True)
        return 1

    time.sleep(DELAY_SEC)
    detail_url = f"{BASE_URL}/jobs-guest/jobs/api/jobPosting/{job_ids[0]}"
    detail_html = _capture("detail_01.html", detail_url)
    if detail_html is not None:
        print(f"  ukuran HTML detail: {len(detail_html)} karakter")

    print("\nSelesai. File yang ditulis:")
    for name in ("guest_cards_01.html", "guest_cards_02.html", "detail_01.html"):
        if (FIXTURES / name).is_file():
            print(f"  {FIXTURES / name}")
    print(f"  {RAW_DIR}  (mentah, gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
