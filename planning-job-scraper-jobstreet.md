# Planning Lengkap: Job Scraper JobStreet → Spreadsheet

Dokumen ini adalah panduan perencanaan dan implementasi untuk program yang secara otomatis mengambil lowongan kerja dari JobStreet Indonesia, menyaringnya sesuai kriteria pribadi, lalu menyimpan yang cocok ke spreadsheet untuk dilamar secara manual.

Dokumen ini dibuat agar bisa berdiri sendiri: dapat dibaca langsung, dan juga dapat diberikan ke AI coding agent sebagai spesifikasi pengerjaan (lihat Bagian 17).

---

## 1. Ringkasan

| Item | Keputusan |
|---|---|
| Tujuan | Mengumpulkan lowongan yang cocok ke satu spreadsheet, lalu dilamar manual |
| Sumber data | JobStreet Indonesia (`id.jobstreet.com`) |
| Tempat menjalankan | Laptop pribadi |
| Bahasa | Python 3.11+ |
| Cara scraping | Playwright (browser otomatis), dengan opsi membaca endpoint JSON jika ditemukan saat investigasi |
| Tempat mengisi kriteria | **File `config.yaml`** (satu-satunya file yang perlu kamu edit sebelum scraping) |
| Penyimpanan hasil | Google Sheets (utama) atau file Excel lokal (cadangan/awal) |
| Pencegah duplikat | Database lokal SQLite (`data/seen_jobs.db`) |
| Penjadwalan | Task Scheduler (Windows) atau cron (Linux/macOS) |

### Jawaban atas dua pertanyaan utama

1. **Apakah bisa dilakukan?** Bisa. Semua komponennya (scraping, filter, tulis ke spreadsheet, penjadwalan) adalah teknik standar. Bagian yang paling rawan adalah scraping, karena struktur situs bisa berubah dan ada proteksi anti-bot. Itu dibahas di Bagian 12 dan 14.
2. **Di mana kriteria diisi?** Di file **`config.yaml`**, pada bagian `search` dan `filters`. Kamu cukup membuka file itu dengan text editor, mengubah isinya, menyimpan, lalu menjalankan program. Tidak perlu mengubah kode Python.

---

## 2. Ruang Lingkup

### Termasuk (In Scope)
- Mengambil daftar lowongan dari JobStreet berdasarkan kata kunci dan lokasi
- Membuka halaman detail lowongan untuk membaca deskripsi (dibutuhkan agar filter akurat)
- Menyaring dan memberi skor sesuai kriteria di `config.yaml`
- Menyimpan lowongan yang lolos ke spreadsheet dengan kolom: link lowongan, nama perusahaan, lokasi, dan kolom pendukung
- Tidak memasukkan lowongan yang sama dua kali
- Log aktivitas dan penanganan error dasar
- Dijalankan manual maupun terjadwal di laptop

### Tidak Termasuk (Out of Scope)
- Mengirim lamaran otomatis (sengaja dikecualikan, lamaran tetap manual)
- Login ke akun JobStreet
- Mengambil data dari situs lain (bisa ditambah nanti, lihat Bagian 16)
- Antarmuka web atau aplikasi desktop
- Berjalan saat laptop mati

---

## 3. Arsitektur dan Alur

```
config.yaml ──► main.py
                  │
                  ▼
          [1] Muat & validasi config
                  │
                  ▼
          [2] Scraper (Playwright)
              untuk setiap (keyword × lokasi):
                buka hasil pencarian → kumpulkan kartu lowongan
                (opsional) buka detail → ambil deskripsi
                  │
                  ▼
          [3] Normalisasi → objek Job
                  │
                  ▼
          [4] Dedup (SQLite): buang yang sudah pernah dilihat
                  │
                  ▼
          [5] Filter + Scoring (sesuai config)
                  │
                  ├── tidak lolos ──► dicatat di SQLite sebagai "dilihat, ditolak"
                  ▼
          [6] Tulis ke spreadsheet (Google Sheets / Excel)
                  │
                  ▼
          [7] Ringkasan di terminal + file log
```

Prinsip desain:
- **Pemisahan tanggung jawab**: bagian scraper, filter, dan penulis spreadsheet berada di modul terpisah. Kalau JobStreet mengubah tampilan, hanya modul scraper yang diperbaiki.
- **Config-driven**: semua hal yang bersifat preferensi ada di `config.yaml`, bukan di dalam kode.
- **Idempotent**: menjalankan program dua kali berturut-turut tidak menghasilkan baris ganda.
- **Spreadsheet sebagai tampilan, SQLite sebagai ingatan**: status lamaran yang kamu ubah manual di sheet tidak akan bentrok dengan proses dedup.

---

## 4. Tech Stack

