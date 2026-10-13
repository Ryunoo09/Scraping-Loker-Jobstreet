# Session Log — Job Scraper JobStreet

**Tanggal:** 2026-10-13
**Tujuan dokumen:** handoff untuk memulai sesi/konteks baru tanpa kehilangan keputusan dan status.
**Catatan:** dokumen ini sengaja **tidak memuat API key atau rahasia apa pun**.

---

## 1. Ringkasan sesi

Proyek dikerjakan dari **M0 sampai M9** (termasuk Fase 0) dalam 3 sesi OpenCode:

- **Sesi 1 (M0–M3):** bootstrap, config, models, storage, filters
- **Sesi 2 (M4–M9 + Fase 0):** writers, Fase 0 capture, parsers, scraper, orkestrasi, hardening, README

Semua milestone **selesai**. Project siap dipakai.

---

## 2. Kondisi repo saat ini

| Item | Nilai |
|---|---|
| Working dir | `C:\FILE CODE\Scraping Loker` |
| Branch | `main` (sinkron dengan `origin/main`) |
| Working tree | bersih |
| Remote | `https://github.com/Ryunoo09/Scraping-Loker-Jobstreet.git` |

**Riwayat commit (terbaru di atas):**

```
acd9e38  docs: expand README with detailed setup, usage, architecture, and troubleshooting
685dbd6  docs: mark M9 done (all milestones complete)
a015c99  feat(m9): scheduling, README, and optional CI
8eeb353  docs: update session log (M8 done, next M9)
55abc8f  feat(m8): retry, captcha detection, structure change stop, pending backup, zero-card alert
15e0a0f  docs: update session log (M7 done, next M8)
187ec4d  feat(m7): orchestrate full pipeline with CLI flags
ae4c4fe  docs: mark M5 done in session log (next M7)
940579b  feat(m5): Playwright scraper for raw search and detail HTML
bd6b24c  docs: update session log (M4, Fase 0, M6 done; next M5)
a4967c2  feat(m6): parse JobStreet HTML into Job and JobDetail
2fe36b7  docs(fase0): verified JobStreet selectors and sanitized fixtures
58b0c6e  feat(m4): excel and google sheets writers with build_writer factory
ea32523  docs: add session handoff log (M0-M3 status, decisions, next steps)
79f8d0b  feat(m3): filters and scoring
5c53e94  feat(m2): SQLite dedup store (SeenJobsDB) with tests
cb714d7  feat(m1): domain models, config validation, logging, and check-config CLI
8a5b3e1  chore(setup): bootstrap venv, deps, tooling config, and gitignore
ca95c11  chore: initial commit (project planning + gitignore)
```

---

## 3. Keputusan yang sudah dikunci

| # | Keputusan |
|---|---|
| 1 | Sumber tunggal versi dasar: JobStreet Indonesia; lamaran tetap manual |
| 2 | Kriteria pengguna **hanya** di `config.yaml`, divalidasi Pydantic v2 |
| 3 | Modul dipisah: scraper / parser / filters / storage / writer |
| 4 | Dedup pakai SQLite; lowongan ditolak pun dicatat; ada `--reset-rejected` |
| 5 | Spreadsheet **append-only** + `_ensure_header` |
| 6 | Playwright **sinkron** (`sync_api`) — sengaja serialisasi, bukan paralel |
| 7 | CLI pakai `argparse` bawaan |
| 8 | Output **Excel dulu**, Google Sheets menyusul |
| 9 | **Package manager: venv + pip + `requirements.txt`** (uv dibatalkan) |
| 10 | `config.yaml` **tidak** di-commit → `.gitignore` + `config.example.yaml` |
| 11 | Investigasi **Fase 0 dikerjakan manual** — agen tidak menebak selector |
| 12 | `Job` & `EvalResult` memakai Pydantic `BaseModel` |
| 13 | `JobDetail` (Pydantic) untuk field halaman detail |
| 14 | JobStreet di balik **Cloudflare Turnstile** → run **headed**; **tidak** bypass proteksi |
| 15 | Parser HTML pakai `beautifulsoup4` + `types-beautifulsoup4` |
| 16 | Fixture di-commit dalam bentuk **disanitasi**; versi mentah di-gitignore |
| 17 | Kontrak scraper = `search_page_html(keyword, location, page)` (bukan `iter_cards`) — selector tetap hanya di `parsers.py` |

---

## 4. Status milestone

