# Penjadwalan dengan Windows Task Scheduler

Perintah berikut membuat tugas harian yang menjalankan scraper setiap jam 08:00.

```bat
schtasks /Create /SC DAILY /TN "JobScraper" /ST 08:00 ^
  /TR "\"C:\FILE CODE\Scraping Loker\.venv\Scripts\python.exe\" ^
         \"C:\FILE CODE\Scraping Loker\main.py\""
```

Setelah dibuat, ubah properti di Task Scheduler GUI:

| Pengaturan | Nilai |
|---|---|
| **Settings → Run task as soon as possible after a scheduled start is missed** | ✅ centang (supaya tetap jalan walau laptop mati jam 08:00) |
| **General → Run whether user is logged on or not** | ✅ (agar jalan tanpa login) |
| **Actions → Start in (optional)** | `C:\FILE CODE\Scraping Loker` (supaya path relatif seperti `config.yaml` terbaca) |
| **Actions → Arguments** | kosongkan; tambahkan flag sesuai kebutuhan (`--headed`, `--limit N`) di argument *Program/script* |

## Catatan
- Saat dijadwalkan, scraper berjalan **headless** (`headless: true` di config.yaml).
  Untuk debugging, jalankan manual dengan `--headed`.
- Bila JobStreet menampilkan Cloudflare, run headless akan gagal ("0 kartu").
  Tidak ada solusi otomatis — batasi frekuensi atau jalankan manual.
- Log: `logs/scraper.log` (rotasi 3×1MB).
