"""Command-line interface (argparse).

``main()`` membaca argumen lalu menjalankan salah satu:

* ``--check-config`` — validasi config lalu keluar.
* ``run()`` — alur penuh: config → scraper → parser → dedup → filter → scoring → writer
  (spec §8.1, EXECUTION-PLAN §7.1-7.4).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from .config import AppConfig, load_config
from .exceptions import (
    CaptchaDetectedError,
    ConfigError,
    JobScraperError,
    ScraperError,
    StructureChangedError,
    WriterError,
)
from .filters import evaluate, passes_prefilter
from .models import Job
from .parsers import apply_detail, parse_detail_page, parse_search_page
from .scraper import JobSource, Scraper
from .storage import SeenJobsDB
from .utils import random_delay, setup_logging
from .writers import build_writer

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = "config.yaml"

# Direktori proyek (resolved dari lokasi module ini: src/job_scraper/cli.py).
_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA = _ROOT / "data"
_LOG_DIR = _ROOT / "logs"


def build_parser() -> argparse.ArgumentParser:
    """Bangun parser argumen dengan semua flag (spec §8 Fase 7)."""
    parser = argparse.ArgumentParser(
        prog="job-scraper",
        description="Mengumpulkan lowongan JobStreet yang cocok ke spreadsheet.",
    )
    parser.add_argument("--config", default=str(_ROOT / DEFAULT_CONFIG), help="path ke config.yaml")
    parser.add_argument("--check-config", action="store_true", help="validasi config lalu keluar")
    parser.add_argument(
        "--dry-run", action="store_true", help="simulasi tanpa menulis ke db/spreadsheet"
    )
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N", help="batasi jumlah lowongan yang diproses"
    )
    parser.add_argument("--headed", action="store_true", help="tampilkan browser (headless=false)")
    parser.add_argument(
        "--reset-rejected",
        action="store_true",
        help="hapus catatan lowongan yang ditolak, biar dinilai ulang",
    )
    return parser


def _print_summary(
    stats: Counter[str],
    new_matches: list[Job],
    output_desc: str,
    *,
    dry_run: bool,
) -> None:
    """Cetak ringkasan akhir ke terminal."""
    print("=" * 40)
    print("Ringkasan:")
    print(f"  Dilihat:       {stats.get('dilihat', 0)}")
    print(f"  Baru:          {stats.get('baru', 0)}")
    for key in ("duplikat", "ditolak", "lolos"):
        count = stats.get(key, 0)
        if count:
            print(f"  {key.capitalize()}:      {count}")
    if dry_run:
        print("  Ditulis:       (dry-run, tidak ditulis)")
    elif new_matches:
        print(f"  Ditulis:       {len(new_matches)} -> {output_desc}")
    else:
        print("  Ditulis:       0 (tidak ada lowongan baru yang lolos)")
    print("=" * 40)


def _backup_pending(jobs: list[Job]) -> None:
    """Simpan lowongan yang gagal ditulis ke file JSON cadangan."""
    if not jobs:
        return
    _DATA.mkdir(parents=True, exist_ok=True)
    data = [j.model_dump(mode="json") for j in jobs]
    path = _DATA / f"pending_{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Cadangan %d lowongan ke %s", len(jobs), path)


def _drain_pending(writer: object) -> None:
    """Tulis ulang lowongan dari file cadangan run sebelumnya."""
    for path in sorted(_DATA.glob("pending_*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            jobs = [Job.model_validate(j) for j in raw]
            writer.append(jobs)  # type: ignore[attr-defined]
            path.unlink()
            logger.info("Memulihkan %d lowongan dari %s", len(jobs), path.name)
        except (OSError, WriterError) as exc:
            logger.warning("Gagal memulihkan %s: %s", path.name, exc)


def run(config_path: Path, args: argparse.Namespace) -> int:
    """Jalankan alur scraping penuh (spec §8.1).

    Returns:
        Exit code (0 sukses, 1 ada error).
    """
    cfg = load_config(config_path)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging(_LOG_DIR / "scraper.log")
    logger.info("Job-scraper dimulai (config=%s)", config_path)

    if args.headed:
        cfg.scraper.headless = False

    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    db_path = _DATA / "seen_jobs.db"
    _DATA.mkdir(parents=True, exist_ok=True)

    with SeenJobsDB(db_path) as db:
        if args.reset_rejected:
            removed = db.reset_rejected()
            logger.info("Reset %d rejected lowongan", removed)

        writer = build_writer(cfg.output, dry_run=args.dry_run)

        if not args.dry_run:
            _drain_pending(writer)

        with Scraper(cfg.scraper) as source:
            for keyword in cfg.search.keywords:
                for location in cfg.search.locations:
                    pagination_stopped = False
                    for page_no in range(1, cfg.search.max_pages_per_query + 1):
                        if pagination_stopped or (args.limit and stats["dilihat"] >= args.limit):
                            break

                        try:
                            page_html = source.search_page_html(keyword, location, page_no)
                        except CaptchaDetectedError as exc:
                            logger.error("CAPTCHA terdeteksi: %s — menghentikan run.", exc)
                            return 1
                        except ScraperError as exc:
                            logger.error(
                                "Gagal memuat halaman %d (%s/%s): %s",
                                page_no,
                                keyword,
                                location,
                                exc,
                            )
                            break

                        try:
                            cards = parse_search_page(page_html)
                        except StructureChangedError as exc:
                            logger.error(
                                "Struktur JobStreet berubah (halaman %d): %s"
                                " — menghentikan scraping",
                                page_no,
                                exc,
                            )
                            return 1
                        if not cards:
                            logger.info(
                                "0 kartu di halaman %d (%s/%s) — hentikan pagination",
                                page_no,
                                keyword,
                                location,
                            )
                            pagination_stopped = True
                            continue

                        if page_no < cfg.search.max_pages_per_query:
                            random_delay(cfg.scraper.delay_min_sec, cfg.scraper.delay_max_sec)

                        _process_cards(
                            cards=cards,
                            cfg=cfg,
                            db=db,
                            source=source,
                            stats=stats,
                            new_matches=new_matches,
                            limit=args.limit,
                            dry_run=args.dry_run,
                        )

                        if args.limit and stats["dilihat"] >= args.limit:
                            break

    if new_matches:
        try:
            writer.append(new_matches)
            stats["ditulis"] = len(new_matches)
        except WriterError as exc:
            logger.exception("Gagal menulis hasil: %s", exc)
            _backup_pending(new_matches)
            return 1

    output_desc = _describe_output(cfg)
    _print_summary(stats, new_matches, output_desc, dry_run=args.dry_run)

    if stats.get("dilihat", 0) == 0:
        msg = (
            "⚠️  Tidak ada kartu di semua pencarian"
            " — kemungkinan scraper rusak atau JobStreet berubah."
        )
        logger.warning(msg)
        print(msg, file=sys.stderr)

    return 0


def _process_cards(
    cards: list[Job],
    cfg: AppConfig,
    db: SeenJobsDB,
    source: JobSource,
    stats: Counter[str],
    new_matches: list[Job],
    limit: int,
    dry_run: bool,
) -> None:
    """Proses satu halaman kartu: dedup, pra-filter, detail, filter, scoring."""
    for job in cards:
        if limit and stats["dilihat"] >= limit:
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
            try:
                detail_html = source.fetch_detail_html(job.url)
            except ScraperError as exc:
                logger.warning("Gagal ambil detail %s: %s", job.job_id, exc)
                continue
            detail = parse_detail_page(detail_html)
            job = apply_detail(job, detail)

        result = evaluate(job, cfg)

        if result.passed:
            job.score = result.score
            new_matches.append(job)
            if not dry_run:
                db.mark(job, status="matched")
            stats["lolos"] += 1
        else:
            if not dry_run:
                db.mark(job, status=f"rejected_{result.reason}")
            stats["ditolak"] += 1


def _describe_output(cfg: AppConfig) -> str:
    """Kembalikan deskripsi output (path atau spreadsheet ID)."""
    out = cfg.output
    if out.type == "excel" and out.excel:
        return out.excel.file_path
    if out.type == "google_sheets" and out.google_sheets:
        return f"Sheets({out.google_sheets.spreadsheet_id})"
    return str(out.type)


def main(argv: Sequence[str] | None = None) -> int:
    """Titik masuk CLI.

    Args:
        argv: Argumen baris perintah; ``None`` berarti ``sys.argv``.

    Returns:
        Exit code (0 sukses, 1 error runtime, 2 config invalid).
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

    try:
        return run(config_path, args)
    except JobScraperError as exc:
        logger.exception("Job-scraper gagal: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