| Kebutuhan | Pustaka | Alasan |
|---|---|---|
| Scraping | `playwright` | Mengendalikan browser sungguhan, lebih tahan terhadap situs berbasis JavaScript |
| Config | `pyyaml` | Format YAML mudah dibaca dan diedit manusia |
| Validasi config | `pydantic` | Mendeteksi salah ketik kriteria sebelum scraping dimulai |
| Google Sheets | `gspread` + `google-auth` | Cara paling sederhana menulis ke Google Sheets |
| Excel lokal | `openpyxl` | Opsi tanpa setup Google Cloud |
| Database lokal | `sqlite3` (bawaan Python) | Tanpa instalasi tambahan |
| Logging | `logging` (bawaan) | Cukup untuk kebutuhan ini |
| CLI | `argparse` (bawaan) | Opsi seperti `--dry-run` |
| Test | `pytest` | Menguji logika filter tanpa menyentuh internet |

`requirements.txt`:
```
playwright>=1.40
pyyaml>=6.0
pydantic>=2.0
gspread>=6.0
google-auth>=2.0
openpyxl>=3.1
pytest>=8.0
```

---

## 5. Struktur Folder

```
job-scraper/
├── config.yaml                  # <-- KRITERIA DIISI DI SINI
├── main.py                      # titik masuk program
├── requirements.txt
├── README.md
├── credentials/
│   └── service_account.json     # kunci Google (JANGAN di-commit/dibagikan)
├── data/
│   ├── seen_jobs.db             # database dedup (dibuat otomatis)
│   └── jobs_local.xlsx          # hanya jika memakai output Excel
├── logs/
│   └── scraper.log
├── src/
│   ├── __init__.py
│   ├── config.py                # memuat dan memvalidasi config.yaml
│   ├── models.py                # dataclass Job
│   ├── scraper.py               # logika Playwright
│   ├── filters.py               # filter + scoring
│   ├── storage.py               # SQLite dedup
│   ├── sheet_writer.py          # Google Sheets & Excel writer
│   └── utils.py                 # delay acak, normalisasi teks, logging
└── tests/
    ├── test_filters.py
    ├── test_storage.py
    └── fixtures/                # contoh HTML/JSON tersimpan untuk test
```

Tambahkan `.gitignore` bila memakai Git:
```
credentials/
data/
logs/
.venv/
__pycache__/
```

---

## 6. Desain `config.yaml` (Tempat Mengisi Kriteria)

Ini adalah file yang kamu edit sebelum setiap scraping. Contoh lengkap berikut memakai nilai ilustrasi; **ganti sesuai kebutuhanmu**.

```yaml
# ============================================================
# BAGIAN 1: PENCARIAN
# Menentukan apa yang dicari di JobStreet.
# Program akan menelusuri setiap kombinasi keyword x lokasi.
# ============================================================
search:
  keywords:
    - "IT Support"
    - "Junior Web Developer"
    - "Backend Developer"
  locations:
    - "Semarang"
    - "Jakarta Raya"
    - "Yogyakarta"
  posted_within_days: 7        # hanya lowongan yang diposting N hari terakhir
  max_pages_per_query: 3       # batas halaman hasil per pencarian (hindari scraping berlebihan)
  fetch_detail: true           # buka halaman detail untuk membaca deskripsi lengkap

# ============================================================
# BAGIAN 2: FILTER
# Lowongan harus lolos semua aturan "wajib" di bawah ini.
# Teks dicocokkan tanpa membedakan huruf besar/kecil.
# ============================================================
filters:
  # Judul lowongan yang mengandung kata ini langsung ditolak
  exclude_title_keywords:
    - "senior"
    - "lead"
    - "manager"
    - "head of"
    - "principal"

  # Deskripsi yang mengandung frasa ini ditolak
  exclude_description_keywords:
    - "minimal 3 tahun"
    - "minimal 5 tahun"
    - "min. 3 tahun"
    - "at least 3 years"

  # Perusahaan yang tidak diinginkan (cocok sebagian nama)
  exclude_companies:
    - "nama perusahaan yang ingin dihindari"

  # Tipe kerja yang diterima. Kosongkan ([]) untuk menerima semua.
  work_types:
    - "full time"
    - "magang"

  # Gaji minimum per bulan dalam Rupiah. null = tidak difilter.
  # Catatan: banyak lowongan tidak mencantumkan gaji.
  min_salary_idr: null
  keep_if_salary_unknown: true  # tetap lolos jika gaji tidak dicantumkan

# ============================================================
# BAGIAN 3: SKOR KECOCOKAN
# Lowongan yang lolos filter diberi skor 0-100.
# Hanya yang skornya >= min_score yang masuk spreadsheet.
# ============================================================
scoring:
  min_score: 40
  title_keywords:            # ada di judul = +bobot
    "developer": 25
    "support": 25
    "junior": 15
  description_keywords:      # ada di deskripsi = +bobot (dihitung sekali per kata)
    "fresh graduate": 20
    "python": 10
    "fastapi": 10
    "laravel": 5
    "mysql": 5
    "remote": 5
  location_bonus:            # bonus jika lokasi mengandung teks ini
    "Semarang": 10

# ============================================================
# BAGIAN 4: OUTPUT
# ============================================================
output:
  type: "google_sheets"      # pilihan: "google_sheets" atau "excel"
  google_sheets:
    spreadsheet_id: "ISI_ID_SPREADSHEET_DI_SINI"
    worksheet_name: "Lowongan"
    credentials_file: "credentials/service_account.json"
  excel:
    file_path: "data/jobs_local.xlsx"

# ============================================================
# BAGIAN 5: PERILAKU SCRAPER
# Pengaturan kesopanan dan stabilitas. Ubah hanya jika perlu.
# ============================================================
scraper:
  headless: true             # false = browser terlihat (berguna saat debugging)
  delay_min_sec: 3           # jeda acak antar permintaan
  delay_max_sec: 8
  page_timeout_sec: 30
  max_retries: 2
  max_jobs_per_run: 150      # batas keras per sekali jalan
```

