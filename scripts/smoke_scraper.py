"""Smoketest manual scraper → parser (butuh internet + browser).

Jalankan (headed, karena JobStreet di balik Cloudflare):
    .\\.venv\\Scripts\\python.exe scripts\\smoke_scraper.py "Junior developer" "Jawa Barat"

Bukan bagian aplikasi (tidak di-unit-test).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from job_scraper.config import ScraperConfig
from job_scraper.parsers import apply_detail, parse_detail_page, parse_search_page
from job_scraper.scraper import Scraper


def main() -> int:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "Junior developer"
    location = sys.argv[2] if len(sys.argv) > 2 else "Jawa Barat"

    cfg = ScraperConfig(headless=False, delay_min_sec=1, delay_max_sec=2, page_timeout_sec=45)

    jobs = []
    with Scraper(cfg) as source:
        for html in source.iter_search_pages(keyword, location, max_pages=1):
            jobs = parse_search_page(html)
            break
        print(f"[search] '{keyword}' di '{location}' -> {len(jobs)} kartu")
        for job in jobs[:5]:
            print(
                f"  - {job.job_id} | {job.title} | {job.company} "
                f"| {job.location} | {job.salary_text}"
            )

        if jobs:
            detail_html = source.fetch_detail_html(jobs[0].url)
            detail = parse_detail_page(detail_html)
            merged = apply_detail(jobs[0], detail)
            description = merged.description or ""
            print(
                f"[detail] {merged.title} | work_type={merged.work_type} "
                f"| salary={merged.salary_text} | desc_len={len(description)}"
            )

    if not jobs:
        print("GAGAL: 0 kartu (struktur berubah / challenge belum lewat).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
