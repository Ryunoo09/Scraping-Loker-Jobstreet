# Execution Plan — Job Scraper JobStreet

> Dokumen ini adalah **rencana eksekusi** yang dibuat oleh agent `python-pro`
> (`.opencode/agents/python-pro.md`) berdasarkan spesifikasi di
> [`planning-job-scraper-jobstreet.md`](planning-job-scraper-jobstreet.md).
>
> Perbedaan peran:
> - **Spec** (`planning-job-scraper-jobstreet.md`) = *apa* yang dibangun (produk, kriteria, skema).
> - **Execution Plan** (dokumen ini) = *bagaimana* membangunnya: urutan kerja, kontrak modul,
>   standar kode, task IDs, definisi selesai (DoD), quality gate, dan keputusan yang belum ditutup.
>
> Spec tetap menjadi acuan tunggal untuk hal produk. Dokumen ini **tidak** menggantikan spec;
> ia merujuk balik ke nomor bagian spec, mis. `(spec §6)`.

Status: **M0 & M1 SELESAI** — menunggu verifikasimu sebelum M2.
Bagian 4.2 mencatat keputusan akhir (venv + pip, Excel dulu, Fase 0 manual olehmu).

---

## 1. Cara pakai dokumen ini

1. Baca Bagian 4 (keputusan terbuka). Kalau ada yang tidak setuju, ubah dulu.
2. Saya kerjakan **satu milestone (M0…M9) per sesi**, berhenti di akhir milestone.
3. Kamu verifikasi pakai DoD milestone tersebut, lalu saya lanjut ke milestone berikutnya.
4. Tidak ada milestone yang dianggap selesai tanpa quality gate di Bagian 11 lolos.

---

## 2. Prasyarat & asumsi lingkungan

| Item | Nilai | Catatan |
|---|---|---|
| OS | Windows (laptop pribadi) | Path absolut saat penjadwalan (spec §13) |
| Interpreter | Python **3.12+** | Standar `python-pro`; spec hanya minta 3.11+ |
| Package manager | **venv + pip + `requirements.txt`** | uv dibatalkan (keputusanmu); config tooling tetap di `pyproject.toml` |
| Repo | `github.com/Ryunoo09/Scraping-Loker-Jobstreet` | Sudah terhubung, branch `main` |
| Direktori kerja | `C:\FILE CODE\Scraping Loker` | Bukan folder `job-scraper/` terpisah — kode ditaruh di root ini |
| Akses internet | Ya (saat scraping) | Unit test **wajib** jalan offline (fixtures) |

Catatan struktur: spec §5 menggambar root bernama `job-scraper/`. Kita sudah punya root repo
`Scraping Loker`, jadi **root repo == root proyek**. Tidak dibuat subfolder lagi.

---

## 3. Standar engineering (mengikat, dari `python-pro`)

Semua kode wajib memenuhi ini:

- **Type hint lengkap** untuk semua signature fungsi & atribut kelas; `mypy --strict` hijau.
- **Pydantic v2** untuk semua input eksternal (config YAML, payload JSON, baris spreadsheet) —
  validasi di batas sistem, bukan di tengah logika.
- **PEP 8** via `ruff format` + `ruff check` (line length 100, target `py312`).
- **Docstring Google-style** untuk fungsi/kelas publik.
- **Custom exception** (bukan `Exception` generik) — lihat Bagian 12.
- **Test coverage ≥ 90%** untuk modul non-jaringan; `pytest` + `pytest-cov`.
- **Security scan** `bandit` bersih; tidak ada rahasia di kode/log (Bagian 13).
- **Config-driven**: nol nilai preferensi di-hardcode dalam logika (spec §3).
- **Idempotent**: run kedua tidak menambah baris ganda (spec §3, §10).
- **Append-only** ke spreadsheet: tidak pernah menimpa/menghapus baris (spec §7).
- **Jangan menebak selector JobStreet.** Selector/endpoint **hanya** berasal dari hasil
  investigasi Fase 0 (spec §8 Fase 0, §17 poin 3).

