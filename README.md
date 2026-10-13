# Job Scraper — JobStreet → Spreadsheet

Mengumpulkan lowongan kerja dari JobStreet Indonesia (`id.jobstreet.com`),
menyaring sesuai kriteria pribadi, dan menyimpan yang cocok ke spreadsheet
(Excel lokal atau Google Sheets).

> **Lamaran tetap manual.** Program hanya mengumpulkan data.

## Prasyarat
- Python 3.12+
- Playwright Chromium (`playwright install chromium` dijalankan **sekali**)

## Setup

```powershell
py -3.12 -m venv .venv
.\\.venv\Scripts\pip install -r requirements-dev.txt
.\\.venv\Scripts\playwright install chromium
```

## Konfigurasi

1. Salin `config.example.yaml` menjadi `config.yaml`.
2. Ubah isinya: keyword, lokasi, filter, bobot skor, output (Excel/Sheets).
3. Jalankan `python main.py --check-config` untuk validasi.

Lihat `docs/fase0-hasil.md` untuk daftar selector JobStreet yang digunakan.

## Penggunaan

```
python main.py [opsi]

Opsi:
  --config PATH         path ke config.yaml (default: config.yaml)
  --check-config        validasi config lalu keluar
  --dry-run             simulasi tanpa menulis ke database atau spreadsheet
  --limit N             batasi jumlah lowongan yang diproses
  --headed              tampilkan browser (headless=false)
  --reset-rejected      hapus catatan lowongan yang ditolak, nilai ulang
```

Contoh:
```powershell
python main.py --dry-run --limit 10
python main.py --headed
python main.py --reset-rejected
```

### Penjadwalan

Buat tugas harian dengan Windows Task Scheduler:
```bat
schtasks /Create /SC DAILY /TN "JobScraper" /ST 08:00 ^
  /TR "\"C:\FILE CODE\Scraping Loker\.venv\Scripts\python.exe\" ^
         \"C:\FILE CODE\Scraping Loker\main.py\""
```
Lihat `scripts/schedule_windows.md` untuk pengaturan lanjutan.

## Investigasi Fase 0

Semua selector HTML didapatkan dari observasi manual (browser headed) dan
diuji dengan fixture asli di `tests/fixtures/`. Lihat `docs/fase0-hasil.md`.

**Jangan** menebak atau mengubah selector tanpa bukti HTML baru.

### Peringatan: Cloudflare Turnstile

JobStreet dilindungi Cloudflare. Headless langsung mendapat halaman
"Tunggu sebentar...". Scraper otomatis mendeteksinya dan berhenti.
Jalankan dengan `--headed` bila perlu, dan jangan coba melewati proteksi.

## Proyek ini

| Item | Detail |
|---|---|
| Package | `src/job_scraper/` |
| Log | `logs/scraper.log` (rotasi) |
| Dedup | SQLite `data/seen_jobs.db` |
| Output | Excel (`data/jobs_local.xlsx`) atau Google Sheets |
| Test | `pytest` (offline, fixture-driven) |

## Keamanan

File berikut **jangan pernah di-commit**:
- `config.yaml` (kriteria pribadi)
- `credentials/` (kunci Google Cloud)
- `data/` (database, output, pending)
- `logs/`
- `tests/hasil fase 0/` (laporan mentah memuat token browser)
- `tests/fixtures/_raw/` (fixture mentah memuat key login)

## Lisensi

Hanya untuk pemakaian pribadi.
