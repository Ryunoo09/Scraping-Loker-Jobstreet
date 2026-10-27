"""Command-line interface scraper LinkedIn.

``main()`` membaca argumen lalu menjalankan salah satu:

* ``--check-config`` — validasi config lalu keluar.
* ``run()`` — alur penuh: config → scraper → parser → dedup → filter → writer.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from .config import AppConfig, load_config
from .exceptions import (
    ConfigError,
    LinkedInError,
    RateLimitError,
    ScraperError,
    StructureChangedError,
    WriterError,
)
from .filters import evaluate, passes_prefilter
from .models import JobLinkedIn
from .parsers import apply_detail, parse_detail_page, parse_search_page
from .scraper import HttpSource, JobSource
from .storage import SeenJobsDB
from .utils import setup_logging
from .writers import build_writer

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = "config_linkedin.yaml"

# Direktori proyek (resolved dari ``src/linkedin_scraper/cli.py``).
_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA = _ROOT / "data"
_LOG_DIR = _ROOT / "logs"


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
    parser.add_argument(
        "--dry-run", action="store_true", help="simulasi tanpa menulis ke db/spreadsheet"
    )
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N", help="batasi jumlah lowongan yang diproses"
    )
    parser.add_argument(
        "--reset-rejected",
        action="store_true",
        help="hapus catatan lowongan yang ditolak, biar dinilai ulang",
    )
    return parser


def _print_summary(
    stats: Counter[str],
    matches: list[JobLinkedIn],
    output_desc: str,
    *,
    dry_run: bool,
) -> None:
    """Cetak ringkasan akhir ke terminal."""
    print("=" * 40)
    print("Ringkasan LinkedIn:")
    print(f"  Dilihat:       {stats.get('dilihat', 0)}")
    print(f"  Baru:          {stats.get('baru', 0)}")
    for key in ("duplikat", "ditolak", "lolos"):
        count = stats.get(key, 0)
        if count:
            print(f"  {key.capitalize()}:      {count}")
    if dry_run:
        print("  Ditulis:       (dry-run, tidak ditulis)")
    elif matches:
        print(f"  Ditulis:       {len(matches)} -> {output_desc}")
    else:
        print("  Ditulis:       0 (tidak ada lowongan baru yang lolos)")
    print("=" * 40)


def run(config_path: Path, args: argparse.Namespace) -> int:
    """Jalankan alur scraping penuh."""
    cfg = load_config(config_path)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging(_LOG_DIR / "linkedin_scraper.log")
    logger.info("LinkedIn scraper dimulai (config=%s)", config_path)

    stats: Counter[str] = Counter()
    matches: list[JobLinkedIn] = []

    _DATA.mkdir(parents=True, exist_ok=True)
    with SeenJobsDB(_DATA / "linkedin_seen.db") as db:
        if args.reset_rejected:
            removed = db.reset_rejected()
            logger.info("Reset %d rejected lowongan", removed)

        writer = build_writer(cfg.output, dry_run=args.dry_run)

        with HttpSource(cfg.scraper, cfg.search) as source:
            for keyword in cfg.search.keywords:
                for page in range(1, cfg.search.max_pages_per_query + 1):
                    if _budget_used(stats, args.limit):
                        break
                    try:
                        page_html = source.search_page_html(keyword, page)
                    except RateLimitError as exc:
                        logger.error("Rate limit: %s — menghentikan run.", exc)
                        return 1
                    except ScraperError as exc:
                        logger.error("Gagal memuat halaman %d (%s): %s", page, keyword, exc)
                        break

                    try:
                        cards = parse_search_page(page_html)
                    except StructureChangedError as exc:
                        logger.error(
                            "Struktur LinkedIn berubah (halaman %d): %s — berhenti.",
                            page,
                            exc,
                        )
                        return 1
                    if not cards:
                        logger.info("0 kartu di halaman %d (%s) — hentikan.", page, keyword)
                        break

                    _process_cards(
                        cards=cards,
                        cfg=cfg,
                        db=db,
                        source=source,
                        stats=stats,
                        matches=matches,
                        limit=args.limit,
                        dry_run=args.dry_run,
                    )

    if matches and not args.dry_run:
        try:
            writer.append(matches)
        except WriterError as exc:
            logger.exception("Gagal menulis hasil: %s", exc)
            return 1

    _print_summary(stats, matches, _describe_output(cfg), dry_run=args.dry_run)

    if stats.get("dilihat", 0) == 0:
        msg = "⚠️  Tidak ada kartu di semua pencarian — endpoint guest mungkin berubah."
        logger.warning(msg)
        print(msg, file=sys.stderr)

    return 0


def _budget_used(stats: Counter[str], limit: int) -> bool:
    """``True`` bila batas ``--limit`` sudah tercapai."""
    return bool(limit and stats["dilihat"] >= limit)


def _process_cards(
    cards: list[JobLinkedIn],
    cfg: AppConfig,
    db: SeenJobsDB,
    source: JobSource,
    stats: Counter[str],
    matches: list[JobLinkedIn],
    limit: int,
    dry_run: bool,
) -> None:
    """Proses satu halaman kartu: dedup, pra-filter, detail, filter, scoring."""
    for job in cards:
        if _budget_used(stats, limit) or stats["dilihat"] >= cfg.scraper.max_jobs_per_run:
            return

        stats["dilihat"] += 1

        if db.has(job.job_id):
            stats["duplikat"] += 1
            continue

        stats["baru"] += 1

        if not passes_prefilter(job, cfg.filters):
            if not dry_run:
                db.mark(job, status="rejected_title")
            stats["ditolak"] += 1
            continue

        if cfg.search.fetch_detail:
            job = _with_detail(job, source)

        result = evaluate(job, cfg)

        if result.passed:
            job = job.model_copy(update={"score": result.score})
            matches.append(job)
            if not dry_run:
                db.mark(job, status="matched")
            stats["lolos"] += 1
        else:
            if not dry_run:
                db.mark(job, status=f"rejected_{result.reason}")
            stats["ditolak"] += 1


def _with_detail(job: JobLinkedIn, source: JobSource) -> JobLinkedIn:
    """Ambil detail best-effort; bila gagal, kembalikan data kartu apa adanya."""
    try:
        detail_html = source.fetch_detail_html(job.job_id)
    except ScraperError as exc:
        logger.warning("Gagal ambil detail %s: %s", job.job_id, exc)
        return job
    return apply_detail(job, parse_detail_page(detail_html))


def _describe_output(cfg: AppConfig) -> str:
    """Kembalikan deskripsi output (path atau spreadsheet ID)."""
    out = cfg.output
    if out.type == "excel" and out.excel:
        return out.excel.file_path
    if out.type == "google_sheets" and out.google_sheets:
        return f"Sheets({out.google_sheets.spreadsheet_id})"
    return str(out.type)


def main(argv: Sequence[str] | None = None) -> int:
    """Titik masuk CLI; exit code 0 sukses, 2 config invalid, 1 error runtime."""
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

    try:
        return run(config_path, args)
    except LinkedInError as exc:
        logger.exception("LinkedIn scraper gagal: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
