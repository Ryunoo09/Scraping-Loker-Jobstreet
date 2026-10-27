"""Smoketest scraper LinkedIn guest: ambil halaman nyata lalu hitung kartu.

Jalankan: .\\.venv\\Scripts\\python.exe scripts\\smoke_linkedin.py --pages 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bs4 import BeautifulSoup

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from linkedin_scraper.config import load_config  # noqa: E402
from linkedin_scraper.scraper import HttpSource  # noqa: E402


def main() -> int:
    """Ambil halaman kartu nyata dan laporkan jumlahnya."""
    parser = argparse.ArgumentParser(description="Smoketest scraper LinkedIn guest.")
    parser.add_argument("--config", default=str(_ROOT / "config_linkedin.example.yaml"))
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    keyword = cfg.search.keywords[0]
    total = 0

    with HttpSource(cfg.scraper, cfg.search) as source:
        for page in range(1, args.pages + 1):
            html = source.search_page_html(keyword, page)
            cards = BeautifulSoup(html, "html.parser").select("div.base-card")
            total += len(cards)
            print(f"halaman {page}: {len(html)} karakter, {len(cards)} kartu")

    print(f"total kartu: {total}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