### 3.1 Tooling & perintah standar (venv + pip)

```powershell
# bootstrap sekali (Windows / PowerShell)
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium

# quality gates (dijalankan tiap milestone)
.\.venv\Scripts\ruff.exe format .
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe --cov=job_scraper --cov-report=term-missing
.\.venv\Scripts\bandit.exe -r src
```

> Di Linux/macOS ganti `.\.venv\Scripts\` menjadi `.venv/bin/`.

### 3.2 `pyproject.toml` (config tooling saja)

Dependensi **tidak** ditulis di sini (kita pakai `requirements.txt`). File ini hanya menampung
konfigurasi ruff/mypy/pytest/coverage. Isi aktualnya sudah ada di repo:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
files = ["src", "tests", "main.py"]
mypy_path = "src"

[[tool.mypy.overrides]]          # gspread belum punya stub resmi
module = ["gspread", "gspread.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
addopts = "-q --strict-markers"
testpaths = ["tests"]
pythonpath = ["src"]             # agar `import job_scraper` bekerja tanpa install

[tool.coverage.run]
source = ["job_scraper"]
omit = ["src/job_scraper/scraper.py"]   # jalur jaringan, diuji via parsers.py
```

> `scraper.py` dikecualikan dari target coverage karena butuh browser+internet. Logika
> **parsing**-nya dipisah ke `parsers.py` yang murni string→`Job` dan **wajib** diuji
> dengan fixtures (Bagian 9). Ini juga yang membuat "JobStreet berubah tampilan" hanya
> menyentuh `parsers.py`.

---

## 4. Keputusan

### 4.1 Terkunci (mengikuti spec, tidak diubah tanpa persetujuanmu)

| # | Keputusan | Sumber |
|---|---|---|
| 1 | Sumber tunggal untuk versi dasar: JobStreet Indonesia; lamaran tetap manual | spec §1, §2 |
| 2 | Kriteria pengguna hanya di `config.yaml`, divalidasi Pydantic | spec §6 |
| 3 | Pemisahan modul: scraper / parser / filters / storage / writer | spec §3 |
| 4 | Dedup pakai SQLite; lowongan ditolak pun dicatat; ada `--reset-rejected` | spec §10 |
| 5 | Spreadsheet append-only + `_ensure_header` | spec §7 |
| 6 | Playwright **sinkron** (`sync_api`) | lihat 4.3, disetujui via spec §12 |
| 7 | CLI pakai `argparse` bawaan (bukan Click) | spec §4 |
| 8 | Output Excel lebih dulu, Google Sheets menyusul | spec §8 Fase 6 |

### 4.2 Keputusan — SUDAH DIJAWAB (dipakai untuk eksekusi)

| Pertanyaan | Jawaban |
|---|---|
| Q1 investigasi Fase 0 | Kamu (manual); saya sediakan panduan + format hasil |
| Q2 output default M4 | Excel lokal dulu, Google Sheets menyusul |
| Q3 package manager | venv + pip + `requirements.txt` (uv dibatalkan) |
| Q4 `config.yaml` | Tidak di-commit → gitignore + `config.example.yaml` |
| Q5 deviasi Bagian 4.4 | Disetujui, kecuali bagian uv (dibatalkan) |

### 4.3 Catatan: kenapa Playwright **sync**, bukan async

`python-pro` default-nya async-first untuk I/O, tetapi di sini kita **sengaja serialisasi**
(scraping sopan, jeda 3–8 detik, sekali sehari — spec §12). Tanpa konkurensi, `sync_api`
lebih sederhana, penanganan error lebih mudah, dan lebih mudah di-debug. Async tidak memberi
keuntungan apa pun di pola ini. Keputusan dicatat agar tidak dianggap kelalaian.

### 4.4 Deviasi kecil dari spec (mohon konfirmasi)

