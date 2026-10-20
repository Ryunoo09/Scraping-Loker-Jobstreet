# Job Scraper — JobStreet → Spreadsheet

Program otomatis yang mengambil lowongan kerja dari **JobStreet Indonesia**
(`id.jobstreet.com`), menyaring sesuai kriteria pribadi, lalu menyimpan yang lolos
ke spreadsheet (Excel atau Google Sheets). Kamu tinggal melamar secara manual.

> **Lamaran tetap manual.** Program hanya mengumpulkan dan menyaring data.

---

## Daftar Isi

- [Cara Kerja](#cara-kerja)
- [Prasyarat](#prasyarat)
- [Setup Langkah Demi Langkah](#setup-langkah-demi-langkah)
- [Konfigurasi](#konfigurasi)
- [Penggunaan](#penggunaan)
- [Hasil Output](#hasil-output)
- [Arsitektur & Modul](#arsitektur--modul)
- [Catatan Investigasi Fase 0](#catatan-investigasi-fase-0)
- [Cloudflare Turnstile](#cloudflare-turnstile)
- [Penjadwalan](#penjadwalan)
- [Testing](#testing)
- [Pemecahan Masalah](#pemecahan-masalah)
- [Keamanan](#keamanan)
- [Struktur File](#struktur-file)

---

## Cara Kerja

```text
config.yaml ──► main.py
                  │
                  ▼
          [1] Muat & validasi config
                  │
                  ▼
          [2] Scraper (Playwright)
              untuk setiap (keyword × lokasi):
                buka hasil pencarian → kumpulkan kartu lowongan
                buka detail → ambil deskripsi
                  │
                  ▼
          [3] Parser → objek Job
                  │
                  ▼
          [4] Dedup (SQLite): buang yang sudah pernah dilihat
                  │
                  ▼
          [5] Filter + Scoring (sesuai config)
                  │
                  ├── tidak lolos ──► dicatat di SQLite sebagai ditolak
                  ▼
          [6] Tulis ke spreadsheet (Excel / Google Sheets)
                  │
                  ▼
          [7] Ringkasan di terminal + file log
```

Alur penuh: config → scraping → parsing → dedup → filter/scoring → writer.
Semua langkah bisa diuji tanpa internet berkat fixture HTML di `tests/fixtures/`.

---

## Prasyarat

| Item | Versi Minimal | Catatan |
|---|---|---|
| Python | 3.12+ | 3.11 mungkin juga berfungsi tetapi belum diuji |
| OS | Windows 10/11 | Path absolut untuk penjadwalan |
| Browser | Chromium | Dipasang via `playwright install chromium` |
| Internet | Ya | Hanya saat scraping; testing offline |

---

## Setup Langkah Demi Langkah

### 1. Clone / buka folder

```powershell
cd "C:\FILE CODE\Scraping Loker"
```

### 2. Buat virtual environment (sekali)

```powershell
py -3.12 -m venv .venv
```

### 3. Aktifkan venv

```powershell
.\\.venv\Scripts\Activate.ps1     # PowerShell
# atau
.\\.venv\Scripts\activate.bat     # CMD klasik
```

> Jika PowerShell menolak karena kebijakan eksekusi:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### 4. Pasang dependensi

```powershell
pip install -r requirements-dev.txt
```

Ini memasang semua dependensi runtime (`playwright`, `pydantic`, `pyyaml`,
`openpyxl`, `gspread`, `beautifulsoup4`) dan dev (`pytest`, `ruff`, `mypy`, `bandit`).

### 5. Pasang Chromium untuk Playwright

```powershell
playwright install chromium
```

> Kalau `playwright` tidak dikenali, pakai:
> `.\\.venv\Scripts\python.exe -m playwright install chromium`

### 6. Siapkan konfigurasi

```powershell
copy config.example.yaml config.yaml
```

Buka `config.yaml` dengan text editor. Lihat bagian [Konfigurasi](#konfigurasi) di bawah.

### 7. Validasi konfigurasi

```powershell
python main.py --check-config
```

Harusnya keluar:
```
Config valid: config.yaml
```

Kalau ada error, perbaiki sesuai pesan yang ditampilkan (mis. salah ketik key,
`spreadsheet_id` masih placeholder, `min_score` di luar 0-100).

---

## Konfigurasi

File `config.yaml` adalah satu-satunya file yang perlu kamu edit. Isinya dibagi
menjadi 5 bagian. Berikut penjelasan tiap bagian.

### Bagian 1: Search — Pencarian

```yaml
search:
  keywords:
    - "IT Support"
    - "Junior Web Developer"
    - "Backend Developer"
  locations:
    - "Semarang"
    - "Jakarta Raya"
  posted_within_days: 7        # null = semua; 7 = hanya 7 hari terakhir
  max_pages_per_query: 3       # batas halaman per kombinasi keyword+lokasi
  fetch_detail: true           # buka halaman detail untuk ambil deskripsi
```

Program akan menelusuri **setiap kombinasi** keyword × lokasi. Makin banyak
kombinasi, makin lama scraping-nya.

### Bagian 2: Filters — Aturan Penolakan

```yaml
filters:
  exclude_title_keywords:
    - "senior"
    - "lead"
    - "manager"
  exclude_description_keywords:
    - "minimal 3 tahun"
    - "at least 3 years"
  exclude_companies: []         # nama perusahaan yang dihindari
  work_types:                   # [] = terima semua
    - "full time"
    - "magang"
  min_salary_idr: null          # null = tidak difilter
  keep_if_salary_unknown: true  # tetap lolos jika gaji tidak dicantumkan
```

- Pencocokan **judul** adalah kata utuh (jadi `lead` tidak menolak `leader`).
- Pencocokan **deskripsi, perusahaan, tipe kerja** adalah substring (frasa).
- Urutan evaluasi: deskripsi terlarang → tipe kerja → gaji → scoring.

### Bagian 3: Scoring — Bobot Kecocokan

```yaml
scoring:
  min_score: 40                 # ambang lolos (0-100)
  title_keywords:
    "developer": 25
    "support": 25
    "junior": 15
  description_keywords:
    "fresh graduate": 20
    "python": 10
  location_bonus:
    "Semarang": 10
```

Skor dihitung dari kata kunci yang cocok di judul + deskripsi + lokasi, lalu
dibatasi maksimum 100. Lowongan dengan skor ≥ `min_score` masuk spreadsheet.

### Bagian 4: Output — Tujuan Hasil

```yaml
output:
  type: "excel"                # "excel" atau "google_sheets"
  excel:
    file_path: "data/jobs_local.xlsx"
  # google_sheets:
  #   spreadsheet_id: "ISI_ID_SPREADSHEET_DI_SINI"
  #   worksheet_name: "Lowongan"
  #   credentials_file: "credentials/service_account.json"
```

**Excel** bisa langsung dipakai tanpa setup apa pun. File dibuat otomatis.
**Google Sheets** butuh setup Google Cloud (lihat [Setup GCP](#setup-gcp-opsional)).

### Bagian 5: Scraper — Perilaku Browser

```yaml
scraper:
  headless: true                # false = browser terlihat
  delay_min_sec: 3              # jeda acak antar permintaan
  delay_max_sec: 8
  page_timeout_sec: 30          # timeout per halaman
  max_retries: 2                # berapa kali ulang saat timeout
  max_jobs_per_run: 150         # batas keras per sekali jalan
```

> `delay_min_sec` dan `delay_max_sec` adalah bagian dari **kesopanan scraping**
> (spec §12). Jangan dikurangi tanpa alasan kuat.

---

## Penggunaan

### Semua opsi CLI

```
python main.py [opsi]

Opsi:
  --config PATH         path ke config.yaml (default: config.yaml)
  --check-config        validasi config lalu keluar
  --dry-run             simulasi tanpa menulis ke database/spreadsheet
  --limit N             batasi jumlah lowongan yang diproses
  --headed              tampilkan browser (headless=false, berguna saat debugging)
  --reset-rejected      hapus catatan lowongan yang ditolak, nilai ulang
```

### Contoh penggunaan

**Validasi konfigurasi dulu:**
```powershell
python main.py --check-config
```

**Coba dengan dry-run (tidak mengubah apa pun):**
```powershell
python main.py --dry-run --limit 10
```

**Jalankan sungguhan dengan Excel:**
```powershell
python main.py --limit 100
```

**Lihat browser untuk debugging:**
```powershell
python main.py --headed --limit 5
```

**Nilai ulang lowongan setelah mengubah kriteria:**
```powershell
python main.py --reset-rejected
```

**Gunakan konfigurasi kustom:**
```powershell
python main.py --config config_lain.yaml
```

### Ringkasan di terminal

Setelah selesai, program mencetak:
```
========================================
Ringkasan:
  Dilihat:       42
  Baru:          15
  Duplikat:      27
  Lolos:          5
  Ditulis:        5 -> data/jobs_local.xlsx
========================================
```

Kalau `dilihat = 0`, akan muncul peringatan:
```
⚠️  Tidak ada kartu di semua pencarian — kemungkinan scraper rusak.
```

---

## Hasil Output

Spreadsheet memiliki 12 kolom, urut sesuai spec §7:

| Kolom | Nama | Diisi oleh |
|---|---|---|
| A | Tanggal Ditemukan | Program |
| B | Posisi | Program |
| C | Nama Perusahaan | Program |
| D | Lokasi | Program |
| E | Link Lowongan | Program (bisa diklik) |
| F | Gaji | Program (atau kosong) |
| G | Tipe Kerja | Program |
| H | Tanggal Posting | Program (waktu WIB `YYYY-MM-DD HH:MM`; fallback teks relatif) |
| I | Skor | Program (0-100) |
| J | Status Lamaran | **Kamu** (dropdown: Belum / Sudah Dikirim / Wawancara / Ditolak / Diterima) |
| K | Catatan | **Kamu** |
| L | Job ID | Program (bisa disembunyikan) |

> Program hanya **menambah baris baru** (append-only). Kolom J dan K milikmu
> tidak akan pernah ditimpa.

**Waktu posting (kolom H).** Program menyimpan **waktu posting pasti** dari data
`window.SEEK_REDUX_DATA` di halaman hasil (bukan hanya teks relatif), lalu
menampilkannya dalam **WIB** (`YYYY-MM-DD HH:MM`) supaya bisa diurutkan. Nilai
ISO 8601 UTC-nya juga disimpan di `data/seen_jobs.db` (kolom `posted_at`). Bila
data pasti tidak tersedia (mis. situs berubah), kolom H jatuh ke teks relatif
seperti `12 jam yang lalu`.

---

## Arsitektur & Modul

```text
src/job_scraper/
├── __init__.py       # versi 0.1.0
├── cli.py            # argparse + orkestrasi alur penuh
├── config.py         # validasi config.yaml dengan Pydantic v2
├── exceptions.py     # hierarki error (ConfigError, ScraperError, dll)
├── filters.py        # passes_prefilter() + evaluate() + scoring
├── models.py         # Job, JobDetail, EvalResult (Pydantic)
├── parsers.py        # parse_search_page(), parse_detail_page() — selector JobStreet
├── scraper.py        # Playwright: ambil HTML mentah (tanpa tahu selector)
├── storage.py        # SeenJobsDB — SQLite dedup
├── utils.py          # setup_logging, random_delay, normalize_text
└── writers/
    ├── __init__.py   # build_writer(cfg, dry_run=) factory
    ├── base.py       # JobWriter Protocol + NullWriter + HEADERS
    ├── excel.py      # ExcelWriter (openpyxl, simpan atomik)
    └── sheets.py     # GoogleSheetsWriter (gspread)

tests/
├── conftest.py       # fixture bersama
├── test_*.py         # 9 file test, 175 test
└── fixtures/         # HTML asli hasil Fase 0 (untuk test offline)
```

### Prinsip desain

- **Config-driven**: semua preferensi di `config.yaml`, bukan hardcode.
- **Pemisahan tanggung jawab**: scraper hanya ambil HTML; parser urus selector;
  writers urus output. Kalau JobStreet berubah, cukup perbaiki `parsers.py`.
- **Idempotent**: dua kali jalan = tidak ada baris ganda (berkat dedup SQLite).
- **Append-only**: spreadsheet tidak pernah ditimpa, kolom manualmu aman.
- **Test offline**: semua logika diuji dengan fixture HTML, tanpa internet.

---

## Catatan Investigasi Fase 0

Semua selector HTML yang digunakan untuk membaca data dari JobStreet **bukan
tebakan**. Didapatkan melalui:

1. Browser manual (Chrome DevTools) ke `id.jobstreet.com`
2. Dicatat `data-automation` dan struktur elemen dari puluhan kartu lowongan
3. Disimpan sebagai fixture HTML di `tests/fixtures/`
4. Selector dikonfirmasi dengan smoketest browser nyata (30 kartu + detail)

Lihat `docs/fase0-hasil.md` untuk tabel selector lengkap.

> **Jangan mengubah selector di `parsers.py` tanpa fixture HTML baru yang
> membuktikan bahwa JobStreet berubah.**

---

## Cloudflare Turnstile

JobStreet (platform SEEK) dilindungi **Cloudflare Turnstile**. Dampaknya:

- Browser **headless** (tanpa jendela) langsung mendapat halaman
  `"Tunggu sebentar..."` — challenge tidak bisa dilewati otomatis.
- Scraper otomatis mendeteksi halaman ini (`CaptchaDetectedError`) dan
  menghentikan run.

**Solusi:** jalankan dengan `--headed`. Browser akan terbuka, challenge
Cloudflare selesai otomatis (biasanya tanpa klik), lalu program lanjut.

```powershell
python main.py --headed --limit 50
```

> Jangan pernah mencoba melewati atau memecahkan proteksi ini (melanggar
> ketentuan layanan dan etika).

---

## Penjadwalan

Program bisa dijadwalkan via Windows Task Scheduler.

### Perintah sekali jalan

```bat
schtasks /Create /SC DAILY /TN "JobScraper" /ST 08:00 ^
  /TR "\"C:\FILE CODE\Scraping Loker\.venv\Scripts\python.exe\" ^
         \"C:\FILE CODE\Scraping Loker\main.py\""
```

### Pengaturan lanjutan (setelah dibuat)

Buka Task Scheduler → cari tugas "JobScraper" → Properties:

| Tab | Pengaturan |
|---|---|
| General | **Run whether user is logged on or not** → centang |
| Settings | **Run task as soon as possible after a scheduled start is missed** → centang |
| Actions | **Start in** → isi `C:\FILE CODE\Scraping Loker` |

Dokumentasi lengkap: `scripts/schedule_windows.md`.

### Catatan penjadwalan

- Saat terjadwal, config `headless: true` dipakai. Jika Cloudflare muncul, run
  akan gagal dengan 0 hasil.
- Untuk debugging, jalankan manual dengan `--headed`.
- Log: `logs/scraper.log` (rotasi otomatis 3×1 MB).

---

## Testing

Semua logika diuji **tanpa internet** menggunakan fixture HTML asli.

```powershell
# Jalankan semua test (175 test)
pytest

# Dengan coverage
pytest --cov=job_scraper --cov-report=term-missing

# Lint & type
ruff check .
mypy

# Security
bandit -r src
```

| Modul | Coverage |
|---|---|
| config | 100% |
| models | 100% |
| filters | 100% |
| storage | 100% |
| parsers | 97% |
| writers | 100% |
| cli | 91% |
| utils | 100% |
| **Total** | **97%** |

Scraper (`scraper.py`) dikecualikan dari coverage karena butuh browser.

---

## Pemecahan Masalah

### "Config tidak valid"

Baca pesan error — biasanya menyebut field yang salah. Contoh:
```
Config tidak valid:
  - search.locations: harus berisi minimal satu nilai
  - output.google_sheets.spreadsheet_id masih placeholder atau kosong
```

### "Tidak ada kartu di semua pencarian"

Kemungkinan:
1. **Cloudflare** — jalankan dengan `--headed`.
2. **Keyword/lokasi tidak menghasilkan hasil** — coba cari manual di browser.
3. **Struktur JobStreet berubah** — lihat `docs/fase0-hasil.md` dan perbarui `parsers.py`.

### File Excel terkunci / tidak bisa disimpan

Tutup file Excel sebelum menjalankan program. Program menyimpan secara atomik
(file sementara lalu `os.replace`), tetapi file yang terbuka di Excel akan
menyebabkan error.

### Error `gspread` / `google-auth`

Tidak masalah jika kamu pakai `output.type: "excel"`. Error ini hanya muncul
saat type `google_sheets` tanpa setup GCP.

### Virtual environment tidak aktif

Pastikan menjalankan:
```powershell
.\\.venv\Scripts\Activate.ps1
```
Atau gunakan path absolut:
```powershell
.\\.venv\Scripts\python.exe main.py
```

---

## Setup GCP (Opsional — hanya untuk Google Sheets)

Jika ingin output Google Sheets, lakukan sekali:

1. Buka [Google Cloud Console](https://console.cloud.google.com), buat project.
2. Aktifkan **Google Sheets API** (dan **Google Drive API** jika perlu).
3. Buat **Service Account** → download JSON → simpan ke `credentials/service_account.json`.
4. Buat Google Sheet, **Share** dengan email service account (Editor).
5. Copy `spreadsheet_id` dari URL sheet ke `config.yaml`.
6. Set `output.type: "google_sheets"`.

Lihat `docs/fase0-investigasi.md` untuk detail.

---

## Keamanan

File berikut **jangan pernah di-commit** ke GitHub:

| File | Alasan |
|---|---|
| `config.yaml` | Berisi kriteria pribadi (keyword, gaji, dll) |
| `credentials/` | Kunci service account Google Cloud |
| `data/` | Database SQLite, file Excel, cadangan pending |
| `logs/` | Log runtime |
| `tests/hasil fase 0/` | Laporan mentah memuat token browser (`key_live_`, `loginId`) |
| `tests/fixtures/_raw/` | Fixture mentah memuat data sesi browser |

Semua file di atas sudah masuk `.gitignore`.

---

## Struktur File

```
Scraping Loker/
├── main.py                         # entrypoint
├── config.yaml                     # KAMU (gitignored)
├── config.example.yaml             # contoh aman untuk di-commit
├── requirements.txt                # dependensi runtime
├── requirements-dev.txt            # + dev
├── pyproject.toml                  # tooling config
├── .gitignore
├── .gitattributes
├── README.md                       # file ini
├── scripts/
│   ├── capture_fase0.py            # ambil fixture Fase 0 (Playwright headed)
│   ├── smoke_scraper.py            # smoketest scraper → parser
│   ├── run.bat                     # pemanggil untuk Task Scheduler
│   └── schedule_windows.md         # panduan penjadwalan
├── docs/
│   ├── fase0-investigasi.md        # panduan investigasi manual
│   ├── fase0-hasil.md              # HASIL: selector terverifikasi
│   ├── plan-tanggal-posting.md     # rencana waktu posting (posted_at)
│   └── session-log.md              # catatan handoff sesi
├── src/job_scraper/                # package utama (~700 LOC)
│   ├── __init__.py
│   ├── cli.py, config.py, exceptions.py, filters.py
│   ├── models.py, parsers.py, scraper.py, storage.py, utils.py
│   └── writers/
│       ├── __init__.py, base.py, excel.py, sheets.py
├── tests/
│   ├── conftest.py
│   ├── test_*.py                   # 9 file, 175 test
│   └── fixtures/
│       ├── search_page_01.html     # 30 kartu lowongan
│       ├── detail_01.html          # halaman detail
│       ├── listing_dates_01.html   # cuplikan waktu posting (server-state)
│       └── _raw/                   # gitignored
├── data/                           # runtime, gitignored
│   ├── seen_jobs.db
│   └── jobs_local.xlsx
└── logs/                           # runtime, gitignored
    └── scraper.log
```

---

## Lisensi

Hanya untuk pemakaian pribadi. Tidak untuk didistribusikan atau dijual.

**Sumber data:** JobStreet Indonesia (bagian dari SEEK). Seluruh hak cipta data
milik JobStreet/SEEK.