**Cara pakai sehari-hari:** buka `config.yaml` → ubah `keywords`, `locations`, dan aturan filter → simpan → jalankan `python main.py`.

Program wajib **memvalidasi config saat dimulai** dan berhenti dengan pesan jelas bila ada kesalahan (misalnya `min_score` bukan angka, atau `spreadsheet_id` masih berisi teks placeholder).

---

## 7. Skema Spreadsheet

Header (baris 1), dalam urutan kolom:

| Kolom | Isi | Keterangan |
|---|---|---|
| A. Tanggal Ditemukan | `2026-10-13` | Diisi program |
| B. Posisi | Judul lowongan | |
| C. Nama Perusahaan | | **Kolom wajib dari kamu** |
| D. Lokasi | Kota/area | **Kolom wajib dari kamu** |
| E. Link Lowongan | URL lengkap | **Kolom wajib dari kamu** |
| F. Gaji | Teks apa adanya, atau kosong | Banyak yang tidak mencantumkan |
| G. Tipe Kerja | Full time / Magang / dll | |
| H. Tanggal Posting | Jika tersedia | |
| I. Skor | 0-100 | Untuk memprioritaskan lamaran |
| J. Status Lamaran | Dropdown | Kamu yang mengisi manual |
| K. Catatan | Bebas | Kamu yang mengisi manual |
| L. Job ID | ID unik lowongan | Kolom pembantu, boleh disembunyikan |

Pengaturan yang dianjurkan di Google Sheets (dilakukan sekali, manual):
- Bekukan baris 1 (freeze row) agar header selalu terlihat
- Kolom J: Data → Validasi data → Dropdown dengan pilihan `Belum`, `Sudah Dikirim`, `Wawancara`, `Ditolak`, `Diterima`
- Format bersyarat pada kolom J supaya warna berubah sesuai status
- Aktifkan filter (Data → Buat filter) lalu urutkan berdasarkan Skor menurun

Aturan penulisan:
- Program hanya **menambah baris baru di bawah**, tidak pernah menimpa atau menghapus baris yang sudah ada, sehingga kolom J dan K milikmu aman.
- Gunakan `append_rows` agar tidak perlu menghitung baris kosong.

---

## 8. Rencana Pengerjaan Bertahap

Estimasi waktu bersifat kasar untuk satu orang yang sudah familiar dengan Python dasar.

### Fase 0: Persiapan dan Investigasi (±2-3 jam)
Tujuan: memahami cara kerja JobStreet sebelum menulis scraper.

Langkah:
1. Pasang Python 3.11+, buat virtual environment, pasang dependensi, jalankan `playwright install chromium`.
2. Buka `id.jobstreet.com` di browser, lakukan pencarian manual (misalnya "IT Support" di Semarang), lalu amati:
   - Struktur URL hasil pencarian (parameter kata kunci, lokasi, pagination)
   - Struktur URL halaman detail lowongan, dan di mana ID lowongan berada
3. Buka DevTools (F12) → tab **Network** → filter **Fetch/XHR**, lalu muat ulang halaman hasil pencarian. Cek apakah ada permintaan yang mengembalikan **JSON berisi daftar lowongan**.
   - Jika ada, itu jalur yang lebih ringan dan stabil daripada mem-parsing HTML.
   - Jika tidak ada atau terlalu rumit, lanjut dengan mem-parsing HTML lewat Playwright.
4. Di tab **Elements**, catat selector yang stabil untuk: judul, perusahaan, lokasi, link, gaji, tanggal, dan deskripsi. Utamakan atribut seperti `data-automation` dibanding nama class acak.
5. Simpan 3-5 contoh HTML/JSON ke `tests/fixtures/` untuk bahan testing.
6. Catat hasil temuan di `README.md` (bagian "Catatan Investigasi").

