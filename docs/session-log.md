# Session Log — Job Scraper JobStreet

**Tanggal:** 2026-10-13
**Tujuan dokumen:** handoff untuk memulai sesi/konteks baru tanpa kehilangan keputusan dan status.
**Catatan:** dokumen ini sengaja **tidak memuat API key atau rahasia apa pun**.

---

## 1. Ringkasan sesi

Dua topik dikerjakan dalam sesi ini:

1. **Menghubungkan project ke GitHub** → repo `github.com/Ryunoo09/Scraping-Loker-Jobstreet` (branch `main`).
2. **Pengerjaan project job-scraper** dengan agen `python-pro`: dibuat rencana eksekusi, lalu dikerjakan milestone M0–M3.
3. **Sampingan:** menghubungkan provider **Sumopod** (OpenAI-compatible) ke OpenCode, dan memecahkan error autentikasinya.

---

## 2. Kondisi repo saat ini

| Item | Nilai |
|---|---|
| Working dir | `C:\FILE CODE\Scraping Loker` |
| Branch | `main` (sinkron dengan `origin/main`) |
| Working tree | bersih (tidak ada perubahan tertunggak) |
| Remote | `https://github.com/Ryunoo09/Scraping-Loker-Jobstreet.git` |
| OpenCode | v2.0.26 |

**Riwayat commit (terbaru di atas):**

```
58b0c6e  feat(m4): excel and google sheets writers with build_writer factory
ea32523  docs: add session handoff log (M0-M3 status, decisions, next steps)
79f8d0b  feat(m3): filters and scoring
5c53e94  feat(m2): SQLite dedup store (SeenJobsDB) with tests
73752d6  chore: ignore local Sumopod model list file
9a687f7  fix(tooling): exclude markdown from ruff format; restore spec file
d2f8ddf  chore: normalize line endings per .gitattributes
cb714d7  feat(m1): domain models, config validation, logging, and check-config CLI
8a5b3e1  chore(setup): bootstrap venv, deps, tooling config, and gitignore
ca95c11  chore: initial commit (project planning + gitignore)
```

> Setelah ini menyusul commit `docs(fase0)` (fixture + laporan selector) dan
> `feat(m6)` (parser + test). Lihat `git log` untuk hash terbaru.

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
| 9 | **Package manager: venv + pip + `requirements.txt`** (uv dibatalkan atas pilihanmu) |
| 10 | `config.yaml` **tidak** di-commit → `.gitignore` + `config.example.yaml` |
| 11 | Investigasi **Fase 0 dikerjakan oleh user** (agen tidak menebak selector) |
| 12 | `Job` & `EvalResult` memakai Pydantic `BaseModel`; package di `src/job_scraper/` |
| 13 | `JobDetail` (Pydantic) untuk field khusus halaman detail (deskripsi/tipe kerja/gaji) |
| 14 | JobStreet di balik Cloudflare Turnstile → capture/run **headed**; **tidak** bypass proteksi |
| 15 | Parser HTML pakai `beautifulsoup4` + `types-beautifulsoup4` (di luar daftar spec §4) |
| 16 | Fixture di-commit dalam bentuk **disanitasi**; versi mentah di-gitignore |

---

## 4. Status milestone

| Milestone | Isi | Status | Commit |
|---|---|---|---|
| M0 | venv, deps, tooling config, gitignore | ✅ | `8a5b3e1` |
| M1 | exceptions, models, config, utils, cli (`--check-config`) | ✅ | `cb714d7` |
| M2 | `storage.py` (dedup SQLite) | ✅ | `5c53e94` |
| M3 | `filters.py` (pra-filter + filter wajib + scoring) | ✅ | `79f8d0b` |
| M4 | writers (Excel + Google Sheets + Null; `build_writer`) | ✅ | `58b0c6e` |
| Fase 0 | investigasi JobStreet (selector terverifikasi + fixture) | ✅ | (commit docs) |
| M6 | `parsers.py` (HTML → Job/JobDetail) + test fixture | ✅ | `a4967c2` |
| M5 | scraper Playwright (`scraper.py`, HTML mentah) | ✅ | (commit m5) |
| M7 | orkestrasi `cli.py` + `run()` penuh + flags | ✅ | `187ec4d` |
| M8 | hardening: retry, CAPTCHA, struktur berubah, pending backup, alert 0 | ✅ | `55abc8f` |
| M9 | penjadwalan + README + CI opsional | ✅ | (commit m9) |

**Quality gate saat ini:** ruff ✅ · `mypy --strict` ✅ (25 file) · pytest **145 passed** · coverage **98%** (cli 91%) · bandit ✅

> ✅ **Seluruh milestone dari M0–M9 + Fase 0 selesai.**

