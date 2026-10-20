"""Skrip sekali-pakai: ambil fixture HTML mentah JobStreet untuk Fase 0.

Jalankan: .\\.venv\\Scripts\\python.exe scripts\\capture_fase0.py

Menghasilkan (apa adanya / raw, tidak dibersihkan):
- tests/fixtures/search_page_01.html  -> halaman hasil pencarian
- tests/fixtures/detail_01.html       -> halaman detail satu lowongan

Catatan: JobStreet dilindungi Cloudflare Turnstile. Skrip ini **tidak** mencoba
melewati proteksi; ia menjalankan browser sungguhan (headed) dan menunggu sampai
halaman hasil benar-benar termuat (kamu boleh menyelesaikan verifikasi manual bila
muncul). Skrip ini bukan bagian dari aplikasi (tidak di-unit-test).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

SEARCH_URL = "https://id.jobstreet.com/id/Junior-developer-jobs/in-Jawa-Barat"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
RAW_DIR = FIXTURES / "_raw"  # mentah (gitignored) — buang sebelum commit

# Fixture mentah memuat token pelacak & key dari sesi browser (mis. key_live_...).
# Versi yang disimpan ke tests/fixtures/ disanitasi: DOM dipertahankan, script dibuang.
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_SOL = re.compile(r"#sol=[0-9a-zA-Z]+")
_SOL_META = re.compile(r'\sdata-(?:search-)?sol-meta="[^"]*"')
_LIVE_KEY = re.compile(r"key_live_[A-Za-z0-9]+")
_TRACKING_ATTR = re.compile(r'\s(?:nonce|data-run-click-only)="[^"]*"')

# --- Cuplikan waktu posting pasti (Fase 0 §2.1) ----------------------------- #
# Blok window.SEEK_REDUX_DATA di <script data-automation="server-state"> memuat
# "listingDate" (ISO 8601 UTC) per lowongan. Fixture yang disimpan hanya memuat
# tiga kunci per lowongan supaya kecil dan bebas token.
LISTING_DATES_FIXTURE = "listing_dates_01.html"
_SERVER_STATE = re.compile(
    r'<script[^>]*data-automation="server-state"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_REDUX_ASSIGN = re.compile(r"window\.SEEK_REDUX_DATA\s*=\s*")
_JOB_KEYS = ("id", "listingDate", "listingDateDisplay")


def _sanitize(html: str) -> str:
    """Buang script/token pelacak, pertahankan struktur DOM untuk test parser."""
    html = _SCRIPT.sub("<!-- script removed -->", html)
    html = _STYLE.sub("<!-- style removed -->", html)
    html = _SOL_META.sub("", html)
    html = _SOL.sub("", html)
    html = _LIVE_KEY.sub("REDACTED", html)
    return _TRACKING_ATTR.sub("", html)


def _save_fixture(name: str, html: str) -> None:
    """Simpan versi mentah ke ``_raw/`` dan versi bersih ke ``tests/fixtures/``."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / name).write_text(html, encoding="utf-8")
    (FIXTURES / name).write_text(_sanitize(html), encoding="utf-8")


