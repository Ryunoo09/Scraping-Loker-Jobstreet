"""Test untuk memuat dan memvalidasi ``config.yaml``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from job_scraper.config import load_config
from job_scraper.exceptions import ConfigError

EXCEL_BLOCK = '  type: "excel"\n  excel:\n    file_path: "data/jobs_local.xlsx"'


def test_valid_config_loads(write_config: Callable[[str], Path], valid_config_text: str) -> None:
    config = load_config(write_config(valid_config_text))
    assert config.search.keywords == ["Backend Developer"]
    assert config.output.type == "excel"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="tidak ditemukan"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_raises(write_config: Callable[[str], Path], valid_config_text: str) -> None:
    bad = valid_config_text.replace("locations:", "locations: [")
    with pytest.raises(ConfigError, match="YAML tidak valid"):
        load_config(write_config(bad))


def test_non_mapping_yaml_raises(write_config: Callable[[str], Path]) -> None:
    with pytest.raises(ConfigError, match="mapping"):
        load_config(write_config("- a\n- b\n"))


def test_empty_keywords_rejected(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text.replace('    - "Backend Developer"\n', "    []\n")
    with pytest.raises(ConfigError, match="keywords"):
        load_config(write_config(bad))


def test_min_score_out_of_range(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text.replace("min_score: 40", "min_score: 200")
    with pytest.raises(ConfigError, match="min_score"):
        load_config(write_config(bad))


def test_unknown_top_level_key_rejected(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text + "\nunexpected_key: 1\n"
    with pytest.raises(ConfigError, match="unexpected_key"):
        load_config(write_config(bad))


def test_delay_min_greater_than_max(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text.replace("delay_min_sec: 1", "delay_min_sec: 10")
    with pytest.raises(ConfigError, match="delay_min_sec"):
        load_config(write_config(bad))


def test_google_sheets_without_block_rejected(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text.replace(EXCEL_BLOCK, '  type: "google_sheets"')
    with pytest.raises(ConfigError, match="google_sheets"):
        load_config(write_config(bad))


def test_google_sheets_placeholder_rejected(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    block = (
        '  type: "google_sheets"\n'
        "  google_sheets:\n"
        '    spreadsheet_id: "ISI_ID_SPREADSHEET_DI_SINI"\n'
    )
    bad = valid_config_text.replace(EXCEL_BLOCK + "\n", block)
    with pytest.raises(ConfigError, match="placeholder"):
        load_config(write_config(bad))


def test_excel_without_block_rejected(
    write_config: Callable[[str], Path], valid_config_text: str
) -> None:
    bad = valid_config_text.replace(EXCEL_BLOCK, '  type: "excel"')
    with pytest.raises(ConfigError, match="excel"):
        load_config(write_config(bad))


def test_example_config_is_valid() -> None:
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    config = load_config(example)
    assert config.output.type == "excel"