Kriteria selesai: kamu bisa menjelaskan dari mana setiap field data diambil dan apa selector atau jalurnya.

> Semua contoh selector pada dokumen ini adalah **placeholder**. Jangan dianggap benar sebelum diverifikasi di Fase 0.

### Fase 1: Kerangka Proyek dan Config (±2 jam)
1. Buat struktur folder (Bagian 5).
2. Tulis `models.py` (dataclass `Job`).
3. Tulis `config.py`: muat YAML, validasi dengan Pydantic, beri pesan error yang jelas.
4. Tulis `utils.py`: setup logging, fungsi `random_delay()`, `normalize_text()`.
5. Buat `config.yaml` awal sesuai Bagian 6.

Kriteria selesai: `python main.py --check-config` menampilkan "Config valid" atau pesan kesalahan yang spesifik.

### Fase 2: Scraper Minimal (±4-6 jam)
Tujuan: untuk satu keyword dan satu lokasi, program mencetak daftar lowongan ke terminal.

1. Buka halaman hasil pencarian dengan Playwright.
2. Ambil dari setiap kartu: Job ID, judul, perusahaan, lokasi, URL, gaji (jika ada), tanggal posting.
3. Tangani pagination sampai `max_pages_per_query`.
4. Tambahkan jeda acak antar halaman.
5. Jalankan dengan `headless: false` dulu untuk melihat apa yang terjadi.

Kriteria selesai: output terminal berisi minimal 20 lowongan dengan field lengkap untuk satu pencarian, tanpa error.

### Fase 3: Detail Lowongan (±2-3 jam)
1. Untuk setiap lowongan baru (yang belum pernah dilihat), buka halaman detail dan ambil deskripsi.
2. Hanya buka detail untuk lowongan yang lolos pra-filter judul (hemat waktu dan lebih sopan ke server).
3. Simpan deskripsi di field `description` pada `Job`.

Kriteria selesai: setiap `Job` yang lolos pra-filter memiliki deskripsi tidak kosong.

### Fase 4: Filter dan Scoring (±3 jam)
1. Implementasikan `filters.py` sesuai Bagian 9.
2. Tulis unit test di `tests/test_filters.py` dengan data buatan.
3. Uji dengan data nyata dari Fase 2-3 dan sesuaikan bobot di `config.yaml`.

Kriteria selesai: test lulus, dan hasil filter pada 20-30 lowongan nyata sesuai penilaianmu secara manual (minimal sebagian besar yang kamu anggap cocok memang lolos).

### Fase 5: Dedup dan Penyimpanan Lokal (±2 jam)
1. Implementasikan `storage.py` dengan tabel SQLite (Bagian 10).
2. Integrasikan: lowongan yang sudah ada di database dilewati.
3. Uji dengan menjalankan program dua kali berturut-turut: run kedua harus menghasilkan 0 lowongan baru.

Kriteria selesai: test dedup lulus, dan run kedua tidak menghasilkan baris ganda.

### Fase 6: Output Spreadsheet (±3-4 jam)
**Jalur A: Excel lokal (mulai dari sini jika ingin cepat)**
1. Implementasikan penulis `openpyxl` yang membuat file dan header jika belum ada, lalu menambah baris.

**Jalur B: Google Sheets**
1. Lakukan setup Google Cloud (Bagian 11).
2. Implementasikan penulis `gspread`.
3. Pastikan header otomatis dibuat bila sheet kosong.

Kriteria selesai: lowongan yang lolos muncul sebagai baris baru di spreadsheet dengan kolom yang benar, dan link bisa diklik.

### Fase 7: Penyatuan, CLI, dan Logging (±2 jam)
1. Rangkai semua tahap di `main.py` (Bagian 8.1).
2. Tambahkan opsi CLI:
   - `--dry-run`: jalankan semuanya tetapi tidak menulis ke spreadsheet/database, hanya mencetak hasil
   - `--check-config`: validasi config lalu keluar
   - `--limit N`: batasi jumlah lowongan (untuk uji coba)
   - `--headed`: tampilkan browser
3. Tulis ringkasan akhir ke terminal: jumlah dilihat, baru, lolos filter, ditulis.
4. Log ke `logs/scraper.log` dengan rotasi sederhana.

Kriteria selesai: satu perintah `python main.py` menjalankan alur penuh dari config sampai spreadsheet.

### Fase 8: Penjadwalan di Laptop (±1 jam)
Lihat Bagian 13.

Kriteria selesai: program berjalan sendiri pada jam yang ditentukan dan baris baru muncul di sheet.

### Fase 9: Hardening (berkelanjutan)
- Penanganan error, retry, dan notifikasi bila scraper rusak (Bagian 12)
- Dokumentasi di README
- Pemeliharaan saat JobStreet mengubah tampilan

