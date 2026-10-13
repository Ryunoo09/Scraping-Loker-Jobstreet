"""Test untuk CLI pada milestone M1 (``--config`` dan ``--check-config``)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from job_scraper.cli import main


def test_check_config_ok(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_config(valid_config_text)
    assert main(["--check-config", "--config", str(path)]) == 0
    assert "Config valid" in capsys.readouterr().out


def test_check_config_invalid(
    write_config: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_config("search: [")
    assert main(["--check-config", "--config", str(path)]) == 2
    assert "Config tidak valid" in capsys.readouterr().err


def test_run_stub_returns_zero(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_config(valid_config_text)
    assert main(["--config", str(path)]) == 0
    assert "belum diimplementasikan" in capsys.readouterr().out
