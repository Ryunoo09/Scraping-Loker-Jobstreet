# Planning: LinkedIn Scraper **Mandiri** → Spreadsheet Terpisah

> Dokumen ini adalah **rencana** penambahan fitur scraper **LinkedIn** ke proyek ini.
>
> Status: **RENCANA — belum dieksekusi.** Tidak ada kode/config yang dibuat berdasarkan
> dokumen ini sampai kamu give the go-ahead.
>
> Sifat fitur: **mandiri (standalone)**. Tidak mengubah satu pun file JobStreet yang
> sudah ada — semua kode, config, data, dan log LinkedIn berada di file terpisah.

Sumber acuan gaya & standar: [`planning-job-scraper-jobstreet.md`](../planning-job-scraper-jobstreet.md)
dan [`EXECUTION-PLAN.md`](../EXECUTION-PLAN.md).

---

## 1. Keputusan yang sudah dikunci

| Aspek | Keputusan | Alasan |
|---|---|---|
| Pendekatan data | **Opsi A — guest/publik, tanpa login** | Aman, tanpa risiko ban akun |
| Integrasi kode | **Paket & CLI terpisah** | Nol perubahan pada kode JobStreet |
| Output | **File/sheet terpisah** | Tidak menyentuh `data/jobs_local.xlsx` |
| Dedup | **SQLite terpisah** (`data/linkedin_seen.db`) | Isolasi penuh dari `seen_jobs.db` |

---

## 2. Jawaban singkat: "Apakah bisa?"

**Bisa secara teknis**, tetapi LinkedIn **jauh lebih sulit dan rapuh** daripada JobStreet,
terutama pada mode guest (tanpa login).

| Aspek | JobStreet (sudah ada) | LinkedIn guest (target) |
|---|---|---|
| Halaman publik tanpa login | Ya, HTML penuh | Terbatas (auth-wall setelah beberapa hasil) |
| Atribut stabil (`data-automation`) | Ya, sangat stabil | Tidak — class ter-obfuscate & berubah |
| Data JSON "server-state" (waktu posting pasti) | Ya (`SEEK_REDUX_DATA`) | Tidak; hanya elemen `<time datetime="...">` |
| Hasil per pencarian | Ratusan (paginasi penuh) | ±25–50 (endpoint guest mentok cepat) |
| Detail lowongan | Publik, lengkap | Sering terpotong / wajib login |
| Anti-bot | Cloudflare Turnstile (lewat dengan `--headed`) | Deteksi bot + rate-limit |

**Konsekuensi yang harus diterima** (konsekuensi dari pilihan Opsi A):
- Volume hasil terbatas.
- Deskripsi/kualifikasi sering tidak lengkap → ditandai `detail_incomplete`.
- Endpoint guest **tidak terdokumentasi** dan bisa berubah/diblokir kapan saja.
- Tidak ada risiko ban akun (karena tidak login).

---

## 3. Ruang lingkup

### Termasuk (In Scope)
- Paket Python baru `src/linkedin_scraper/` yang sepenuhnya mandiri.
- Entry point baru `linkedin_main.py` (paralel dengan `main.py`).
- Config baru `config_linkedin.yaml` (+ contoh aman di-commit).
- Scraping halaman kartu LinkedIn guest + detail best-effort.
- Filter, scoring, dedup, dan writer sendiri.
- Fixture HTML asli + test offline.

### Tidak Termasuk (Out of Scope)
- Perubahan apa pun pada kode JobStreet (`src/job_scraper/**`).
- Login, penyimpanan cookie/sesi, atau akun LinkedIn.
- Bypass proteksi bot/rate-limit.
- Melamar otomatis (tetap manual).
- Migrasi/merge ke `data/jobs_local.xlsx` atau `seen_jobs.db`.

> **Aturan emas:** kalau sebuah perubahan menyentuh file JobStreet yang sudah ada,
> perubahan itu **keluar dari rencana ini** dan harus dibahas ulang.

---

## 4. Struktur file baru

Semua entri di bawah **baru**. Tidak ada file lama yang diubah.