| Spec | Usulan | Alasan |
|---|---|---|
| `Job` = `dataclass` (spec §6) | `Job` = Pydantic `BaseModel` | Validasi + `model_dump_json()` gratis untuk backup `data/pending_*.json` (spec §12) |
| `requirements.txt` (spec §4) | Dipertahankan apa adanya | Keputusanmu: uv dibatalkan; `pyproject.toml` hanya untuk config tooling |
| `src/` = modul lepas | `src/job_scraper/` = package | Import jelas, installable (`uv pip install -e .`), struktur `main.py` di root tetap sama |

---

## 5. Struktur proyek final

```
Scraping Loker/
├── main.py                       # entrypoint tipis → job_scraper.cli.main()
├── pyproject.toml                # config tooling saja (ruff/mypy/pytest/coverage)
├── requirements.txt              # dependensi runtime
├── requirements-dev.txt          # dependensi dev (pytest/ruff/mypy/bandit)
├── config.example.yaml           # contoh aman untuk di-commit
├── config.yaml                   # MILIK KAMU (lihat Bagian 18 / Q4)
├── README.md
├── .gitignore
├── .gitattributes                # (opsional) normalisasi LF/CRLF
├── credentials/                  # JANGAN di-commit
│   └── service_account.json
├── data/                         # runtime, JANGAN di-commit
│   ├── seen_jobs.db
│   ├── jobs_local.xlsx
│   └── pending_YYYYMMDD.json
├── logs/                         # runtime, JANGAN di-commit
│   └── scraper.log
├── scripts/
│   ├── run.bat                   # pemanggil untuk Task Scheduler
│   └── schedule_windows.md       # catatan perintah schtasks
├── docs/
│   └── fase0-investigasi.md      # panduan investigasi (tugas kamu) + format hasil
├── src/
│   └── job_scraper/
│       ├── __init__.py
│       ├── cli.py                # argparse, orkestrasi run()
│       ├── exceptions.py         # hierarki error
│       ├── config.py             # load + validasi config.yaml (Pydantic)
│       ├── models.py             # Job, EvalResult, Stats
│       ├── filters.py            # pra-filter, evaluate, scoring
│       ├── storage.py            # SeenJobsDB (SQLite)
│       ├── writers/
│       │   ├── __init__.py       # build_writer() factory + Protocol
│       │   ├── base.py           # JobWriter Protocol + NullWriter
│       │   ├── excel.py          # ExcelWriter (openpyxl)
│       │   └── sheets.py         # GoogleSheetsWriter (gspread)
│       ├── scraper.py            # Playwright: navigasi + ambil HTML mentah
│       ├── parsers.py            # HTML/JSON → Job (murni, diuji fixtures)
│       └── utils.py              # random_delay, normalize_text, logging setup
└── tests/
    ├── conftest.py               # fixtures: cfg, make_job, write_config
    ├── test_config.py
    ├── test_models.py
    ├── test_cli.py
    ├── test_filters.py
    ├── test_storage.py
    ├── test_parsers.py
    ├── test_writers.py
    ├── test_utils.py
    └── fixtures/                 # contoh HTML/JSON hasil Fase 0
```

Tambahan `.gitignore` di atas yang sudah ada:

```
credentials/
data/
logs/
config.yaml
*.xlsx
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
```

---

## 6. Kontrak modul (interfaces)

Ditetapkan lebih dulu supaya modul bisa dikerjakan & diuji terpisah (spec §3).