### 8.1 Rangkaian `main.py` (pseudo-code)

```python
def run(args):
    cfg = load_config(args.config)                 # validasi Pydantic
    setup_logging()
    db = SeenJobsDB("data/seen_jobs.db")
    writer = build_writer(cfg.output)              # Sheets atau Excel

    new_matches = []
    stats = Counter()

    with Scraper(cfg.scraper) as scraper:
        for keyword in cfg.search.keywords:
            for location in cfg.search.locations:
                for job in scraper.search(keyword, location, cfg.search):
                    stats["dilihat"] += 1
                    if db.has(job.job_id):
                        stats["duplikat"] += 1
                        continue

                    if not passes_prefilter(job, cfg.filters):    # cek judul dulu
                        db.mark(job, status="rejected_title")
                        continue

                    if cfg.search.fetch_detail:
                        job.description = scraper.fetch_description(job.url)

                    result = evaluate(job, cfg)                    # filter + skor
                    if result.passed:
                        job.score = result.score
                        new_matches.append(job)
                        db.mark(job, status="matched")
                    else:
                        db.mark(job, status=f"rejected_{result.reason}")

                    if stats["dilihat"] >= cfg.scraper.max_jobs_per_run:
                        break

    if not args.dry_run:
        writer.append(new_matches)

    print_summary(stats, new_matches)
```

---

## 9. Logika Filter dan Scoring

### Urutan evaluasi
1. **Pra-filter (hanya data kartu, murah):** judul mengandung kata di `exclude_title_keywords` → tolak. Perusahaan ada di `exclude_companies` → tolak.
2. **Filter wajib (setelah ada deskripsi):**
   - Deskripsi mengandung frasa `exclude_description_keywords` → tolak
   - Tipe kerja tidak ada di `work_types` (bila diisi) → tolak
   - Gaji di bawah `min_salary_idr` (bila gaji diketahui) → tolak
   - Gaji tidak diketahui dan `keep_if_salary_unknown: false` → tolak
3. **Scoring:** jumlahkan bobot kecocokan, batasi maksimum 100.
4. **Ambang:** skor `< min_score` → tolak.

### Skeleton `filters.py`

```python
from dataclasses import dataclass

@dataclass
class EvalResult:
    passed: bool
    score: int = 0
    reason: str = ""

def _contains_any(text: str, keywords: list[str]) -> str | None:
    t = text.lower()
    for kw in keywords:
        if kw.lower() in t:
            return kw
    return None

def passes_prefilter(job, filters) -> bool:
    if _contains_any(job.title, filters.exclude_title_keywords):
        return False
    if _contains_any(job.company, filters.exclude_companies):
        return False
    return True

def evaluate(job, cfg) -> EvalResult:
    f, s = cfg.filters, cfg.scoring
    desc = job.description or ""

    if _contains_any(desc, f.exclude_description_keywords):
        return EvalResult(False, reason="desc_excluded")

    if f.work_types and job.work_type:
        if not _contains_any(job.work_type, f.work_types):
            return EvalResult(False, reason="work_type")

    if f.min_salary_idr is not None:
        if job.salary_min_idr is None:
            if not f.keep_if_salary_unknown:
                return EvalResult(False, reason="salary_unknown")
        elif job.salary_min_idr < f.min_salary_idr:
            return EvalResult(False, reason="salary_low")

    score = 0
    title = job.title.lower()
    for kw, weight in s.title_keywords.items():
        if kw.lower() in title:
            score += weight
    desc_l = desc.lower()
    for kw, weight in s.description_keywords.items():
        if kw.lower() in desc_l:
            score += weight
    loc = (job.location or "").lower()
    for kw, bonus in s.location_bonus.items():
        if kw.lower() in loc:
            score += bonus
    score = min(score, 100)

    if score < s.min_score:
        return EvalResult(False, score, reason="low_score")
    return EvalResult(True, score)
```

### Catatan akurasi
- Pencocokan substring sederhana bisa salah, misalnya "lead" cocok dengan "leader" atau "misleading". Pertimbangkan pencocokan **kata utuh** dengan regex `\b...\b` untuk kata pendek.
- Penulisan pengalaman sangat bervariasi ("min. 2 tahun", "2+ years", "pengalaman 2 - 3 tahun"). Untuk hasil lebih baik, tambahkan fungsi yang mengekstrak angka tahun pengalaman dengan regex, lalu bandingkan dengan `max_experience_years` bila kamu ingin menambah opsi tersebut ke config.
- Bobot di config adalah titik awal. Setelah beberapa hari berjalan, tinjau lowongan yang lolos dan yang ditolak, lalu sesuaikan.

---

## 10. Dedup dengan SQLite

Skema:

