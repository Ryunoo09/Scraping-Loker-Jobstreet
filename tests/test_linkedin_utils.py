"""Test utilitas LinkedIn: normalisasi teks, jeda, dan logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import linkedin_scraper.utils as utils


def test_normalize_text_collapses_whitespace_and_lowercases() -> None:
    assert utils.normalize_text("  Senior\tDeveloper\n") == "senior developer"


def test_normalize_text_handles_none() -> None:
    assert utils.normalize_text(None) == ""


def test_random_delay_returns_duration() -> None:
    assert utils.random_delay(0.0, 0.0) == 0.0


def test_setup_logging_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utils, "_LOGGING_CONFIGURED", False)
    root = logging.getLogger()
    before = len(root.handlers)

    utils.setup_logging(tmp_path / "log.txt")
    after_first = len(root.handlers)
    utils.setup_logging(tmp_path / "log.txt")

    assert len(root.handlers) == after_first
    assert after_first > before

    for handler in root.handlers[before:]:
        root.removeHandler(handler)
        handler.close()
