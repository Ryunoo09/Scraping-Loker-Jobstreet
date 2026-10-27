"""Titik masuk: ``python linkedin_main.py [opsi]``."""

from __future__ import annotations

import sys
from pathlib import Path

# Pastikan package `linkedin_scraper` di src/ bisa di-import tanpa perlu install.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from linkedin_scraper.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