```python
# models.py
class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    url: str
    salary_text: str | None = None
    salary_min_idr: int | None = None
    work_type: str | None = None
    posted_date: str | None = None  # ISO date bila tersedia
    description: str | None = None
    found_date: str  # ISO date, diisi saat ditemukan
    score: int = 0


class EvalResult(BaseModel):
    passed: bool
    score: int = 0
    reason: str = ""


# storage.py
class SeenJobsDB:
    def __init__(self, path: Path) -> None: ...
    def has(self, job_id: str) -> bool: ...
    def mark(self, job: Job, status: str) -> None: ...
    def reset_rejected(self) -> int: ...  # hapus status rejected_*
    def close(self) -> None: ...


# filters.py  (fungsi murni, tanpa I/O)
def passes_prefilter(job: Job, filters: FiltersConfig) -> bool: ...
def evaluate(job: Job, cfg: AppConfig) -> EvalResult: ...


# writers/base.py
class JobWriter(Protocol):
    def ensure_header(self) -> None: ...
    def append(self, jobs: Sequence[Job]) -> None: ...  # batch, sekali per run


# scraper.py  (butuh jaringan; mengembalikan data mentah, bukan Job)
class JobSource(Protocol):
    def iter_cards(self, keyword: str, location: str, page: int) -> Iterator[RawCard]: ...
    def fetch_detail_html(self, url: str) -> str: ...
```

Prinsip: `scraper.py` **tidak** tahu soal `Job`; `parsers.py` yang mengubah HTML/JSON → `Job`.
Kalau Fase 0 ternyata menemukan endpoint JSON, cukup tambah `JsonJobSource` yang memenuhi
`JobSource` — parser & modul lain tidak berubah (spec §1, §12).

---

## 7. Urutan eksekusi (dependency-first) & pemetaan ke spec

Spec mengerjakan scraper lebih dulu (Fase 2). Saya usulkan urutan yang **lebih aman**: seluruh
logika yang bisa diuji **offline** dibangun lebih dulu, baru scraper (bagian berisiko, bergantung
hasil investigasimu). Alasan: (a) Fase 0 butuh waktumu; (b) logika filter/dedup/writer bisa
matang tanpa internet; (c) mengurangi risiko "scraper jalan tapi tidak ada tempat menampung hasil".

```
M0 bootstrap ─► M1 domain+config ─┬─► M2 storage ──┐
                                  ├─► M3 filters ──┼─► M7 orkestrasi+CLI ─► M8 hardening ─► M9 jadwal+docs
                    (M0-M3 OFFLINE)└─► M4 writers ─┘
                                  M5 scraper* ─► M6 parser tests*
                                  (*bergantung hasil investigasi Fase 0)
```

| Milestone | Spec | Butuh internet? | Gate |
|---|---|---|---|
| M0 Bootstrap & tooling | §8 Fase 0 layar-setup, §4 | sebagian (install) | — |
| M1 Domain + config + logging | §8 Fase 1, §6 | tidak | — |
| M2 Storage/dedup | §8 Fase 5, §10 | tidak | — |
| M3 Filters + scoring | §8 Fase 4, §9 | tidak | — |
| M4 Writers (Excel→Sheets) | §8 Fase 6, §7, §11 | Sheets: ya | Q2/Q3 |
| M5 Scraper Playwright | §8 Fase 2–3, §12 | ya | **Q1 (hasil Fase 0)** |
| M6 Parser + fixtures tests | §15 | tidak | Q1 |
| M7 Orkestrasi + CLI + summary | §8 Fase 7, §8.1 | tidak | — |
| M8 Hardening (retry, captcha, 0-hasil, pending) | §8 Fase 9, §12 | ya (uji manual) | Q1 |
| M9 Penjadwalan + README + CI opsional | §8 Fase 8, §13 | tidak | — |

---

## 8. Work Breakdown Structure

Kolom `Owner`: **A** = saya (agent), **U** = kamu (butuh aksi/izin manusia).

