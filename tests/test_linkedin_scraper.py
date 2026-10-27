"""Test scraper LinkedIn: URL builder dan retry 429 (tanpa jaringan)."""

from __future__ import annotations

import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from linkedin_scraper import scraper
from linkedin_scraper.config import ScraperConfig, SearchConfig
from linkedin_scraper.exceptions import RateLimitError, ScraperError
from linkedin_scraper.scraper import HttpSource, build_detail_url, build_search_url

SEARCH = SearchConfig(keywords=["Developer"], location="Indonesia")
CONFIG = ScraperConfig(max_retries=2)


class _FakeResponse:
    """Pengganti respons HTTP untuk test."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_build_search_url_defaults() -> None:
    url = build_search_url("Junior Web Developer", "Indonesia", 1)
    assert url == (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords=Junior+Web+Developer&location=Indonesia&start=0"
    )


def test_build_search_url_pagination() -> None:
    url = build_search_url("Developer", "Indonesia", 3)
    assert "start=20" in url


def test_build_search_url_filters() -> None:
    url = build_search_url(
        "Developer",
        "Indonesia",
        1,
        posted_within_days=7,
        work_types=["F"],
        experience_levels=[1, 2],
    )
    assert "f_TPR=r604800" in url
    assert "f_JT=F" in url
    assert "f_E=1%2C2" in url


def test_build_detail_url() -> None:
    assert build_detail_url("4446754033") == (
        "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4446754033"
    )


def test_search_page_html_builds_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_get(self: HttpSource, url: str) -> str:
        captured["url"] = url
        return "<html/>"

    monkeypatch.setattr(HttpSource, "_get", fake_get)
    monkeypatch.setattr(scraper, "random_delay", lambda *_: 0.0)

    search = SearchConfig(
        keywords=["Dev"],
        location="Indonesia",
        posted_within_days=7,
        work_types=["F"],
    )
    source = HttpSource(CONFIG, search)
    assert source.search_page_html("Dev", 2) == "<html/>"
    assert "start=10" in captured["url"]
    assert "f_TPR=r604800" in captured["url"]
    assert "f_JT=F" in captured["url"]


def test_fetch_detail_html_builds_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_get(self: HttpSource, url: str) -> str:
        captured["url"] = url
        return "<html/>"

    monkeypatch.setattr(HttpSource, "_get", fake_get)
    monkeypatch.setattr(scraper, "random_delay", lambda *_: 0.0)

    source = HttpSource(CONFIG, SEARCH)
    assert source.fetch_detail_html("123") == "<html/>"
    assert captured["url"].endswith("/jobPosting/123")


def _raise_429(*args: Any, **kwargs: Any) -> _FakeResponse:
    raise urllib.error.HTTPError("http://x", 429, "Too Many", Message(), None)


def test_get_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_urlopen(request: Any, timeout: int = 0) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError("http://x", 429, "Too Many", Message(), None)
        return _FakeResponse(b"<li>ok</li>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(scraper, "random_delay", lambda *_: 0.0)

    source = HttpSource(CONFIG, SEARCH, backoff_sec=0.0)
    assert source._get("https://example.test") == "<li>ok</li>"
    assert calls["n"] == 3


def test_get_exhausted_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _raise_429)
    monkeypatch.setattr(scraper, "random_delay", lambda *_: 0.0)

    source = HttpSource(CONFIG, SEARCH, backoff_sec=0.0)
    with pytest.raises(RateLimitError):
        source._get("https://example.test")


def test_get_non_429_http_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: int = 0) -> _FakeResponse:
        raise urllib.error.HTTPError("http://x", 404, "Not Found", Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    source = HttpSource(CONFIG, SEARCH, backoff_sec=0.0)
    with pytest.raises(ScraperError, match="HTTP 404"):
        source._get("https://example.test")


def test_get_rejects_oversized_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: int = 0) -> _FakeResponse:
        return _FakeResponse(b"01234567890")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    source = HttpSource(CONFIG, SEARCH, backoff_sec=0.0, max_response_bytes=10)

    with pytest.raises(ScraperError, match="terlalu besar"):
        source._get("https://example.test")


def test_build_detail_url_rejects_non_numeric_id() -> None:
    with pytest.raises(ValueError, match="job_id"):
        build_detail_url("../../etc/passwd")


def test_base_url_must_be_https() -> None:
    with pytest.raises(ValueError, match="https"):
        build_search_url("Dev", "Indonesia", 1, base_url="http://evil.test")
    with pytest.raises(ValueError, match="https"):
        build_detail_url("1", base_url="http://evil.test")


def test_get_retries_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_urlopen(request: Any, timeout: int = 0) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 2:
            raise urllib.error.URLError("connection reset")
        return _FakeResponse(b"<html/>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(scraper, "random_delay", lambda *_: 0.0)

    source = HttpSource(CONFIG, SEARCH, backoff_sec=0.0)
    assert source._get("https://example.test") == "<html/>"
    assert calls["n"] == 2