```text
Scraping Loker/
├── linkedin_main.py                    # entry point paralel main.py
├── config_linkedin.example.yaml        # contoh config (aman di-commit)
├── config_linkedin.yaml                # config kamu (gitignored)
├── docs/
│   ├── planning-linkedin.md            # dokumen ini
│   └── fase0-linkedin.md               # hasil investigasi selector (dibuat di L0)
├── src/linkedin_scraper/               # paket mandiri (~600 LOC)
│   ├── __init__.py
│   ├── cli.py                          # argparse + orkestrasi
│   ├── config.py                       # Pydantic v2 (pola sama dgn job_scraper/config.py)
│   ├── models.py                       # JobLinkedIn
│   ├── scraper.py                      # Playwright: ambil HTML mentah guest
│   ├── parsers.py                      # selector LinkedIn (hasil Fase 0)
│   ├── filters.py                      # filter + scoring
│   ├── storage.py                      # SQLite dedup terpisah
│   ├── utils.py                        # logging, delay, normalize, WIB
│   └── writers/
│       ├── __init__.py
│       ├── base.py
│       ├── excel.py                    # data/linkedin_jobs.xlsx
│       └── sheets.py                   # opsional, sheet berbeda
├── scripts/
│   ├── capture_linkedin.py             # Fase 0: simpan fixture (headed)
│   └── smoke_linkedin.py               # smoketest scraper → parser
└── tests/
    ├── test_linkedin_config.py
    ├── test_linkedin_parsers.py
    ├── test_linkedin_filters.py
    ├── test_linkedin_storage.py
    ├── test_linkedin_writers.py
    ├── test_linkedin_cli.py
    └── fixtures/linkedin/              # HTML asli hasil Fase 0
```

### 4.1 Kebijakan duplikasi kode

Cara "script terpisah" ini memang menduplikasi sebagian logika (`filters`, `utils`,
`writers`). Itu adalah **trade-off yang dipilih** (isolasi penuh).

Agar duplikasi terkendali, hanya **helper murni yang stabil** yang boleh di-*import*
dari paket lama (read-only, tanpa mengubah paket lama):

- `from job_scraper.utils import normalize_text, to_wib`
- `from job_scraper.filters import evaluate` (opsional; fungsi murni tanpa I/O)

Sisanya disalin penuh ke paket baru. Kalau kamu mau **nol ketergantungan**, salin
semua dan JANGAN import dari `job_scraper` sama sekali.

---

## 5. Arsitektur & alur

```text
config_linkedin.yaml ──► linkedin_main.py
                              │
                              ▼
                     [1] Muat & validasi config (Pydantic)
                              │
                              ▼
                     [2] Scraper (Playwright) — guest:
                           untuk tiap keyword:
                             buka /jobs/search & guest API
                             kumpulkan kartu (+ detail best-effort)
                              │
                              ▼
                     [3] Parser → objek JobLinkedIn
                              │
                              ▼
                     [4] Dedup (SQLite: data/linkedin_seen.db)
                              │
                              ▼
                     [5] Filter + Scoring (config_linkedin.yaml)
                              │
                              ▼
                     [6] Tulis ke spreadsheet terpisah
                              │
                              ▼
                     [7] Ringkasan terminal + logs/linkedin_scraper.log
```

Pemisahan tanggung jawab tetap sama seperti JobStreet:
`scraper.py` **hanya** mengambil HTML mentah; `parsers.py` **hanya** mengubah HTML
menjadi objek domain. Bila LinkedIn berubah, cukup perbaiki `parsers.py` + fixture.

---

## 6. Contoh `config_linkedin.yaml`

