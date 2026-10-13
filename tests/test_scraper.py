"""Test bagian murni :mod:`job_scraper.scraper` (tanpa browser/jaringan).

``scraper.py`` dikecualikan dari target coverage (butuh browser), tetapi logika
pembangun URL layak diuji offline.
"""

from __future__ import annotations

import pytest

from job_scraper.config import ScraperConfig
from job_scraper.exceptions import ScraperError
from job_scraper.scraper import BASE_URL, Scraper, build_search_url


def test_build_search_url_first_page() -> None:
    url = build_search_url("Junior developer", "Jawa Barat", 1)

    assert url == f"{BASE_URL}/id/Junior-developer-jobs/in-Jawa-Barat"


def test_build_search_url_adds_page_query() -> None:
    url = build_search_url("Junior developer", "Jawa Barat", 2)

    assert url == f"{BASE_URL}/id/Junior-developer-jobs/in-Jawa-Barat?page=2"


def test_build_search_url_collapses_extra_whitespace() -> None:
    url = build_search_url("  IT   Support ", "  Semarang ", 1)

    assert url == f"{BASE_URL}/id/IT-Support-jobs/in-Semarang"


def test_build_search_url_encodes_special_characters() -> None:
    url = build_search_url("C#", "Jakarta Raya", 1)

    assert url == f"{BASE_URL}/id/C%23-jobs/in-Jakarta-Raya"


def test_build_search_url_respects_base_url() -> None:
    url = build_search_url("Backend", "Bandung", 1, base_url="https://example.test")

    assert url == "https://example.test/id/Backend-jobs/in-Bandung"


def test_using_scraper_without_enter_raises() -> None:
    scraper = Scraper(ScraperConfig())

    with pytest.raises(ScraperError, match="belum dibuka"):
        scraper.fetch_detail_html("https://example.test/job/1")


def test_close_before_open_is_safe() -> None:
    Scraper(ScraperConfig()).close()
