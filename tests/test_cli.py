"""Test untuk CLI — flag, orkestrasi internal, dan integrasi dasar.

Sebisa mungkin diuji offline; ``Scraper`` di-mock untuk menghindari browser.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from job_scraper.cli import _describe_output, _print_summary, _process_cards, build_parser, main
from job_scraper.config import (
    AppConfig,
    ExcelConfig,
    OutputConfig,
    ScoringConfig,
    SearchConfig,
)
from job_scraper.exceptions import CaptchaDetectedError, ScraperError, WriterError
from job_scraper.models import Job
from job_scraper.parsers import parse_search_page
from job_scraper.storage import SeenJobsDB

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_HTML = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
DETAIL_HTML = (FIXTURES / "detail_01.html").read_text(encoding="utf-8")

# --------------------------------------------------------------------------- #
# Helper: FakeSource menggantikan Scraper (mengembalikan fixture, tanpa browser)
# --------------------------------------------------------------------------- #


class _FakeSource:
    """Pengganti ``Scraper`` yang mengembalikan fixture HTML."""

    def __init__(self, cfg: object) -> None:
        self._fail_detail = False

    def __enter__(self) -> _FakeSource:
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def search_page_html(self, keyword: str, location: str, page: int) -> str:
        return SEARCH_HTML

    def fetch_detail_html(self, url: str) -> str:
        if self._fail_detail:
            raise ScraperError("network error")
        return DETAIL_HTML


# --------------------------------------------------------------------------- #
# Flag parsing
# --------------------------------------------------------------------------- #


def test_build_parser_dry_run() -> None:
    args = build_parser().parse_args(["--dry-run"])
    assert args.dry_run is True


def test_build_parser_limit() -> None:
    args = build_parser().parse_args(["--limit", "10"])
    assert args.limit == 10


def test_build_parser_headed() -> None:
    args = build_parser().parse_args(["--headed"])
    assert args.headed is True


def test_build_parser_reset_rejected() -> None:
    args = build_parser().parse_args(["--reset-rejected"])
    assert args.reset_rejected is True


def test_build_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.dry_run is False
    assert args.limit == 0
    assert args.headed is False
    assert args.reset_rejected is False


# --------------------------------------------------------------------------- #
# _print_summary
# --------------------------------------------------------------------------- #


def test_print_summary(capsys: pytest.CaptureFixture[str]) -> None:
    from collections import Counter

    _print_summary(
        Counter({"dilihat": 42, "baru": 15, "lolos": 5, "ditolak": 10, "duplikat": 27}),
        [],
        "data/jobs.xlsx",
        dry_run=False,
    )
    out = capsys.readouterr().out
    assert "Dilihat:       42" in out
    assert "Baru:          15" in out
    assert "Lolos:      5" in out


def test_print_summary_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    from collections import Counter

    _print_summary(Counter(), [], "data/jobs.xlsx", dry_run=True)
    assert "dry-run" in capsys.readouterr().out


def test_print_summary_no_matches(capsys: pytest.CaptureFixture[str]) -> None:
    from collections import Counter

    _print_summary(Counter({"dilihat": 3, "baru": 3}), [], "data/jobs.xlsx", dry_run=False)
    assert "tidak ada lowongan baru" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# _describe_output
# --------------------------------------------------------------------------- #


def test_describe_output_excel() -> None:
    cfg = AppConfig(
        search=SearchConfig(keywords=["test"], locations=["a"]),
        output=OutputConfig(type="excel", excel=ExcelConfig(file_path="hasil.xlsx")),
    )
    assert _describe_output(cfg) == "hasil.xlsx"


def test_describe_output_sheets() -> None:
    from job_scraper.config import GoogleSheetsConfig

    cfg = AppConfig(
        search=SearchConfig(keywords=["test"], locations=["a"]),
        output=OutputConfig(
            type="google_sheets",
            google_sheets=GoogleSheetsConfig(spreadsheet_id="abc123", worksheet_name="Sheet1"),
        ),
    )
    assert "abc123" in _describe_output(cfg)


# --------------------------------------------------------------------------- #
# _process_cards (intgrasi dengan db nyata + filter)
# --------------------------------------------------------------------------- #


@pytest.fixture
def make_cfg() -> AppConfig:
    """Config dengan min_score=0 agar semua lolos."""
    return AppConfig(
        search=SearchConfig(keywords=["developer"], locations=["Semarang"], fetch_detail=True),
        output=OutputConfig(type="excel", excel=ExcelConfig()),
        scoring=ScoringConfig(min_score=0),
    )


def test_process_cards_all_lolos(make_cfg: AppConfig, capsys: pytest.CaptureFixture[str]) -> None:
    from collections import Counter

    cards = parse_search_page(SEARCH_HTML)
    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    with SeenJobsDB(":memory:") as db:
        source = _FakeSource(None)
        _process_cards(cards, make_cfg, db, source, stats, new_matches, limit=3, dry_run=False)

        assert stats["dilihat"] == 3
        assert stats["baru"] == 3
        assert stats["duplikat"] == 0
        assert stats["lolos"] >= 1
        assert db.has(cards[0].job_id)
        assert db.get_status(cards[0].job_id) == "matched"


def test_process_cards_dry_run_skips_db(make_cfg: AppConfig) -> None:
    from collections import Counter

    cards = parse_search_page(SEARCH_HTML)
    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    with SeenJobsDB(":memory:") as db:
        source = _FakeSource(None)
        _process_cards(cards[:1], make_cfg, db, source, stats, new_matches, limit=0, dry_run=True)

        assert not db.has(cards[0].job_id)


def test_process_cards_deduplicates(make_cfg: AppConfig) -> None:
    from collections import Counter

    cards = parse_search_page(SEARCH_HTML)
    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    with SeenJobsDB(":memory:") as db:
        source = _FakeSource(None)
        # Proses kartu pertama dua kali
        _process_cards(cards[:1], make_cfg, db, source, stats, new_matches, limit=0, dry_run=False)
        _process_cards(cards[:1], make_cfg, db, source, stats, new_matches, limit=0, dry_run=False)

        assert stats["duplikat"] == 1
        assert len(new_matches) == 1


def test_process_cards_prefilter_rejects() -> None:
    """Judul mengandung 'senior' akan ditolak di pra-filter."""
    from collections import Counter

    from job_scraper.config import (
        AppConfig,
        FiltersConfig,
        OutputConfig,
        ScoringConfig,
        SearchConfig,
    )
    from job_scraper.models import Job

    cfg = AppConfig(
        search=SearchConfig(keywords=["test"], locations=["x"]),
        filters=FiltersConfig(exclude_title_keywords=["senior"]),
        scoring=ScoringConfig(),
        output=OutputConfig(type="excel", excel=ExcelConfig()),
    )
    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    with SeenJobsDB(":memory:") as db:
        source = _FakeSource(None)
        senior = Job(
            job_id="999",
            title="Senior Developer",
            company="PT A",
            location="Jakarta",
            url="https://id.jobstreet.com/job/999",
        )
        _process_cards([senior], cfg, db, source, stats, new_matches, limit=0, dry_run=False)

        assert db.get_status("999") == "rejected_title"
        assert stats["ditolak"] == 1
        assert stats["baru"] == 1


def test_process_cards_detail_fetch_failure_skips_card(make_cfg: AppConfig) -> None:
    from collections import Counter

    cards = parse_search_page(SEARCH_HTML)
    stats: Counter[str] = Counter()
    new_matches: list[Job] = []

    with SeenJobsDB(":memory:") as db:
        source = _FakeSource(None)
        source._fail_detail = True
        _process_cards(cards[:1], make_cfg, db, source, stats, new_matches, limit=0, dry_run=False)

        assert stats["baru"] == 1
        assert len(new_matches) == 0
        assert not db.has(cards[0].job_id)


# --------------------------------------------------------------------------- #
# main -- end-to-end (Scraper di-mock)
# --------------------------------------------------------------------------- #


def test_main_check_config_ok(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_config(valid_config_text)
    code = main(["--check-config", "--config", str(path)])
    assert code == 0
    assert "Config valid" in capsys.readouterr().out


def test_main_check_config_invalid(
    write_config: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_config("search: [")
    code = main(["--check-config", "--config", str(path)])
    assert code == 2
    assert "Config tidak valid" in capsys.readouterr().err


def test_main_dry_run_with_mocks(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Alur penuh dengan Scraper di-mock; dry-run tidak menulis."""
    monkeypatch.setattr("job_scraper.cli.Scraper", _FakeSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(valid_config_text)
    code = main(["--config", str(path), "--dry-run", "--limit", "5"])
    output = capsys.readouterr().out

    assert code == 0
    assert "Dilihat:       5" in output
    assert "dry-run" in output


def test_main_headed_overrides_config(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--headed mengubah cfg.scraper.headless menjadi False."""
    recorded: list[object] = []

    class _RecordingScraper:
        def __init__(self, cfg: object) -> None:
            recorded.append(cfg)

        def __enter__(self) -> _RecordingScraper:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            return "<html></html>"

        def fetch_detail_html(self, url: str) -> str:
            return "<html></html>"

    monkeypatch.setattr("job_scraper.cli.Scraper", _RecordingScraper)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(valid_config_text)
    main(["--config", str(path), "--headed", "--dry-run", "--limit", "1"])

    assert len(recorded) == 1
    assert recorded[0].headless is False  # type: ignore[attr-defined]


def test_main_reset_rejected_called(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--reset-rejected memanggil db.reset_rejected."""
    monkeypatch.setattr("job_scraper.cli.Scraper", _FakeSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    from job_scraper.storage import SeenJobsDB

    db_path = write_config("").parent / "_data" / "seen_jobs.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with SeenJobsDB(db_path) as db:
        from job_scraper.models import Job

        db.mark(
            Job(job_id="1", title="X", company="C", location="L", url="U"), status="rejected_title"
        )

    path = write_config(valid_config_text)
    code = main(["--config", str(path), "--reset-rejected", "--dry-run", "--limit", "1"])
    assert code == 0

    with SeenJobsDB(db_path) as db:
        assert db.has("1") is False


def test_main_handles_writer_error(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """WriterError dikembalikan sebagai exit code 1."""
    # Config minimal dengan min_score=0 agar ada lowongan lolos
    config_min = """
search:
  keywords: ["Backend Developer"]
  locations: ["Semarang"]
filters: {}
scoring:
  min_score: 0
output:
  type: "excel"
  excel:
    file_path: "data/jobs.xlsx"
scraper:
  delay_min_sec: 1
  delay_max_sec: 2
"""
    monkeypatch.setattr("job_scraper.cli.Scraper", _FakeSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    from job_scraper.writers import ExcelWriter

    def _fail_append(*args: object, **kwargs: object) -> None:
        raise WriterError("cannot write")

    monkeypatch.setattr(ExcelWriter, "append", _fail_append)

    path = write_config(config_min)
    code = main(["--config", str(path), "--limit", "10"])
    assert code == 1
    assert "cannot write" in capsys.readouterr().err


def test_main_empty_search_page_stops_pagination(
    write_config: Callable[[str], Path],
    valid_config_text: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Halaman hasil 0 kartu → pagination berhenti."""
    calls: list[str] = []

    class _NoCards:
        def __init__(self, *a: object) -> None:
            pass

        def __enter__(self) -> _NoCards:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            calls.append(f"page={page}")
            return "<html><body>no cards</body></html>"

        def fetch_detail_html(self, url: str) -> str:
            return "<html></html>"

    monkeypatch.setattr("job_scraper.cli.Scraper", _NoCards)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(valid_config_text)
    main(["--config", str(path), "--dry-run"])

    assert len(calls) == 1  # hanya halaman 1


# --------------------------------------------------------------------------- #
# M8 hardening tests
# --------------------------------------------------------------------------- #


_CONFIG_MIN = """
search:
  keywords: ["Backend Developer"]
  locations: ["Semarang"]
filters: {}
scoring:
  min_score: 0
output:
  type: "excel"
  excel:
    file_path: "jobs.xlsx"
scraper:
  delay_min_sec: 1
  delay_max_sec: 2
"""


def test_main_captcha_stops_run(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CaptchaDetectedError → exit 1."""

    class _CaptchaSource(_FakeSource):
        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            raise CaptchaDetectedError("challenge")

    monkeypatch.setattr("job_scraper.cli.Scraper", _CaptchaSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(_CONFIG_MIN)
    code = main(["--config", str(path), "--limit", "5"])
    assert code == 1
    assert "CAPTCHA" in capsys.readouterr().err


def test_main_scraper_error_breaks_pagination(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ScraperError dari halaman → log error + lanjut keyword berikutnya."""

    class _ErrorSource(_FakeSource):
        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            raise ScraperError("network broken")

    monkeypatch.setattr("job_scraper.cli.Scraper", _ErrorSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(_CONFIG_MIN)
    code = main(["--config", str(path), "--dry-run"])
    # Error per halaman → break pagination + lanjut; tapi 0 kartu → return 0
    assert code == 0


def test_main_structure_changed_stops_run(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """StructureChangedError dari parse → exit 1."""
    from job_scraper.exceptions import StructureChangedError

    class _BrokenSource(_FakeSource):
        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            return "<html><body>no cards</body></html>"

    monkeypatch.setattr("job_scraper.cli.Scraper", _BrokenSource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    # Patch parse so it crashes even on empty page
    monkeypatch.setattr(
        "job_scraper.cli.parse_search_page",
        lambda html: (_ for _ in ()).throw(StructureChangedError("bad")),
    )

    path = write_config(_CONFIG_MIN)
    code = main(["--config", str(path), "--limit", "5"])
    assert code == 1


def test_main_writer_error_backs_up_pending(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """WriterError → backup file dibuat."""
    from job_scraper.writers import ExcelWriter

    monkeypatch.setattr("job_scraper.cli.Scraper", _FakeSource)
    data_dir = write_config("").parent / "_data"
    monkeypatch.setattr("job_scraper.cli._DATA", data_dir)
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    def _fail_append(*a: object, **kw: object) -> None:
        raise WriterError("write failed")

    monkeypatch.setattr(ExcelWriter, "append", _fail_append)

    path = write_config(_CONFIG_MIN)
    code = main(["--config", str(path), "--limit", "10"])
    assert code == 1
    pending = list(data_dir.glob("pending_*.json"))
    assert len(pending) == 1
    data = json.loads(pending[0].read_text(encoding="utf-8"))
    assert len(data) >= 1


def test_main_zero_cards_alert(
    write_config: Callable[[str], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """0 kartu → peringatan dicetak."""

    class _EmptySource:
        def __init__(self, *a: object) -> None:
            pass

        def __enter__(self) -> _EmptySource:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def search_page_html(self, kw: str, loc: str, page: int) -> str:
            return "<html></html>"

        def fetch_detail_html(self, url: str) -> str:
            return "<html></html>"

    monkeypatch.setattr("job_scraper.cli.Scraper", _EmptySource)
    monkeypatch.setattr("job_scraper.cli._DATA", write_config("").parent / "_data")
    monkeypatch.setattr("job_scraper.cli._LOG_DIR", write_config("").parent / "_logs")

    path = write_config(_CONFIG_MIN)
    code = main(["--config", str(path), "--dry-run"])
    assert code == 0
    assert "tidak ada kartu" in capsys.readouterr().err.lower()
