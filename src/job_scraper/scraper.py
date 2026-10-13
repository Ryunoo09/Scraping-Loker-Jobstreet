"""Scraper Playwright (sinkron): navigasi + ambil HTML **mentah** (spec §12).

Modul ini sengaja **tidak tahu** objek :class:`~job_scraper.models.Job` maupun
selector JobStreet — semua parsing ada di :mod:`job_scraper.parsers` (spec §3,
EXECUTION-PLAN §6). Karena butuh browser + internet, modul ini dikecualikan dari
target coverage; logika parser diuji lewat fixture, dan jalur ini diuji dengan
smoketest manual (``scripts/smoke_scraper.py``).

Urutan URL bersumber dari hasil investigasi Fase 0 (``docs/fase0-hasil.md``),
bukan tebakan.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType
from typing import Protocol, Self
from urllib.parse import quote

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    ViewportSize,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from .config import ScraperConfig
from .exceptions import ScraperError
from .utils import random_delay

#: Basis situs JobStreet Indonesia (Fase 0 §1).
BASE_URL = "https://id.jobstreet.com"

_VIEWPORT: ViewportSize = {"width": 1366, "height": 900}


class JobSource(Protocol):
    """Kontrak sumber HTML mentah (dipakai orkestrasi; mudah di-fake saat test)."""

    def iter_search_pages(self, keyword: str, location: str, *, max_pages: int) -> Iterator[str]:
        """Hasilkan HTML halaman hasil pencarian untuk tiap nomor halaman."""
        ...

    def fetch_detail_html(self, url: str) -> str:
        """Ambil HTML satu halaman detail lowongan."""
        ...


def _slug(text: str) -> str:
    """Ubah teks menjadi segmen URL gaya JobStreet (spasi → tanda hubung)."""
    collapsed = "-".join(text.split())
    return quote(collapsed, safe="-")


def build_search_url(
    keyword: str,
    location: str,
    page: int,
    *,
    base_url: str = BASE_URL,
) -> str:
    """Bangun URL halaman hasil pencarian (pola Fase 0).

    Args:
        keyword: Kata kunci pencarian, mis. ``"Junior developer"``.
        location: Lokasi, mis. ``"Jawa Barat"``.
        page: Nomor halaman (1-based); ``1`` tidak menambah query.
        base_url: Basis situs (bisa diganti saat test).

    Returns:
        URL absolut, mis. ``https://id.jobstreet.com/id/Junior-developer-jobs/in-Jawa-Barat``.
    """
    url = f"{base_url}/id/{_slug(keyword)}-jobs/in-{_slug(location)}"
    if page > 1:
        url = f"{url}?page={page}"
    return url


class Scraper:
    """Konteks browser Playwright sinkron untuk mengambil HTML mentah.

    Pakai sebagai context manager agar browser selalu ditutup:

        with Scraper(cfg.scraper) as source:
            for html in source.iter_search_pages("IT Support", "Semarang", max_pages=3):
                ...
    """

    def __init__(self, cfg: ScraperConfig) -> None:
        self._cfg = cfg
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> Self:
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=self._cfg.headless)
            self._context = self._browser.new_context(locale="id-ID", viewport=_VIEWPORT)
            self._page = self._context.new_page()
            self._page.set_default_timeout(self._cfg.page_timeout_sec * 1000)
        except PlaywrightError as exc:
            self.close()
            raise ScraperError(f"Gagal memulai browser: {exc}") from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def _current_page(self) -> Page:
        """Halaman aktif; error jelas bila scraper belum dibuka."""
        if self._page is None:
            raise ScraperError("Scraper belum dibuka; gunakan 'with Scraper(cfg):'.")
        return self._page

    def close(self) -> None:
        """Tutup halaman/context/browser/playwright dengan aman (idempoten)."""
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def iter_search_pages(self, keyword: str, location: str, *, max_pages: int) -> Iterator[str]:
        """Hasilkan HTML mentah tiap halaman hasil, dengan jeda acak antar halaman.

        Berhenti memuat halaman berikutnya adalah tugas pemanggil (mengetahui
        "0 kartu" butuh selector, yang hanya ada di :mod:`job_scraper.parsers`).
        """
        for page_no in range(1, max_pages + 1):
            yield self._load(build_search_url(keyword, location, page_no))
            if page_no < max_pages:
                random_delay(self._cfg.delay_min_sec, self._cfg.delay_max_sec)

    def fetch_detail_html(self, url: str) -> str:
        """Ambil HTML satu halaman detail, lalu jeda acak (kesopanan, spec §12)."""
        html = self._load(url)
        random_delay(self._cfg.delay_min_sec, self._cfg.delay_max_sec)
        return html

    def _load(self, url: str) -> str:
        """Navigasi ke ``url`` dan kembalikan HTML halaman; timeout → ScraperError."""
        page = self._current_page
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_load_state("load")
        except PlaywrightTimeoutError as exc:
            raise ScraperError(f"Timeout memuat {url}: {exc}") from exc
        except PlaywrightError as exc:
            raise ScraperError(f"Gagal memuat {url}: {exc}") from exc
        return page.content()