---

## 5. Struktur file saat ini

```
Scraping Loker/
├── main.py                     # entrypoint tipis → job_scraper.cli.main()
├── pyproject.toml              # config tooling saja (ruff/mypy/pytest/coverage)
├── requirements.txt            # deps runtime
├── requirements-dev.txt        # deps dev (pytest/ruff/mypy/bandit/hypothesis)
├── .python-version             # 3.12
├── .gitattributes              # normalisasi EOL
├── .gitignore
├── config.example.yaml         # contoh aman untuk di-commit
├── config.yaml                 # lokal, GITIGNORED
├── models_sumopod.md           # hasil /v1/models, GITIGNORED (referensi)
├── planning-job-scraper-jobstreet.md   # SPEC asli (jangan diubah)
├── EXECUTION-PLAN.md           # rencana eksekusi (dibuat agen)
├── docs/
│   ├── fase0-investigasi.md    # panduan investigasi Fase 0 (tugas user)
│   ├── fase0-hasil.md          # HASIL Fase 0: selector terverifikasi + fixture
│   └── session-log.md          # dokumen ini
├── .opencode/                  # GITIGNORED (dibaca OpenCode)
│   ├── opencode.jsonc          # konfigurasi provider Sumopod
│   ├── agents/                 # 17 agent
│   └── skills/                 # 14 skill
├── src/job_scraper/
│   ├── __init__.py
│   ├── exceptions.py           # ConfigError, ScraperError, StructureChangedError, ...
│   ├── models.py               # Job, EvalResult (Pydantic v2)
│   ├── config.py               # SearchConfig/FiltersConfig/ScoringConfig/OutputConfig/ScraperConfig/AppConfig + load_config
│   ├── utils.py                # setup_logging, random_delay, normalize_text
│   ├── storage.py              # SeenJobsDB
│   ├── filters.py              # passes_prefilter, evaluate
│   ├── parsers.py              # HTML → Job/JobDetail (selector dari Fase 0)
│   ├── scraper.py              # Playwright: ambil HTML mentah (tanpa selector)
│   ├── writers/
│   │   ├── __init__.py         # build_writer(cfg.output, dry_run=)
│   │   ├── base.py             # JobWriter Protocol, NullWriter, HEADERS, job_to_row
│   │   ├── excel.py            # ExcelWriter (openpyxl; simpan atomik, hyperlink)
│   │   └── sheets.py           # GoogleSheetsWriter (gspread; append_rows batch)
│   └── cli.py                  # --config, --check-config
└── tests/
    ├── conftest.py             # fixture: valid_config_text, write_config, cfg, make_job, make_config
    ├── test_config.py
    ├── test_models.py
    ├── test_cli.py
    ├── test_utils.py
    ├── test_storage.py
    ├── test_filters.py
    ├── test_writers.py
    ├── test_parsers.py         # berbasis fixture Fase 0 (offline)
    ├── test_scraper.py         # bagian murni scraper (URL builder) — offline
    └── fixtures/
        ├── search_page_01.html # halaman hasil (bersih; 30 kartu)
        ├── detail_01.html      # halaman detail (bersih)
        └── _raw/               # mentah, GITIGNORED (memuat token/key)

scripts/
├── capture_fase0.py            # utilitas: ambil + sanitasi fixture Fase 0
└── smoke_scraper.py            # smoketest manual scraper → parser (headed)
```

---

## 6. Perintah standar (quality gate)

```powershell
cd "C:\FILE CODE\Scraping Loker"
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # sekali saja
.\.venv\Scripts\ruff.exe format .
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe
.\.venv\Scripts\pytest.exe --cov=job_scraper --cov-report=term-missing
.\.venv\Scripts\bandit.exe -r src
.\.venv\Scripts\python.exe main.py --check-config
```

Milestone tidak dianggap selesai bila salah satu gate merah.

---

## 7. Detail teknis modul (yang sudah jadi)

### `config.py` (M1)
- Pydantic v2, `extra="forbid"` → salah ketik key langsung terdeteksi.
- Validasi penting: `keywords`/`locations` non-kosong; `min_score` 0–100; `delay_min_sec <= delay_max_sec`;
  `output.type` harus `"excel"` atau `"google_sheets"`; `spreadsheet_id` tidak boleh placeholder (`ISI_...`).
- `load_config(path)` → `AppConfig`; error dibungkus `ConfigError` dengan pesan field-level.

### `storage.py` (M2)
- Tabel `seen_jobs(job_id PK, title, company, url, status, score, first_seen)`; `PRAGMA journal_mode=WAL`.
- API: `has(id)`, `get_status(id)`, `mark(job, status)`, `reset_rejected()`, `close()`, context manager.
- `mark` idempotent: `INSERT ... ON CONFLICT DO UPDATE` (hanya `status`/`score`; `first_seen` tetap).
- Error sqlite3 diterjemahkan menjadi `StorageError`.

