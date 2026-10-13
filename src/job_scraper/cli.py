"""Command-line interface (argparse).

Milestone M1 hanya menyediakan ``--config`` dan ``--check-config``. Opsi lain
(``--dry-run``, ``--limit``, ``--headed``, ``--reset-rejected``) ditambahkan di M7.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import load_config
from .exceptions import ConfigError

DEFAULT_CONFIG = "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    """Bangun parser argumen untuk aplikasi."""
    parser = argparse.ArgumentParser(
        prog="job-scraper",
        description="Mengumpulkan lowongan JobStreet yang cocok ke spreadsheet.",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path ke config.yaml")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validasi config lalu keluar tanpa scraping",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Titik masuk CLI.

    Args:
        argv: Argumen baris perintah; ``None`` berarti ``sys.argv``.

    Returns:
        Exit code (0 sukses, 2 config tidak valid).
    """
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

    print("Alur scraping belum diimplementasikan (menyusul di milestone berikutnya).")
    return 0
