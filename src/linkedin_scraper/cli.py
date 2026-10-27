"""Command-line interface scraper LinkedIn."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import load_config
from .exceptions import ConfigError

DEFAULT_CONFIG = "config_linkedin.yaml"

#: Direktori proyek (resolved dari ``src/linkedin_scraper/cli.py``).
_ROOT = Path(__file__).resolve().parent.parent.parent


def build_parser() -> argparse.ArgumentParser:
    """Bangun parser argumen."""
    parser = argparse.ArgumentParser(
        prog="linkedin-scraper",
        description="Mengumpulkan lowongan LinkedIn (guest) ke spreadsheet terpisah.",
    )
    parser.add_argument(
        "--config", default=str(_ROOT / DEFAULT_CONFIG), help="path ke config_linkedin.yaml"
    )
    parser.add_argument("--check-config", action="store_true", help="validasi config lalu keluar")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Titik masuk CLI; exit code 0 sukses, 2 config invalid."""
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)

    try:
        load_config(config_path)
    except ConfigError as exc:
        print(f"Config tidak valid: {exc}", file=sys.stderr)
        return 2

    if args.check_config:
        print(f"Config valid: {config_path}")
        return 0

    print("Pipeline scraping belum tersedia; gunakan --check-config.", file=sys.stderr)
    return 1