### `filters.py` (M3)
- `passes_prefilter(job, filters)` — **judul** cocok **kata utuh** (agar `lead` ≠ `leader`), **perusahaan** substring.
- `evaluate(job, cfg) -> EvalResult(passed, score, reason)`.
- Urutan: deskripsi terlarang → tipe kerja → gaji → scoring (cap 100) → ambang `min_score`.
- Kode alasan: `desc_excluded`, `work_type`, `salary_unknown`, `salary_low`, `low_score`.
- `evaluate()` dipakai nanti di M7, dengan `result.reason` menjadi `db.mark(status=f"rejected_{reason}")`.

### `models.py` (M1)
- `Job`: `job_id, title, company, location, url, salary_text, salary_min_idr, work_type, posted_date, description, found_date, score`.
- `EvalResult`: `passed, score, reason`.
- `JobDetail` (M6): `title, company, location, work_type, salary_text, salary_min_idr, description` (semua opsional).

### `parsers.py` (M6)
- Selector JobStreet **hanya** ada di sini (acuan: `docs/fase0-hasil.md`).
- `parse_search_page(html, *, base_url)` → `list[Job]` (field kartu; `job_id` dari `data-job-id`
  dengan fallback `href`); kartu tanpa judul/href/ID → `StructureChangedError`.
- `parse_detail_page(html)` → `JobDetail`; `parse_salary_min_idr(text)` → batas bawah gaji;
  `apply_detail(job, detail)` → salinan `Job` dengan field detail.
- `work_type` **hanya** ada di halaman detail (kartu tidak punya automation-nya).

### `scraper.py` (M5)
- Playwright **sinkron**; context manager (`Scraper(cfg.scraper) as source`).
- `build_search_url(keyword, location, page)` (pola Fase 0); `iter_search_pages(kw, loc, max_pages)`
  → HTML mentah per halaman + jeda acak; `fetch_detail_html(url)` → HTML detail + jeda.
- **Tidak** tahu `Job`/selector; semua parsing di `parsers.py`.
- Dikecualikan dari coverage; diuji via `tests/test_scraper.py` (bagian murni) +
  `scripts/smoke_scraper.py` (headed).

### `utils.py` (M1)
- `setup_logging(path)` (console + RotatingFileHandler, idempoten), `random_delay(min,max)`,
  `normalize_text(text)` (NFKC + lowercase + spasi tunggal).

---

## 8. Konfigurasi Sumopod di OpenCode (SUDAH BERFUNGSI)

- File: `.opencode/opencode.jsonc` (project-level, gitignored).
- Provider `sumopod`, `package @opencode/ai/providers/openai-compatible`,
  `settings.baseURL = https://ai.sumopod.com/v1` (WAJIB ada `/v1`).
- **61 model chat** terdaftar dari hasil `GET /v1/models` (64 total; 3 embedding dikecualikan).
- Model default project: `"model": "sumopod/claude-sonnet-5"`.
- ID bertanda khusus ditangani via `modelID`, mis. `sumopod/gemini-3.8-flash` → `gemini/gemini-3.8-flash`
  dan `sumopod/deepseek-v4-flash-0731-netra` → `deepseek-v4-flash-0731:netra`.

**Pelajaran penting (mahal didapat):** untuk provider **custom**, field `env` di config saja **tidak**
memasang kredensial — harus lewat alur `connect`. Yang berhasil:

```
/connect  →  pilih Sumopod  →  API key  →  tempel key
# verifikasi: opencode auth list  →  "Sumopod  Sumopod  stored"
# uji      : opencode run --model sumopod/claude-haiku-4-5 "Reply with exactly: OK"
```

Metode yang **gagal** (jangan diulang):
- `env: ["SUMOPOD_API_KEY"]` + `opencode service set env ...` (termasuk dengan `--standalone`) → "No api key passed in".
- `settings.apiKey: "{env:...}"` → header tidak terkirim.
- `settings.apiKey: "${...}"` → dikirim **literal** (tidak disubstitusi).
- `opencode auth login sumopod --method key` via pipe/stdin → butuh terminal interaktif.

---

## 9. Gotcha / pelajaran penting

1. **`ruff format .` memformat blok kode di dalam file Markdown.** Ini pernah menulis-ulang
   `planning-job-scraper-jobstreet.md` (spec user). Sudah diperbaiki dan dicegah dengan
   `extend-exclude = ["*.md", "docs"]` di `pyproject.toml`. **Jangan hapus exclude itu.**