| ID | Task | M | Owner | Depends on | DoD ringkas |
|---|---|---|---|---|---|
| T0.1 | `uv init`, deps, `playwright install chromium` | M0 | U izin / A | — | `uv run python -c "import playwright,pydantic,yaml"` OK |
| T0.2 | `pyproject.toml` (ruff/mypy/pytest/coverage) | M0 | A | T0.1 | `ruff`, `mypy`, `pytest` jalan (kosong) |
| T0.3 | Update `.gitignore` + `.gitattributes` | M0 | A | — | `credentials/ data/ logs/ config.yaml` ter-ignore |
| T0.4 | Investigasi Fase 0 (URL, selector/endpoint, Job ID) | M0/M5 | **U** | — | Catatan + 3–5 fixture HTML/JSON |
| T1.1 | `exceptions.py` | M1 | A | — | Hierarki error terdefinisi & terdokumentasi |
| T1.2 | `models.py` (`Job`, `EvalResult`) | M1 | A | T1.1 | Round-trip `model_dump_json()` OK |
| T1.3 | `config.py` Pydantic v2 + pesan error spesifik | M1 | A | T1.2 | `--check-config` lolos & gagal dengan pesan jelas |
| T1.4 | `utils.py` (`random_delay`, `normalize_text`, logging) | M1 | A | — | Log ke `logs/scraper.log` + rotasi |
| T1.5 | `config.example.yaml` + `config.yaml` awal | M1 | A/U | T1.3 | Sesuai spec §6; Q4 |
| T1.6 | `tests/test_config.py`, `test_utils.py` | M1 | A | T1.3, T1.4 | Valid & invalid YAML tercakup |
| T2.1 | `storage.py` skema SQLite + `sqlite3` context mgr | M2 | A | T1.2 | Tabel `seen_jobs` sesuai spec §10 |
| T2.2 | `has/mark/reset_rejected` | M2 | A | T2.1 | Run 2x → 0 baru |
| T2.3 | `tests/test_storage.py` (in-memory `:memory:`) | M2 | A | T2.1 | Dedup + status + reset teruji |
| T3.1 | `passes_prefilter` + regex kata utuh | M3 | A | T1.3 | "lead" ≠ "leader" (spec §9 catatan) |
| T3.2 | `evaluate` (filter wajib + scoring + cap 100) | M3 | A | T3.1 | Sesuai spec §9 urutan evaluasi |
| T3.3 | `tests/test_filters.py` + Hypothesis (opsional) | M3 | A | T3.2 | Termasuk contoh test di spec §15 |
| T4.1 | `writers/base.py` + `NullWriter` (dry-run) | M4 | A | T1.2 | Protocol + no-op writer |
| T4.2 | `ExcelWriter` (buat file+header, append, simpan atomik) | M4 | A | T4.1 | Link klik + file terkunci ditangani (spec §11) |
| T4.3 | `GoogleSheetsWriter` (batch `append_rows`) | M4 | A | T4.1, T? (setup GCP) | Header otomatis; quota aman |
| T4.4 | `build_writer(cfg)` factory | M4 | A | T4.2, T4.3 | Pilih Sheets/Excel/Null dari config |
| T4.5 | `tests/test_writers.py` (Excel, tmp_path) | M4 | A | T4.2 | Header + append + no-overwrite |
| T5.1 | `scraper.py` context manager + `new_context(locale, viewport)` | M5 | A | T0.4 | Browser hidup/mati bersih (spec §12) |
| T5.2 | `iter_cards` pagination + jeda acak | M5 | A | T5.1, T0.4 | ≥20 kartu untuk 1 pencarian (spec §8 Fase 2) |
| T5.3 | `fetch_detail_html` (hanya utk yang lolos pra-filter) | M5 | A | T5.2 | Deskripsi non-kosong (spec §8 Fase 3) |
| T6.1 | `parsers.py` kartu → `Job` (selector dari T0.4) | M6 | A | T0.4 | Semua field terisi dari fixture |
| T6.2 | `parsers.py` detail HTML/JSON → description | M6 | A | T6.1 | Fixture-driven |
| T6.3 | `tests/test_parsers.py` + `tests/fixtures/` | M6 | A | T0.4 | Offline, tidak menyentuh internet |
| T7.1 | `cli.py` `run()` sesuai spec §8.1 | M7 | A | M2,M3,M4,M5,M6 | Alur penuh jalan |
| T7.2 | Flags `--config/--dry-run/--check-config/--limit/--headed/--reset-rejected` | M7 | A | T7.1 | Semua berfungsi (spec §8 Fase 7) |
| T7.3 | `Stats` + ringkasan terminal | M7 | A | T7.1 | Melihat/baru/lolos/ditulis |
| T7.4 | `main.py` tipis | M7 | A | T7.1 | `python main.py` cukup |
| T8.1 | Retry + timeout per halaman | M8 | A | T5.2 | Sesuai tabel error spec §12 |
| T8.2 | Deteksi selector-hilang → `StructureChangedError`, stop tanpa tulis separuh | M8 | A | T6.1 | Tidak ada data setengah jadi |
| T8.3 | Deteksi CAPTCHA/verifikasi → stop + log | M8 | A | T5.1 | Tidak retry agresif |
| T8.4 | Backup `data/pending_YYYYMMDD.json` + drain di run berikutnya | M8 | A | T1.2, T4.4 | Gagal tulis Sheets tidak hilang data |
| T8.5 | Alert "0 kartu di semua pencarian" | M8 | A | T7.3 | Peringatan mencolok (spec §8, §12) |
| T9.1 | `scripts/run.bat` + catatan Task Scheduler | M9 | A | T7.4 | Path absolut venv (spec §13) |
| T9.2 | `README.md` (cara pakai + catatan investigasi) | M9 | A | semua | Sesuai spec §18 checklist |
| T9.3 | CI GitHub Actions (lint+types+test, offline) — opsional | M9 | A | M7 | Hijau tanpa secret |