```sql
CREATE TABLE IF NOT EXISTS seen_jobs (
    job_id      TEXT PRIMARY KEY,
    title       TEXT,
    company     TEXT,
    url         TEXT,
    status      TEXT,      -- matched / rejected_title / rejected_low_score / ...
    score       INTEGER,
    first_seen  TEXT       -- ISO datetime
);
```

Aturan:
- `job_id` diambil dari ID bawaan JobStreet (biasanya angka pada URL lowongan; verifikasi di Fase 0). Jika tidak ada, gunakan hash dari `company + title + location`.
- Lowongan yang **ditolak pun dicatat** supaya tidak diproses ulang tiap hari. Konsekuensinya: jika kamu mengubah kriteria dan ingin menilai ulang lowongan lama, sediakan opsi `--reset-rejected` yang menghapus baris berstatus `rejected_*`.
- Satu lowongan bisa muncul dari beberapa kombinasi keyword/lokasi; dedup berdasarkan `job_id` mencegah baris ganda dalam satu run.

---

## 11. Setup Google Sheets API (Langkah Demi Langkah)

Lakukan sekali. Bagian ini hanya dibutuhkan untuk output `google_sheets`.

1. Buka Google Cloud Console (`console.cloud.google.com`) dan buat project baru, misalnya `job-scraper`.
2. Di **APIs & Services → Library**, aktifkan **Google Sheets API** (dan **Google Drive API** jika diperlukan).
3. Di **APIs & Services → Credentials**, pilih **Create Credentials → Service account**. Beri nama, lalu selesaikan.
4. Buka service account yang dibuat → tab **Keys** → **Add key → Create new key → JSON**. File JSON akan terunduh.
5. Pindahkan file itu ke `credentials/service_account.json`. **Jangan dibagikan atau di-commit ke Git.**
6. Buka file JSON, salin nilai `client_email` (bentuknya `nama@project-id.iam.gserviceaccount.com`).
7. Buat Google Sheet baru. Klik **Share**, lalu tambahkan email service account tadi dengan akses **Editor**.
8. Salin **ID spreadsheet** dari URL: `https://docs.google.com/spreadsheets/d/<INI_ID_NYA>/edit`. Tempel ke `config.yaml` pada `spreadsheet_id`.
9. Beri nama worksheet sesuai `worksheet_name` (default `Lowongan`).

Skeleton `sheet_writer.py` (Google Sheets):

```python
import gspread

HEADERS = [
    "Tanggal Ditemukan", "Posisi", "Nama Perusahaan", "Lokasi",
    "Link Lowongan", "Gaji", "Tipe Kerja", "Tanggal Posting",
    "Skor", "Status Lamaran", "Catatan", "Job ID",
]

class GoogleSheetWriter:
    def __init__(self, cfg):
        gc = gspread.service_account(filename=cfg.credentials_file)
        sh = gc.open_by_key(cfg.spreadsheet_id)
        self.ws = sh.worksheet(cfg.worksheet_name)
        self._ensure_header()

    def _ensure_header(self):
        if self.ws.row_values(1) != HEADERS:
            if not self.ws.row_values(1):
                self.ws.insert_row(HEADERS, 1)

    def append(self, jobs):
        if not jobs:
            return
        rows = [[
            j.found_date, j.title, j.company, j.location,
            j.url, j.salary or "", j.work_type or "", j.posted_date or "",
            j.score, "Belum", "", j.job_id,
        ] for j in jobs]
        self.ws.append_rows(rows, value_input_option="USER_ENTERED")
```

Catatan: pastikan penulisan dilakukan **sekali per run** dengan `append_rows` (batch), bukan satu baris per permintaan, supaya tidak terkena batas kuota API.

Jalur Excel (`openpyxl`): buat workbook bila belum ada, tulis header, lalu `ws.append(row)` per lowongan dan `wb.save(path)`. Pastikan file Excel **tidak sedang terbuka** saat program berjalan, karena akan gagal disimpan di Windows.

---

## 12. Scraper: Pendekatan, Etika, dan Ketahanan

### Skeleton `scraper.py` (Playwright, sinkron)

```python
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from .utils import random_delay

class Scraper:
    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.cfg.headless)
        self._ctx = self._browser.new_context(
            locale="id-ID",
            viewport={"width": 1366, "height": 800},
        )
        self.page = self._ctx.new_page()
        self.page.set_default_timeout(self.cfg.page_timeout_sec * 1000)
        return self

    def __exit__(self, *exc):
        self._ctx.close()
        self._browser.close()
        self._pw.stop()

    def search(self, keyword, location, search_cfg):
        # TODO (Fase 0): isi pola URL & selector hasil investigasi
        for page_no in range(1, search_cfg.max_pages_per_query + 1):
            url = self._build_search_url(keyword, location, page_no, search_cfg)
            self.page.goto(url)
            cards = self.page.query_selector_all("SELECTOR_KARTU_LOWONGAN")
            if not cards:
                break
            for card in cards:
                yield self._parse_card(card)
            random_delay(self.cfg.delay_min_sec, self.cfg.delay_max_sec)

    def fetch_description(self, url):
        # TODO (Fase 0): selector deskripsi
        self.page.goto(url)
        el = self.page.query_selector("SELECTOR_DESKRIPSI")
        random_delay(self.cfg.delay_min_sec, self.cfg.delay_max_sec)
        return el.inner_text() if el else ""
```