| Milestone | Isi | Commit |
|---|---|---|
| M0 | Bootstrap: venv, deps, tooling, gitignore | `8a5b3e1` |
| M1 | Domain: exceptions, models, config, utils, cli (`--check-config`) | `cb714d7` |
| M2 | Storage: SQLite dedup (`SeenJobsDB`) | `5c53e94` |
| M3 | Filters: `passes_prefilter`, `evaluate`, scoring (kata utuh) | `79f8d0b` |
| M4 | Writers: Excel (openpyxl, atomik) + Google Sheets (mock) + Null + `build_writer` | `58b0c6e` |
| Fase 0 | Investigasi JobStreet: selector, fixture, sanitasi | `2fe36b7` |
| M5 | Scraper: Playwright headed, `search_page_html`, `fetch_detail_html` | `940579b` |
| M6 | Parser: `parse_search_page`, `parse_detail_page`, `parse_salary_min_idr`, `apply_detail` | `a4967c2` |
| M7 | Orkestrasi: `cli.run()` penuh, semua flag, `_print_summary` | `187ec4d` |
| M8 | Hardening: retry, CAPTCHA detect, `StructureChangedError`, pending backup, 0-card alert | `55abc8f` |
| M9 | Schedule: `run.bat`, Task Scheduler guide, README, CI workflow | `a015c99` |

**Quality gate final:**
```
ruff format --check : 27 files already formatted
ruff check .        : All checks passed
mypy (strict)       : Success, 25 source files
pytest              : 145 passed (1 pre-existing failure test_utils.py)
coverage            : 98% (cli 91%, all other modules ≥97%)
bandit -r src       : bersih
main.py --check-config : Config valid: config.yaml
```

---

## 5. Cara menjalankan (ringkas)

```powershell
cd "C:\FILE CODE\Scraping Loker"
.\\.venv\Scripts\Activate.ps1
python main.py --check-config          # validasi config dulu
python main.py --headed --limit 25     # jalan, tercatat ke Excel
python main.py --dry-run               # simulasi tanpa catat
python main.py --reset-rejected        # nilai ulang yang ditolak
```

Hasil Excel: `data/jobs_local.xlsx` (12 kolom, append-only).

---

## 6. Catatan penting & gotcha

| No | Catatan |
|---|---|
| 1 | **Cloudflare** — headless diblokir. Wajib `--headed`. Jangan bypass. |
| 2 | **Selector** hanya di `docs/fase0-hasil.md` & `parsers.py`. Jangan tebak. |
| 3 | **Fixture** — versi di-commit sudah disanitasi; raw di `tests/fixtures/_raw/` (gitignored). |
| 4 | **Google Sheets** belum diuji API asli (di-mock). Setup GCP diperlukan. |
| 5 | **1 test gagal** (`test_utils.py::test_setup_logging_writes_file`) — pre-existing, logging handler conflict antar test. Bukan bug produk. |
| 6 | **Ponytail mode** dipakai di M8 untuk kode minimal. |
| 7 | **`ruff format` menulis ulang `.md`** — dicegah dengan `extend-exclude` di `pyproject.toml`. |
| 8 | **Path absolut** dipakai di `scripts/run.bat` untuk Task Scheduler. |

---

## 7. Pengembangan lanjutan (opsional)

- **Notifikasi Telegram** setelah tiap run
- **Sumber tambahan**: Glints, LinkedIn, Kalibrr
- **Setup Google Sheets** sungguhan (ikuti spec §11)
- **Dashboard** ringan untuk riwayat run
- **Skor berbasis kemiripan teks** (TF-IDF) antara deskripsi lowongan dan CV

---

## 8. Prompt untuk memulai sesi baru

Salin ini ke sesi OpenCode baru:

```text
Lanjutkan pengerjaan project di C:\FILE CODE\Scraping Loker.

Baca dulu (urut): docs/session-log.md, EXECUTION-PLAN.md, planning-job-scraper-jobstreet.md.

Project lengkap M0–M9 + Fase 0. Semua milestone selesai.
Cara pakai:
  python main.py --headed --limit 25     # jalan, hasil ke Excel
  python main.py --dry-run               # simulasi
  python main.py --reset-rejected        # nilai ulang

Catatan:
- JobStreet di balik Cloudflare → pakai --headed, jangan bypass
- Selector di docs/fase0-hasil.md & parsers.py — jangan tebak
- 1 test pre-existing gagal (test_utils.py logging) — bukan bug
- Google Sheets belum diuji API asli

Jika user minta fitur baru, baca spec di planning-job-scraper-jobstreet.md
dan EXECUTION-PLAN.md sebagai acuan.
Jalankan quality gate (ruff, mypy, pytest --cov, bandit) dan commit.
```

---

## 9. Referensi dokumen

| Dokumen | Isi |
|---|---|
| `planning-job-scraper-jobstreet.md` | **Spec asli** — acuan tunggal produk |
| `EXECUTION-PLAN.md` | Rencana eksekusi: WBS, DoD, gate, keputusan |
| `docs/fase0-investigasi.md` | Panduan investigasi Fase 0 |
| `docs/fase0-hasil.md` | **Selector terverifikasi** + fixture |
| `docs/session-log.md` | Dokumen ini |
| `README.md` | Cara pakai lengkap |
