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
import re
import sys
from collections import Counter
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Ambil fixture HTML JobStreet (Fase 0).")
    parser.add_argument(
        "--headless", action="store_true", help="jalankan tanpa jendela (default: headed)"
    )
    args = parser.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)

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
        print(f"  {RAW_DIR}  (mentah, gitignored)")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