---

## 9. Strategi testing & coverage

| Layer | File | Teknik | Target |
|---|---|---|---|
| Config | `test_config.py` | beberapa YAML valid/invalid | 100% |
| Models | (via config/filters) | round-trip JSON | ≥90% |
| Utils | `test_utils.py` | delay range, normalisasi teks | ≥90% |
| Filters | `test_filters.py` | data buatan + `hypothesis` | **100%** |
| Storage | `test_storage.py` | SQLite `:memory:` | ≥95% |
| Parsers | `test_parsers.py` | **fixtures HTML/JSON dari Fase 0** | ≥95% |
| Writers | `test_writers.py` | `openpyxl` ke `tmp_path` | ≥90% (Sheets di-mock) |
| Scraper | — | manual + `--dry-run --limit 10` | dikeluarkan dari cov |

- Fixtures **wajib** berasal dari HTML/JSON asli hasil Fase 0, disimpan di `tests/fixtures/`.
  Ini regression test untuk saat JobStreet mengubah tampilan.
- Integrasi (butuh internet): `uv run python main.py --dry-run --limit 10`.
- Manual (spec §15): cek kolom sheet, link klik, tidak ada baris ganda.

---

## 10. Git & workflow

Repo sudah terhubung (`origin`, branch `main`).

- **Model sederhana (direkomendasikan untuk proyek solo):** commit langsung ke `main`,
  satu commit per task group, Conventional Commits.
  - `feat(config): validasi config.yaml dengan pydantic v2`
  - `feat(filters): pra-filter judul + scoring berbobot`
  - `fix(parsers): perbarui selector kartu pasca-perubahan JobStreet`
- Alternatif: branch per milestone (`feat/m3-filters`) lalu merge — dipakai bila kamu mau PR review.
- **Tag per milestone**: `git tag m1-config` dst. (opsional, memudahkan rollback)
- **Jangan pernah commit**: `credentials/`, `data/`, `logs/`, `config.yaml` (Q4), `.env`, `*.xlsx`.
- `bandit` + review manual sebelum commit untuk memastikan tidak ada rahasia/log kredensial.

---