def _balanced_object(text: str, start: int) -> str | None:
    """Ambil literal objek JSON seimbang (mulai ``{`` pertama pada/atau setelah ``start``)."""
    index = text.find("{", start)
    if index < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for position in range(index, len(text)):
        char = text[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[index : position + 1]
    return None


def _find_jobs(
    node: Any, path: tuple[str | int, ...] = ()
) -> tuple[tuple[str | int, ...], list[Any]] | None:
    """Cari list objek lowongan pertama (semua itemnya punya ``listingDate``)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, dict) and "listingDate" in item for item in value)
            ):
                return (*path, key), value
            found = _find_jobs(value, (*path, key))
            if found is not None:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _find_jobs(value, (*path, index))
            if found is not None:
                return found
    return None


def _nest(path: tuple[str | int, ...], leaf: Any) -> Any:
    """Bungkus ``leaf`` kembali ke jalur bersarang (cermin struktur asli)."""
    node = leaf
    for key in reversed(path):
        node = {key: node} if isinstance(key, str) else [node]
    return node


def listing_dates_fixture(search_html: str) -> str:
    """Buat fixture HTML kecil: server-state dengan hanya ``id``+``listingDate``.

    Mempertahankan jalur bersarang asli (mis. ``results.results.jobs``) dan
    membuang seluruh token/sesi/lowongan lain, sehingga aman di-commit.
    """
    script = _SERVER_STATE.search(search_html)
    if script is None:
        raise SystemExit('Blok data-automation="server-state" tidak ditemukan.')
    assignment = _REDUX_ASSIGN.search(script.group(1))
    if assignment is None:
        raise SystemExit("window.SEEK_REDUX_DATA tidak ditemukan di dalam server-state.")
    literal = _balanced_object(script.group(1), assignment.end())
    if literal is None:
        raise SystemExit("Literal JSON SEEK_REDUX_DATA tidak lengkap.")
    data = json.loads(literal)
    found = _find_jobs(data)
    if found is None:
        raise SystemExit("Daftar lowongan dengan listingDate tidak ditemukan.")
    path, jobs = found
    reduced = [{key: job[key] for key in _JOB_KEYS if key in job} for job in jobs]
    payload = json.dumps(_nest(path, reduced), ensure_ascii=False)
    return (
        "<!DOCTYPE html>\n<html><head>\n"
        '<script data-automation="server-state">'
        f"window.SEEK_REDUX_DATA = {payload};"
        "</script>\n</head><body></body></html>\n"
    )


_AUTOMATION_LIST = "[data-automation]"
_JOB_LINKS = 'a[href*="/job/"]'
_GET_HREFS = "els => els.map(e => e.href)"
_CARD_SNIPPET_JS = """() => {
    const a = document.querySelector('a[href*="/job/"]');
    if (!a) return '';
    let node = a;
    for (let i = 0; i < 6 && node.parentElement; i++) node = node.parentElement;
    return node.outerHTML;
}"""


def _dump_automation(page: Page) -> None:
    """Cetak atribut data-automation yang muncul beserta jumlahnya."""
    getters = "els => els.map(e => e.getAttribute('data-automation'))"
    values = page.eval_on_selector_all(_AUTOMATION_LIST, getters)
    counts = Counter(str(value) for value in values)
    print("== data-automation yang ditemukan (value: jumlah) ==")
    for name, count in counts.most_common():
        print(f"  {count:4d}  {name}")


def _wait_for_job_links(
    page: Page, timeout_ms: int = 120_000, interval_ms: int = 2_000
) -> list[str]:
    """Tunggu sampai minimal satu link lowongan muncul (atau waktu habis)."""
    waited = 0
    while waited < timeout_ms:
        hrefs = [str(href) for href in page.eval_on_selector_all(_JOB_LINKS, _GET_HREFS)]
        if hrefs:
            return hrefs
        if waited == 0:
            print("Menunggu halaman hasil termuat (selesaikan verifikasi bila muncul)...")
        page.wait_for_timeout(interval_ms)
        waited += interval_ms
    return []


def _write_listing_dates_fixture(search_html: str) -> Path:
    """Tulis fixture waktu posting dari HTML halaman hasil; kembalikan path-nya."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / LISTING_DATES_FIXTURE
    path.write_text(listing_dates_fixture(search_html), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Ambil fixture HTML JobStreet (Fase 0).")
    parser.add_argument(
        "--headless", action="store_true", help="jalankan tanpa jendela (default: headed)"
    )
    parser.add_argument(
        "--from-raw",
        nargs="?",
        const=str(RAW_DIR / "search_page_01.html"),
        default=None,
        metavar="PATH",
        help="buat ulang fixture listing_dates dari HTML mentah yang sudah ada (tanpa jaringan)",
    )
    args = parser.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)

    if args.from_raw is not None:
        source = Path(args.from_raw)
        if not source.is_file():
            print(f"File mentah tidak ditemukan: {source}", file=sys.stderr)
            return 1
        path = _write_listing_dates_fixture(source.read_text(encoding="utf-8"))
        print(f"Fixture waktu posting dibuat dari {source}:\n  {path}")
        return 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=bool(args.headless))
        context = browser.new_context(locale="id-ID", viewport={"width": 1366, "height": 900})
        page = context.new_page()

        print(f"Membuka halaman hasil: {SEARCH_URL}")
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60_000)

        hrefs = _wait_for_job_links(page)
        page.mouse.wheel(0, 3_000)
        page.wait_for_timeout(2_000)

        _save_fixture("search_page_01.html", page.content())
        _write_listing_dates_fixture(page.content())
        print(f"\nJumlah link lowongan ditemukan: {len(hrefs)}")
        for href in list(dict.fromkeys(hrefs))[:5]:
            print(f"  - {href}")

        if not hrefs:
            print(
                "\nPERINGATAN: tidak ada link lowongan "
                "(kemungkinan challenge Cloudflare belum lewat).",
                file=sys.stderr,
            )
            _dump_automation(page)
            browser.close()
            return 1

        _dump_automation(page)
        snippet = page.evaluate(_CARD_SNIPPET_JS)
        print("\n== Potongan outerHTML sekitar kartu pertama (6000 char) ==")
        print(str(snippet)[:6000])

        detail_url = str(hrefs[0])
        print(f"\nMembuka detail: {detail_url}")
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5_000)
        _save_fixture("detail_01.html", page.content())

        print("\nSelesai. File yang ditulis:")
        print(f"  {FIXTURES / 'search_page_01.html'}  (bersih)")
        print(f"  {FIXTURES / 'detail_01.html'}       (bersih)")
        print(f"  {FIXTURES / LISTING_DATES_FIXTURE}  (bersih, waktu posting)")
        print(f"  {RAW_DIR}  (mentah, gitignored)")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
