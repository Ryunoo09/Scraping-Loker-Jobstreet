"""Test untuk ``utils``: jeda acak, normalisasi teks, dan logging."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from job_scraper import utils


def test_random_delay_within_range(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[float] = []
    monkeypatch.setattr(time, "sleep", recorded.append)

    delay = utils.random_delay(1.0, 2.0)

    assert recorded == [delay]
    assert 1.0 <= delay <= 2.0


def test_random_delay_equal_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    assert utils.random_delay(0.5, 0.5) == 0.5


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Hello\n  World  ", "hello world"),
        ("TAB\tinside", "tab inside"),
        (None, ""),
        ("", ""),
        ("\uff26\uff55\uff4c\uff4c", "full"),
    ],
)
def test_normalize_text(raw: str | None, expected: str) -> None:
    assert utils.normalize_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-13T02:58:53.000Z", "2026-10-13 09:58"),  # UTC -> WIB (+7)
        ("2026-10-13T18:30:00Z", "2026-10-14 01:30"),  # lewat tengah malam WIB
        ("2026-10-13T09:58:00", "2026-10-13 16:58"),  # tanpa zona dianggap UTC
        ("2026-10-13T02:58:53+07:00", "2026-10-13 02:58"),  # sudah WIB
        (None, None),
        ("", None),
        ("bukan-tanggal", None),
    ],
)
def test_to_wib(raw: str | None, expected: str | None) -> None:
    assert utils.to_wib(raw) == expected


def test_setup_logging_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = tmp_path / "logs" / "scraper.log"
    # Isolasi: test lain (mis. cli) mungkin sudah mengonfigurasi logging global.
    for handler in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(handler)
    monkeypatch.setattr(utils, "_LOGGING_CONFIGURED", False)

    utils.setup_logging(log_path)
    logging.getLogger("test").info("halo dunia")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.is_file()
    assert "halo dunia" in log_path.read_text(encoding="utf-8")