## 11. Quality gate (wajib lolos di akhir tiap milestone)

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=job_scraper --cov-report=term-missing
uv run bandit -r src -q
```

Milestone tidak "selesai" bila salah satu merah. Untuk milestone yang menyentuh Scraper,
tambahkan smoketest manual `--dry-run --limit 10`.

---

## 12. Ketahanan & error handling

Hierarki exception (`exceptions.py`):

```text
JobScraperError
├── ConfigError              # config.yaml tidak valid → berhenti sebelum scraping
├── ScraperError
│   ├── StructureChangedError   # selector hilang → stop, jangan tulis separuh
│   └── CaptchaDetectedError    # stop, jangan retry agresif
├── StorageError
└── WriterError              # → picu backup pending_*.json
```

Perilaku sesuai tabel spec §12: timeout → retry sampai `max_retries` lalu lewati+catat;
struktur berubah → stop bersih; CAPTCHA → stop+catat; gagal tulis Sheets → backup lalu
dicoba run berikutnya; config invalid → berhenti dengan pesan spesifik.

Prinsip "stop bersih": penulisan ke spreadsheet hanya dilakukan **sekali di akhir run**
(batch). Kalau run gagal sebelum titik itu, **tidak ada** baris yang masuk.

---

## 13. Keamanan & rahasia

- `credentials/service_account.json` tidak pernah masuk Git (`.gitignore`).
- Rahasia tidak pernah muncul di kode, log, atau pesan error. Path boleh, isi key tidak.
- Config berisi `spreadsheet_id` → diperlakukan semi-sensitif (Q4).
- Scope service account minimal: hanya Sheets+Drive yang dibutuhkan (spec §11).
- `bandit -r src` bersih. Pertimbangkan `detect-secrets`/`gitleaks` sebagai pre-commit (opsional).
- Sheet di-share hanya ke `client_email` service account dengan akses Editor.

---

## 14. Penjadwalan (spec §13)

- `scripts/run.bat` memanggil **python di dalam venv dengan path absolut**.
- Path relatif diselesaikan dari `Path(__file__).resolve().parent`, bukan CWD.
- Task Scheduler: centang "run as soon as possible after a missed start", isi "Start in".
- `headless: true` untuk run terjadwal. Frekuensi maksimal 1×/hari (spec §12 etika).

---

## 15. CI opsional (M9)

GitHub Actions: `ruff` + `mypy` + `pytest` (tanpa internet, semua fixtures).
Tidak butuh secret. Bonus: menjaga hijau saat kamu mengubah selector.

---

## 16. Risiko eksekusi (bukan risiko produk — itu di spec §14)

| Risiko | Mitigasi |
|---|---|
| Fase 0 belum selesai → M5/M6 terblokir | Kerjakan M0–M4 & M7 dulu (offline); M5/M6 begitu hasil investigasi ada |
| Asumsi selector salah → parser diam-diam kosong | Parser diuji dengan fixture asli; validasi "field wajib tidak kosong"; alert 0-hasil |
| Playwright/Chromium minta unduhan besar | Konfirmasi izin (Q1/T0.1) sebelum mengunduh |
| Blokir/CAPTCHA saat pengembangan | Uji dengan `--limit` kecil + `--headed`; simpan HTML, uji parser offline |
| Google Cloud setup melelahkan | Jalur Excel dulu (M4 T4.2) agar M7 tidak terblokir |
| `mypy --strict` + gspread tanpa stub | override `ignore_missing_imports` (Bagian 3.2) |
| Windows: file Excel terkunci | Simpan atomik (temp + `os.replace`), pesan error jelas |
| Coverage gagal karena kode jaringan | `omit scraper.py`; logika di `parsers.py` yang diuji |

---

## 17. Yang saya butuhkan darimu sebelum/selama eksekusi

1. **Hasil investigasi Fase 0** (spec §8 Fase 0): pola URL pencarian & pagination, selector
   stabil (utamakan `data-automation`), lokasi Job ID, dan apakah ada endpoint JSON; plus
   **3–5 file HTML/JSON** untuk `tests/fixtures/`.
   → Atau beri saya izin menjalankan Playwright (headed) di laptopmu untuk mengambil ini.
2. **Setup Google Cloud** (spec §11) bila mau output Sheets: `service_account.json` +
   `spreadsheet_id`. Tidak perlu bila mulai dari Excel.
3. **Konfirmasi nilai `config.yaml`** awal (keywords, lokasi, filter, bobot skor).
4. **Izin menjalankan** perintah instalasi dependensi & unduhan Chromium (T0.1).

---

## 18. Keputusan terbuka — TERJAWAB (lihat §4.2)

| # | Pertanyaan | Rekomendasi saya |
|---|---|---|
| Q1 | Siapa mengerjakan investigasi Fase 0? | Kamu jalankan manual (spec §17); saya bisa bantu terpandu / atau saya coba otomatis headed |
| Q2 | Output default milestone M4? | **Excel dulu** (tanpa setup GCP), lalu tambah Google Sheets |
| Q3 | Package manager? | **uv** + `pyproject.toml`; tetap ekspor `requirements.txt` bila perlu |
| Q4 | `config.yaml` (kriteria pribadimu) di-commit? | **Tidak** — gitignore `config.yaml`, commit `config.example.yaml` |
| Q5 | Setujui deviasi Bagian 4.4 (Pydantic `Job`, uv, `src/job_scraper/`)? | Ya |

---

## 19. Definition of Done (proyek)

Mengacu checklist spec §18, dan semua item di bawah ini harus terpenuhi:

- [ ] Semua quality gate Bagian 11 hijau (ruff, mypy strict, pytest ≥90%, bandit)
- [ ] `python main.py --check-config` lolos untuk `config.yaml` valid & menolak yang invalid
- [ ] `python main.py` menjalankan alur penuh config → spreadsheet
- [ ] `--dry-run`, `--limit`, `--headed`, `--reset-rejected` terbukti berfungsi
- [ ] Dua run berturut-turut → tidak ada baris ganda
- [ ] Spreadsheet: kolom sesuai spec §7, link klik, header otomatis, append-only
- [ ] Log + rotasi tertulis; alert "0 hasil" teruji
- [ ] Kegagalan tulis output → backup `pending_*.json` terbentuk & dipulihkan run berikutnya
- [ ] `credentials/`, `data/`, `logs/`, `config.yaml` ter-ignore dari Git
- [ ] README memuat cara pakai + catatan investigasi
- [ ] Penjadwalan terbukti jalan di laptop
- [ ] Tidak ada selector hasil tebakan; semua berasal dari Fase 0

---

## 20. Estimasi

Estimasi spec §8 bersifat manusia; dengan saya sebagai agent, sebagian besar bekerja jauh
lebih cepat. Yang tersisa sebagai "waktu kamu" adalah Fase 0 (investigasi) dan setup GCP.

| Milestone | Est. agent | Est. kamu |
|---|---|---|
| M0 Bootstrap | ~15 mnt | ~15 mnt (izin/install) |
| M1 Domain+config | ~30 mnt | — |
| M2 Storage | ~20 mnt | — |
| M3 Filters | ~25 mnt | — |
| M4 Writers | ~40 mnt | ~30 mnt (bila Sheets/GCP) |
| M5 Scraper | ~45 mnt | **Fase 0** (spec §8: ±2–3 jam) |
| M6 Parser tests | ~30 mnt | — |
| M7 Orkestrasi+CLI | ~40 mnt | — |
| M8 Hardening | ~40 mnt | uji manual |
| M9 Jadwal+docs | ~30 mnt | ~15 mnt (Task Scheduler) |

Kritikal path: **M0 → M1 → (M2/M3/M4 paralel) → M7** (semua offline, bisa jalan tanpa
menunggu Fase 0), sementara **M5/M6** menunggu hasil investigasi Fase 0 darimu.