```yaml
# ============================================================
# LinkedIn Scraper — CONTOH konfigurasi (mandiri)
# Salin menjadi config_linkedin.yaml lalu sesuaikan.
# ============================================================

# ------------------------------------------------------------
# BAGIAN 1: PENCARIAN
# ------------------------------------------------------------
search:
  keywords:
    - "IT Support"
    - "Junior Web Developer"
  location: "Indonesia"          # teks bebas; geoId opsional
  posted_within_days: 7          # -> f_TPR=r604800
  work_types: ["F"]              # F=full-time, I=internship, C=contract
  experience_levels: [1, 2]      # 1=Entry, 2=Associate, 3=Senior, 4=Director...
  max_pages_per_query: 2         # guest biasanya mentok setelah 1-2 halaman
  fetch_detail: true

# ------------------------------------------------------------
# BAGIAN 2: FILTER (harus lolos semua aturan wajib)
# ------------------------------------------------------------
filters:
  exclude_title_keywords:
    - "senior"
    - "lead"
    - "manager"
  exclude_description_keywords:
    - "minimal 3 tahun"
    - "at least 3 years"
  exclude_companies: []
  min_salary_idr: null
  keep_if_salary_unknown: true

# ------------------------------------------------------------
# BAGIAN 3: SKOR KECOCOKAN (0-100)
# ------------------------------------------------------------
scoring:
  min_score: 40
  title_keywords:
    "developer": 25
    "support": 25
    "junior": 15
  description_keywords:
    "fresh graduate": 20
    "python": 10
  location_bonus:
    "Jakarta": 10

# ------------------------------------------------------------
# BAGIAN 4: OUTPUT (TERPISAH dari JobStreet)
# ------------------------------------------------------------
output:
  type: "excel"
  excel:
    file_path: "data/linkedin_jobs.xlsx"
  # google_sheets:
  #   spreadsheet_id: "ISI_ID_SHEET_TERPISAH"
  #   worksheet_name: "LinkedIn"
  #   credentials_file: "credentials/service_account.json"

# ------------------------------------------------------------
# BAGIAN 5: PERILAKU SCRAPER (lebih sopan dari JobStreet)
# ------------------------------------------------------------
scraper:
  headless: true
  delay_min_sec: 6               # jeda acak antar permintaan
  delay_max_sec: 15
  page_timeout_sec: 30
  max_retries: 2
  max_jobs_per_run: 100
```

---

## 7. Skema spreadsheet LinkedIn

File **sendiri** (`data/linkedin_jobs.xlsx`), tidak menyentuh `data/jobs_local.xlsx`.

| Kolom | Nama | Diisi oleh |
|---|---|---|
| A | Tanggal Ditemukan | Program |
| B | Posisi | Program |
| C | Nama Perusahaan | Program |
| D | Lokasi | Program |
| E | Link Lowongan | Program (bisa diklik) |
| F | Gaji | Program (bila ada) |
| G | Tipe Kerja | Program |
| H | Tanggal Posting | Program (`<time datetime>`; fallback teks relatif) |
| I | Skor | Program (0-100) |
| J | Status Lamaran | **Kamu** (dropdown manual) |
| K | Catatan | **Kamu** |
| L | Deskripsi | Program |
| M | Kualifikasi | Program |
| N | Job ID | Program |
| O | Detail Lengkap? | Program (`Ya`/`Tidak`) |

> Sama seperti JobStreet: penulisan **append-only**. Kolom J & K milikmu tidak pernah ditimpa.

---

## 8. Rencana seleksi & URL (indikatif — **wajib diverifikasi di L0**)

| Keperluan | Pola indikatif |
|---|---|
| Pencarian | `/jobs/search?keywords={kw}&location={loc}&start={n}` |
| Rentang waktu | `f_TPR=r604800` (7 hari) |
| Tipe kerja | `f_JT=F` (full-time), `f_JT=I` (internship) |
| Pengalaman | `f_E=1,2` |
| Kartu (guest API) | `/jobs-guest/jobs/api/seeMoreJobPostings/search?...` |
| Detail (guest API) | `/jobs-guest/jobs/api/jobPosting/{id}` |
| Fallback DOM kartu | `div.base-card` / `li`, `.base-search-card__title`, `.base-search-card__subtitle`, `.job-search-card__location`, `a.base-search-card__full-link`, `time[datetime]` |

> Semua di atas **indikatif**. Tidak boleh masuk `parsers.py` sebelum dikonfirmasi
> dengan fixture HTML asli di L0 (prinsip spec §17 poin 3: jangan menebak selector).

---

## 9. Milestone eksekusi (tiap tahap berhenti untuk verifikasi)

### L0 — Fase 0: Investigasi guest LinkedIn
- `scripts/capture_linkedin.py` (Playwright **headed**) menyimpan HTML asli:
  - halaman `jobs/search` publik,
  - fragmen `jobs-guest/jobs/api/seeMoreJobPostings/search`,
  - detail `jobs-guest/jobs/api/jobPosting/<id>`.
- Tulis `docs/fase0-linkedin.md`: tabel selector terverifikasi + pola URL + param filter.
- **DoD:** fixture nyata tersimpan; tabel selector terisi; **nol tebakan**; dikonfirmasi
  apakah guest endpoint masih mengembalikan kartu saat ini.
- **Commit:** `docs(linkedin): capture guest fixtures & selectors (L0)`

### L1 — Kerangka paket & config
- `config.py` (Pydantic v2, pola sama: `extra="forbid"`, validator delay & output).
- `config_linkedin.example.yaml` + flag `--check-config`.
- **DoD:** `python linkedin_main.py --check-config` sukses; error jelas saat config salah.
- **Commit:** `feat(linkedin): package skeleton & config validation (L1)`

