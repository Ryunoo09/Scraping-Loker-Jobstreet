"""Scraper HTTP untuk endpoint guest LinkedIn (tanpa login).

Modul ini sengaja **tidak tahu** objek domain maupun selector — semua parsing ada di
:mod:`linkedin_scraper.parsers`. Pendekatan guest mengembalikan HTML polos, jadi tidak
butuh browser; cukup HTTP GET dengan User-Agent browser.

Endpoint & parameter berasal dari Fase 0 (``docs/fase0-linkedin.md``), bukan tebakan.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlencode

from .config import ScraperConfig, SearchConfig
from .exceptions import RateLimitError, ScraperError
from .utils import random_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com"
SEARCH_PATH = "/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_PATH = "/jobs-guest/jobs/api/jobPosting/{job_id}"

#: Kartu per halaman pada endpoint guest (terverifikasi Fase 0).
PAGE_SIZE = 10

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class JobSource(Protocol):
    """Kontrak sumber HTML mentah (mudah di-fake saat test)."""

    def search_page_html(self, keyword: str, page: int) -> str:
        """Ambil HTML satu halaman kartu (termasuk jeda kesopanan)."""
        ...

    def fetch_detail_html(self, job_id: str) -> str:
        """Ambil HTML detail satu lowongan."""
        ...


def build_search_url(
    keyword: str,
    location: str,
    page: int,
    *,
    posted_within_days: int | None = None,
    work_types: Sequence[str] = (),
    experience_levels: Sequence[int] = (),
    base_url: str = BASE_URL,
) -> str:
    """Bangun URL guest untuk satu halaman kartu.

    Args:
        keyword: Kata kunci pencarian.
        location: Lokasi (teks bebas, mis. ``"Indonesia"``).
        page: Nomor halaman 1-based; dikonversi ke ``start`` kelipatan 10.
        posted_within_days: Bila diisi, menambah ``f_TPR`` (rentang hari).
        work_types: Kode ``f_JT`` (mis. ``["F"]``).
        experience_levels: Kode ``f_E`` (mis. ``[1, 2]``).
        base_url: Basis situs (bisa diganti saat test).

    Returns:
        URL absolut endpoint guest.
    """
    params: dict[str, str | int] = {
        "keywords": keyword,
        "location": location,
        "start": (page - 1) * PAGE_SIZE,
    }
    if posted_within_days is not None:
        params["f_TPR"] = f"r{posted_within_days * 86_400}"
    if work_types:
        params["f_JT"] = ",".join(work_types)
    if experience_levels:
        params["f_E"] = ",".join(str(level) for level in experience_levels)
    return f"{base_url}{SEARCH_PATH}?{urlencode(params)}"


def build_detail_url(job_id: str, *, base_url: str = BASE_URL) -> str:
    """Bangun URL guest untuk detail satu lowongan."""
    return f"{base_url}{DETAIL_PATH.format(job_id=job_id)}"


class HttpSource:
    """Sumber HTML guest berbasis HTTP GET dengan retry/backoff.

    Pakai sebagai context manager agar rapi (tidak ada resource yang perlu ditutup,
    tetapi bentuknya konsisten dengan ``Scraper`` JobStreet).
    """

    def __init__(
        self,
        cfg: ScraperConfig,
        search: SearchConfig,
        *,
        backoff_sec: float = 5.0,
    ) -> None:
        self._cfg = cfg
        self._search = search
        self._backoff_sec = backoff_sec

    def __enter__(self) -> HttpSource:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def search_page_html(self, keyword: str, page: int) -> str:
        """Ambil HTML halaman kartu lalu jeda acak (kesopanan)."""
        url = build_search_url(
            keyword,
            self._search.location,
            page,
            posted_within_days=self._search.posted_within_days,
            work_types=self._search.work_types,
            experience_levels=self._search.experience_levels,
        )
        html = self._get(url)
        random_delay(self._cfg.delay_min_sec, self._cfg.delay_max_sec)
        return html

    def fetch_detail_html(self, job_id: str) -> str:
        """Ambil HTML detail lalu jeda acak (kesopanan)."""
        html = self._get(build_detail_url(job_id))
        random_delay(self._cfg.delay_min_sec, self._cfg.delay_max_sec)
        return html

    def _get(self, url: str) -> str:
        """GET ``url`` dengan retry saat 429/jaringan gagal."""
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
        )
        last_error: ScraperError = ScraperError(f"Gagal memuat {url}")
        for attempt in range(self._cfg.max_retries + 1):
            try:
                # URL selalu https dan berasal dari konstanta modul ini.
                with urllib.request.urlopen(  # nosec B310
                    request, timeout=self._cfg.page_timeout_sec
                ) as response:
                    raw: bytes = response.read()
                    return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    raise ScraperError(f"HTTP {exc.code} saat memuat {url}") from exc
                last_error = RateLimitError(f"429 Too Many Requests: {url}")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = ScraperError(f"Gagal memuat {url}: {exc}")
            wait = min(60.0, self._backoff_sec * (attempt + 1))
            logger.warning("%s (percobaan %d) — tunggu %.0fs", last_error, attempt + 1, wait)
            random_delay(wait, wait)
        raise last_error