### Etika dan kesopanan scraping
- Gunakan jeda acak 3-8 detik antar permintaan, dan jangan menjalankan secara paralel.
- Batasi volume: `max_pages_per_query` dan `max_jobs_per_run`.
- Jalankan paling banyak sekali sehari. Lowongan tidak berubah tiap menit.
- Jangan mencoba melewati CAPTCHA atau pemblokiran secara paksa. Jika muncul, hentikan run dan catat di log.
- Untuk pemakaian pribadi saja. Jangan menjual atau mendistribusikan ulang data.

### Penanganan error
| Situasi | Perilaku yang diinginkan |
|---|---|
| Timeout satu halaman | Retry sampai `max_retries`, lalu lewati dan catat |
| Selector tidak ditemukan (struktur berubah) | Catat error jelas ("kemungkinan struktur situs berubah"), hentikan run, **jangan menulis data setengah jadi** |
| CAPTCHA / halaman verifikasi terdeteksi | Hentikan run, catat, jangan retry agresif |
| Gagal menulis ke Sheets | Simpan hasil ke file cadangan `data/pending_YYYYMMDD.json`, lalu coba lagi pada run berikutnya |
| Config tidak valid | Berhenti sebelum scraping dan tampilkan pesan spesifik |

### Deteksi dini kerusakan
Tambahkan pemeriksaan sederhana: jika satu run menghasilkan **0 kartu lowongan** untuk semua pencarian, perlakukan sebagai kemungkinan scraper rusak (bukan "memang tidak ada lowongan") dan tampilkan peringatan mencolok di log serta terminal.

### Rencana cadangan bila scraping tidak memungkinkan
Jika JobStreet memblokir secara konsisten, gunakan fitur **job alert via email** milik JobStreet, lalu buat program kecil yang membaca email alert (Gmail API atau IMAP), mengekstrak link dan data lowongan, dan memasukkannya ke spreadsheet dengan alur filter yang sama. Modul `filters.py`, `storage.py`, dan `sheet_writer.py` bisa dipakai ulang tanpa perubahan.

---

## 13. Penjadwalan di Laptop

Karena berjalan di laptop, program hanya berjalan saat laptop menyala. Beberapa pengaturan agar tetap andal:

### Windows (Task Scheduler)
Perintah cepat (sesuaikan path):
```
schtasks /Create /SC DAILY /TN "JobScraper" /ST 08:00 ^
  /TR "\"C:\path\job-scraper\.venv\Scripts\python.exe\" \"C:\path\job-scraper\main.py\""
```
Lalu di Task Scheduler (GUI), buka properti tugas dan atur:
- **Settings → Run task as soon as possible after a scheduled start is missed**: dicentang (supaya tetap jalan jika laptop mati pada jam 08:00)
- **Start in (optional)**: isi dengan folder proyek (`C:\path\job-scraper`), supaya path relatif seperti `config.yaml` terbaca
- **Conditions**: atur sesuai kebutuhan terkait mode baterai dan koneksi jaringan

### Linux / macOS (cron)
```
0 8 * * * cd /path/job-scraper && /path/job-scraper/.venv/bin/python main.py >> logs/cron.log 2>&1
```
Pada macOS, `launchd` lebih andal untuk tugas harian di laptop yang sering tidur.

### Catatan penting
- Selalu gunakan **path absolut ke Python di dalam virtual environment**, bukan `python` biasa.
- Program harus memakai path relatif terhadap lokasi `main.py` (misalnya lewat `Path(__file__).parent`), bukan terhadap working directory saat dijalankan.
- Gunakan `headless: true` untuk run terjadwal.

---

## 14. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Struktur JobStreet berubah | Scraper berhenti bekerja | Modul scraper terpisah, deteksi "0 hasil", fixture untuk test, siap diperbaiki cepat |
| Diblokir / CAPTCHA | Tidak bisa mengambil data | Jeda acak, volume rendah, 1x sehari, rencana cadangan job alert email |
| Pelanggaran ketentuan layanan | Akun/IP dibatasi | Pemakaian pribadi, volume kecil, tidak login, tidak menjual data |
| Filter terlalu ketat / longgar | Lowongan bagus terlewat atau sheet penuh sampah | Tinjau hasil berkala, sesuaikan bobot, gunakan `--dry-run` untuk uji |
| Kunci Google bocor | Akses tidak sah ke sheet | Jangan commit `credentials/`, gunakan `.gitignore`, batasi share sheet |
| Laptop mati saat jadwal | Run terlewat | Opsi "run as soon as possible after missed start" |
| Data lowongan kedaluwarsa | Melamar ke lowongan yang sudah tutup | Simpan tanggal posting, cek manual sebelum melamar |