### L2 — Scraper minimal (kartu)
- Build URL pencarian dengan filter `f_TPR` / `f_JT` / `f_E` + paginasi `start` (kelipatan 25).
- Ambil HTML kartu; deteksi dinding login / limit / 0 hasil.
- Retry + delay sesuai config.
- **DoD:** smoketest ambil ≥1 halaman kartu nyata.
- **Commit:** `feat(linkedin): guest search scraper (L2)`

### L3 — Parser kartu + fixture test
- `parsers.py`: kartu → `JobLinkedIn`; `posted_at` dari `<time datetime="...">`;
  ID dari `data-entity-urn` atau URL.
- `StructureChangedError` bila field wajib hilang.
- **DoD:** test parser ≥90% coverage berbasis fixture.
- **Commit:** `feat(linkedin): parse job cards + fixtures (L3)`

### L4 — Detail lowongan (best-effort)
- Fetch `jobs-guest/jobs/api/jobPosting/<id>` → deskripsi & tipe kerja bila tersedia.
- Guest sering terpotong: simpan apa adanya, set `detail_incomplete = true`.
- **DoD:** test parse detail + fallback saat detail kosong/gagal.
- **Commit:** `feat(linkedin): best-effort detail parsing (L4)`

### L5 — Filter, scoring, dedup
- `filters.py` (port/import) + `storage.py` (DB terpisah `data/linkedin_seen.db`).
- **DoD:** test filter/scoring/dedup hijau; idempotent (run 2× tidak menghasilkan baris ganda).
- **Commit:** `feat(linkedin): filters, scoring & dedup (L5)`

### L6 — Writer, CLI lengkap, dokumentasi
- `writers/excel.py` → `data/linkedin_jobs.xlsx` (append-only); `sheets.py` opsional
  (spreadsheet/worksheet berbeda).
- CLI: `--config`, `--check-config`, `--dry-run`, `--limit N`, `--headed`, `--reset-rejected`.
- Ringkasan terminal + `logs/linkedin_scraper.log`.
- Update `.gitignore` (`config_linkedin.yaml`, `data/linkedin_*`, `tests/fixtures/linkedin/_raw/`).
- **DoD:** quality gate hijau; catatan singkat penggunaan.
- **Commit:** `feat(linkedin): writers, CLI & docs (L6)`

**Estimasi:** L0 ±2–3 jam · L1 ±2 jam · L2 ±3–4 jam · L3 ±3 jam · L4 ±2–3 jam ·
L5 ±2–3 jam · L6 ±2–3 jam → **±16–21 jam**.

### 9.1 Skill wajib & commit per milestone (MENGIKAT)

Sebelum dan selama eksekusi, **setiap perubahan wajib menerapkan skill berikut**:

| Skill | Peran dalam eksekusi |
|---|---|
| `python-pro` | Standar Python 3.12+, type hint lengkap, Pydantic v2, pola async/sync tepat |
| `clean-code` | SRP, KISS, YAGNI, guard clause, fungsi kecil, tanpa komentar berlebihan |
| `ponytail` | Ambil solusi terkecil yang lengkap; hindari over-engineering; setiap shortcut diberi komentar |
| `code-reviewer` | Review tiap perubahan sebelum commit (checklist + quality checker) |
| `git-commit-helper` | Pesan commit Conventional Commits, atomik per fase |

**Alur kerja tiap milestone (fase):**

1. **Implementasi** perubahan (terapkan `python-pro` + `clean-code` + `ponytail`).
2. **Quality gate** (§11) — jalankan `ruff format`, `ruff check`, `mypy`, `pytest`, `bandit`.
3. **Review** perubahan (`code-reviewer`) — perbaiki temuan dulu sebelum lanjut.
4. **Commit** atomik (`git-commit-helper`) — **satu commit per milestone/fase**, hanya
   setelah DoD milestone lolos.

**Aturan commit (mengikat):**

- Format **Conventional Commits**: `<type>(<scope>): <description>`, scope `linkedin`.
- **Satu milestone = satu commit logis.** Jangan menggabungkan beberapa milestone dalam satu commit.
- Commit **hanya setelah DoD milestone lolos** (bukan di tengah pekerjaan).
- Jangan commit: `config_linkedin.yaml`, `data/linkedin_*`, `logs/` (masuk `.gitignore`).
- Tipe yang dipakai: `feat` (kode/uji fitur), `docs` (dokumen/fixture investigasi),
  `chore` (tooling/`.gitignore`), `refactor` (bila ada pembersihan).