2. **`.opencode/` di-gitignore tapi tetap dibaca OpenCode** — jadi config provider aman dari commit.
3. **`config.yaml` dan `models_sumopod.md` gitignored** (kriteria pribadi & referensi).
4. **API key pernah bocor** ke `~/.local/share/opencode/log/opencode.log` karena `opencode service set env`
   mencatat argumen CLI. Sudah dirotasi & env-nya dihapus (`opencode service get` → `{}`).
   Selalu pakai `Read-Host -AsSecureString` bila harus melewatkan secret via CLI.
5. **`opencode service restart`/`set env` menghentikan server** → dapat memutus perintah shell yang sedang
   berjalan dari dalam sesi OpenCode.
6. **Playwright Chromium sudah terpasang** (`playwright install chromium`).
7. **JobStreet dilindungi Cloudflare Turnstile** — headless diblokir. Jalankan **headed** bila perlu
   dan **jangan** mencoba melewati proteksi (spec §12). Selector resmi ada di `docs/fase0-hasil.md`.
8. **Fixture mentah memuat token/key** (mis. `key_live_...`, `loginId`) → `tests/fixtures/_raw/`
   dan `tests/hasil fase 0/` GITIGNORED. Versi yang di-commit sudah disanitasi.

---

## 10. Yang menunggu & langkah berikutnya

### Selesai
- **M4 — writers** (`58b0c6e`): `writers/` (base/excel/sheets) + `build_writer(cfg.output, dry_run=)`.
- **Fase 0 — investigasi**: strip **Cloudflare Turnstile** (headless diblokir). Capture pakai
  `scripts/capture_fase0.py` (browser headed, tanpa bypass). Fixture disanitasi (buang script/token;
  raw di `tests/fixtures/_raw/`, gitignored). Selector terverifikasi → `docs/fase0-hasil.md`.
- **M6 — parser**: `parsers.py` (`parse_search_page`, `parse_detail_page`, `parse_salary_min_idr`,
  `apply_detail`) + `tests/test_parsers.py` (offline, fixture-driven). `JobDetail` ditambah ke `models.py`.
- **M5 — scraper**: `scraper.py` (`build_search_url`, `Scraper` context manager, `iter_search_pages`,
  `fetch_detail_html`) + `tests/test_scraper.py` (bagian murni) + `scripts/smoke_scraper.py`.
  Smoketest headed: **30 kartu** + detail terbaca (work_type, deskripsi 3733 char).
  Catatan: kontrak dipakai `iter_search_pages(...) -> Iterator[str]` (HTML per halaman), bukan
  `iter_cards`: selector tetap **hanya** di `parsers.py`, scraper tidak tahu apa itu "kartu".
- **M9 — penjadwalan + README + CI**: `scripts/run.bat` (path absolut),
  `scripts/schedule_windows.md` (panduan Task Scheduler), `README.md` (setup,
  usage, investigasi, keamanan), `.github/workflows/ci.yml` (ruff, mypy, pytest
  offline), `*.xlsx` ditambah ke `.gitignore`.

---

> ✅ **Semua milestone M0–M9 + Fase 0 selesai.** Lihat EXECUTION-PLAN §19
> Definition of Done untuk status checklist.

---

## 11. Prompt untuk memulai sesi baru

Salin ini ke sesi OpenCode baru:

```text
Lanjutkan pengerjaan project di C:\FILE CODE\Scraping Loker.

Baca dulu (urut): docs/session-log.md, EXECUTION-PLAN.md, planning-job-scraper-jobstreet.md.
Kerjakan per milestone sesuai EXECUTION-PLAN.md, dan BERHENTI di akhir setiap milestone
untuk saya verifikasi. Ikuti standar python-pro: type hints lengkap, mypy --strict,
ruff, pytest >=90% coverage, bandit; jangan ubah spec; jangan menebak selector JobStreet.

Status: M0–M8 + Fase 0 selesai. Lanjutkan dari M9 (jadwal + README + CI opsional).
Selector resmi di docs/fase0-hasil.md — jangan menebak. Scraper wajib headed bila
Cloudflare muncul; jangan bypass.
Jalankan quality gate di akhir dan commit dengan Conventional Commits.
```

---

## 12. Referensi dokumen

| Dokumen | Isi |
|---|---|
| `planning-job-scraper-jobstreet.md` | **Spec asli** — acuan tunggal produk |
| `EXECUTION-PLAN.md` | Rencana eksekusi: WBS, DoD, gate, keputusan |
| `docs/fase0-investigasi.md` | Panduan investigasi Fase 0 (tugas user) |
| `docs/session-log.md` | Dokumen ini |
| `.opencode/opencode.jsonc` | Konfigurasi provider Sumopod |