### Catatan hukum dan ketentuan layanan
JobStreet (bagian dari SEEK) umumnya melarang pengambilan data otomatis dalam syarat penggunaannya. Proyek ini ditujukan untuk pemakaian pribadi berfrekuensi rendah, tetapi risikonya tetap ada dan menjadi tanggung jawabmu. Baca syarat penggunaan terbaru di situsnya sebelum memulai. Dokumen ini bukan nasihat hukum.

---

## 15. Strategi Pengujian

| Jenis | Apa yang diuji | Cara |
|---|---|---|
| Unit | `filters.py`: tolak/lolos, skor | `pytest` dengan data `Job` buatan |
| Unit | `storage.py`: dedup, status | SQLite in-memory (`:memory:`) |
| Unit | `config.py`: config valid/invalid | Beberapa file YAML contoh |
| Parser | Ekstraksi field dari HTML/JSON | Gunakan fixture di `tests/fixtures/`, tanpa internet |
| Integrasi | Alur penuh | `python main.py --dry-run --limit 10` |
| Manual | Hasil di spreadsheet | Cek kolom, link bisa diklik, tidak ada baris ganda |

Contoh test:
```python
def test_senior_title_rejected(cfg):
    job = make_job(title="Senior Backend Developer", company="PT A")
    assert passes_prefilter(job, cfg.filters) is False

def test_fresh_grad_scores_above_threshold(cfg):
    job = make_job(
        title="Junior Web Developer",
        description="Fresh graduate welcome. Python, FastAPI.",
        location="Semarang",
    )
    result = evaluate(job, cfg)
    assert result.passed and result.score >= cfg.scoring.min_score
```

---

## 16. Pengembangan Lanjutan (Opsional, Setelah Versi Dasar Stabil)

1. Notifikasi Telegram ringkas setelah tiap run ("5 lowongan baru, skor tertinggi: ...")
2. Sumber tambahan: Glints, LinkedIn, Kalibrr, situs karier perusahaan
3. Ekstraksi pengalaman minimum otomatis dengan regex
4. Opsi `max_experience_years` dan `education_required` di config
5. Penandaan lowongan yang sudah ditutup
6. Skor berbasis kemiripan teks antara deskripsi lowongan dan CV (misalnya TF-IDF)
7. Dashboard ringan untuk meninjau statistik run

---

## 17. Instruksi Ringkas untuk AI Coding Agent

Bagian ini bisa disalin sebagai prompt bila pengerjaan dibantu AI agent:

> Bangun proyek Python "job-scraper" sesuai dokumen planning ini. Ikuti struktur folder di Bagian 5 dan desain `config.yaml` di Bagian 6. Kerjakan per fase (Bagian 8) dan berhenti di akhir tiap fase untuk saya verifikasi. Ketentuan: (1) seluruh preferensi pengguna berasal dari `config.yaml` yang divalidasi Pydantic; (2) pisahkan modul scraper, filter, storage, dan sheet writer; (3) jangan menebak selector JobStreet, minta saya menjalankan investigasi Fase 0 dan memberikan hasilnya atau contoh HTML/JSON; (4) program tidak boleh menimpa atau menghapus baris yang sudah ada di spreadsheet; (5) sediakan opsi CLI `--dry-run`, `--check-config`, `--limit`, `--headed`; (6) tulis unit test untuk filter, dedup, dan config; (7) jangan pernah menyimpan kredensial di dalam kode.

---

## 18. Checklist Akhir

- [ ] Fase 0: struktur URL, selector/endpoint, dan ID lowongan sudah dicatat
- [ ] `config.yaml` terisi dan lolos `--check-config`
- [ ] Scraper mengambil lowongan untuk satu pencarian dengan benar
- [ ] Deskripsi detail terbaca
- [ ] Filter dan skor diuji dan terasa pas pada data nyata
- [ ] Menjalankan dua kali berturut-turut tidak menghasilkan baris ganda
- [ ] Spreadsheet terisi dengan kolom yang benar dan link yang bisa diklik
- [ ] Dropdown Status Lamaran dan filter di sheet sudah dipasang
- [ ] `--dry-run` berfungsi
- [ ] Log tertulis dan peringatan "0 hasil" bekerja
- [ ] Penjadwalan berjalan di laptop
- [ ] `credentials/` masuk `.gitignore`
- [ ] README berisi cara pakai dan catatan investigasi