---

## 10. Standar engineering (mengikuti `EXECUTION-PLAN.md` §3)

- Type hint lengkap; `mypy --strict` hijau untuk `src/linkedin_scraper`.
- **Pydantic v2** untuk semua input eksternal (config YAML, baris spreadsheet).
- PEP 8 via `ruff format` + `ruff check` (line length 100, target `py312`).
- Docstring Google-style untuk API publik.
- Custom exception (bukan `Exception` generik).
- Test coverage ≥90% untuk modul non-jaringan; `scraper.py` dikecualikan.
- `bandit -r src` bersih; tidak ada rahasia di kode/log.
- Config-driven: nol nilai preferensi di-hardcode.
- Idempotent; append-only ke spreadsheet.

---

## 11. Strategi testing

- Offline penuh pakai fixture LinkedIn di `tests/fixtures/linkedin/`.
- `scraper.py` dikecualikan dari coverage (butuh browser + internet), diuji lewat
  smoketest manual `scripts/smoke_linkedin.py`.
- Quality gate per milestone:

```powershell
.\.venv\Scripts\ruff.exe format src/linkedin_scraper tests linkedin_main.py
.\.venv\Scripts\ruff.exe check src/linkedin_scraper tests linkedin_main.py
.\.venv\Scripts\mypy.exe src/linkedin_scraper
.\.venv\Scripts\pytest.exe tests -k linkedin --cov=linkedin_scraper --cov-report=term-missing
.\.venv\Scripts\bandit.exe -r src/linkedin_scraper
```

---

## 12. Risiko & mitigasi

| Risiko | Mitigasi |
|---|---|
| Endpoint guest berubah/diblokir | Deteksi 0 kartu → berhenti + pesan jelas; selector terisolasi di `parsers.py` |
| Hasil & detail terbatas | Tandai `detail_incomplete`; dokumentasikan batasnya di catatan penggunaan |
| Melanggar ToS LinkedIn | Tanpa login, volume kecil, delay besar (6–15 dtk), tanpa bypass proteksi |
| Duplikasi logika filter/writer | Import hanya helper murni yang stabil; sisanya salin terkendali |
| Config/data tercampur dengan JobStreet | Nama file, DB, dan log **terpisah total** + entri `.gitignore` sendiri |
| Google Sheets tertukar | `worksheet_name`/`spreadsheet_id` berbeda; validasi placeholder di config |

### Catatan hukum & etika
Scraping LinkedIn melanggar Ketentuan Layanan mereka. Fitur ini disediakan untuk
pengumpulan data pribadi berskala kecil dan **bukan** untuk didistribusikan/dijual.
Tidak ada upaya menembus proteksi bot/captcha. Gunakan dengan kesadaran risikomu sendiri.

---

## 13. Definition of Done (fitur LinkedIn)

1. L0–L6 selesai dan tiap DoD-nya terverifikasi.
2. Tidak ada satu pun file `src/job_scraper/**`, `config.yaml`, `data/jobs_local.xlsx`,
   atau `seen_jobs.db` yang berubah.
3. `python linkedin_main.py --check-config` dan `--dry-run --limit 5` berjalan bersih.
4. Test LinkedIn hijau dengan coverage ≥90% modul non-jaringan.
5. `.gitignore` mencakup config & data LinkedIn.
6. Catatan penggunaan (cara jalan, batasan guest, ToS) tersedia.
7. **Setiap milestone menghasilkan tepat satu commit atomik** (aturan `git-commit-helper`,
   §9.1) dan sudah melewati review `code-reviewer`.
8. Skill `python-pro`, `clean-code`, `ponytail`, `code-reviewer`, dan `git-commit-helper`
   diterapkan pada setiap fase.

---

## 14. Yang saya butuhkan darimu sebelum eksekusi

1. Konfirmasi untuk mulai **L0** (investigasi Fase 0 guest LinkedIn) — saya akan
   menjalankan browser headed sekali untuk mengambil fixture.
2. Boleh/tidaknya menjalankan Playwright headed di mesinmu (butuh Chromium).
3. Preferensi paket: **import helper murni dari `job_scraper`** atau **nol
   ketergantungan (salin semua)**.
