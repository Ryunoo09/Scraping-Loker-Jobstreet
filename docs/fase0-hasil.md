# Hasil Investigasi Fase 0 — JobStreet (terverifikasi)

> Sumber: fixture HTML nyata dari `tests/fixtures/` (diambil via
> `scripts/capture_fase0.py`, browser headed).
> **Semua selector di bawah ini berasal dari observasi HTML asli, bukan tebakan.**
> Ini menjadi acuan tunggal `scraper.py` (M5) dan `parsers.py` (M6).

Tanggal: 2026-10-13 · Situs: `id.jobstreet.com` (JobStreet Indonesia, platform SEEK).

---

## 1. Pola URL

| Keperluan | Pola | Contoh |
|---|---|---|
| Hasil pencarian | `/id/{Keyword-dengan-hubung}-jobs/in-{Lokasi}` | `/id/Junior-developer-jobs/in-Jawa-Barat` |
| Halaman ke-N | tambahkan `?page=N` (1-based) | `.../in-Jawa-Barat?page=2` |
| Detail lowongan | `/id/job/{Job ID}` (+ query `?type=standard&ref=...`) | `/id/job/95227572?type=standard&ref=search-standalone` |

- **Job ID**: deretan angka pada path `/id/job/{id}` — dan juga tersedia langsung
  sebagai atribut `data-job-id` pada elemen kartu.
- **Endpoint JSON**: tidak ada yang praktis (halaman server-rendered + hydrate).
  Ada globals `window.SEEK_REDUX_DATA` / `window.SK_DL`, tetapi jalur yang dipakai
  adalah **HTML** (sesuai spec §1/§12).

## 2. Selector — daftar hasil (kartu)

| Field | Selector | Catatan |
|---|---|---|
| Kartu (pembungkus) | `article[data-automation="normalJob"]` | punya `data-job-id="<ID>"`, `data-testid="job-card"` |
| Job ID | `[data-automation="normalJob"]@data-job-id` | 100% andal, tidak perlu parse URL |
| Judul | `[data-automation="jobTitle"]` | elemen `<a>`, teks judul |
| Link detail | `[data-automation="jobTitle"]@href` | relatif (`/id/job/...`), jadikan absolut |
| Nama perusahaan | `[data-automation="jobCompany"]` | |
| Lokasi | `[data-automation="jobLocation"]` | pembungkus: `jobCardLocation` |
| Gaji | `[data-automation="jobSalary"]` | **tidak selalu ada** (10 dari 30 kartu pada sampel) |
| Tanggal posting | `[data-automation="jobListingDate"]` | teks **relatif** (`12 jam yang lalu`, `Listed more than twelve days ago`) |
| Deskripsi singkat | `[data-automation="jobShortDescription"]` | teaser, bukan deskripsi penuh |
| Klasifikasi | `[data-automation="jobClassification"]` | mis. `(Teknologi Informasi & Komunikasi)` |
| Sub-klasifikasi | `[data-automation="jobSubClassification"]` | mis. `Developer/Programmer` |

- **Tipe kerja TIDAK tersedia lewat `data-automation` di kartu.** Di kartu hanya
  muncul sebagai teks biasa (`... lowongan kerja Full time`). Karena itu `work_type`
  diambil dari halaman **detail** (lihat §3) — diisi saat `fetch_detail`.
- Total hasil ada di `[data-automation="totalJobsMessage"]` (mis. `68 pekerjaan`).

## 2.1 Data server-state — waktu posting pasti

Selain DOM, halaman hasil menyertakan satu blok data aplikasi:

| Hal | Nilai |
|---|---|
| Lokasi | `<script data-automation="server-state">` (tepat **satu** blok) |
| Variabel | `window.SEEK_REDUX_DATA` (bersama `window.SEEK_CONFIG`) |
| Jalur data | `results.results.jobs` — daftar objek lowongan (30 pada sampel) |
| Kunci per lowongan | `id` (sama dengan `data-job-id`), `listingDate`, `listingDateDisplay` |

| Kunci JSON | Contoh | Arti |
|---|---|---|
| `id` | `"95227572"` | Job ID (kunci pencocokan ke kartu) |
| `listingDate` | `"2026-10-13T02:58:53.000Z"` | **waktu posting pasti**, ISO 8601 UTC |
| `listingDateDisplay` | `"12 jam yang lalu"` | teks relatif — sama dengan `jobListingDate` di kartu |

- `listingDate` dipakai untuk mengisi `Job.posted_at` (`parsers.parse_listing_dates`),
  karena `jobListingDate` di DOM hanya teks relatif (tidak bisa diurutkan/filter).
- Halaman detail juga memuat `listedAt.dateTimeUtc` dengan nilai yang sama, tetapi
  **tidak dipakai** — kartu sudah cukup dan lebih hemat.
- Skrip fixture mengekstrak blok ini menjadi `tests/fixtures/listing_dates_01.html`
  (hanya 3 kunci per lowongan, tanpa token/sesi) — lihat §6.

## 3. Selector — halaman detail

| Field | Selector | Contoh isi |
|---|---|---|
| Halaman | `[data-automation="jobDetailsPage"]` | penanda sudah di halaman detail |
| Judul | `[data-automation="job-detail-title"]` | `Junior Programmer` |
| Perusahaan | `[data-automation="advertiser-name"]` | `PT Universal Tatalaksana` |
| Lokasi | `[data-automation="job-detail-location"]` | `Pondokgede, Jawa Barat` |
| Klasifikasi | `[data-automation="job-detail-classifications"]` | `Developer/Programmer (…)` |
| Tipe kerja | `[data-automation="job-detail-work-type"]` | `Full time` |
| Gaji | `[data-automation="job-detail-salary"]` | `Rp 4.000.000 – Rp 6.000.000 per month` |
| **Deskripsi penuh** | `[data-automation="jobAdDetails"]` | HTML berisi `<p>`, `<ul>`, `<li>` |

- Tombol lamar: `[data-automation="job-detail-apply"]` (tidak dipakai — lamaran manual).
- Tanggal posting di detail tampil sebagai teks `Diposting 12 jam yang lalu`
  (tanpa `data-automation`) → gunakan `jobListingDate` dari kartu.

## 4. Pagination
- Berpindah halaman via parameter URL `?page=N` (1-based). Kontrol halaman juga ada
  di DOM: `[data-automation="page-0"]`, `page-1`, `page-2`, `page-3`.
- Rekomendasi: bangun URL per halaman, jangan klik tombol.

## 5. Anti-bot (penting)
- Situs dilindungi **Cloudflare Turnstile**. Browser **headless langsung** diarahkan
  ke halaman `"Tunggu sebentar..."`.
- Perilaku yang benar (spec §12): jalankan **headed** (`headless: false`) bila perlu,
  jeda acak, volume kecil. **Jangan** mencoba melewati/memecahkan proteksi.
- Bila challenge tetap muncul saat automasi: hentikan run, catat di log
  (`CaptchaDetectedError`), jangan retry agresif.

## 6. Fixture
| File | Isi | Catatan |
|---|---|---|
| `tests/fixtures/search_page_01.html` | halaman hasil (30 kartu) | versi bersih (script/token dibuang) |
| `tests/fixtures/detail_01.html` | halaman detail satu lowongan | versi bersih |
| `tests/fixtures/listing_dates_01.html` | cuplikan server-state (`id`+`listingDate`) | versi bersih, dibuat `capture_fase0.py` |
| `tests/fixtures/_raw/…` | versi mentah | **gitignored** (memuat token/key) |

- Fixture **wajib** dipakai untuk test parser offline (`tests/test_parsers.py`, M6).
- Versi mentah disimpan di `_raw/` hanya untuk rujukan lokal; jangan di-commit.
- `listing_dates_01.html` bisa dibuat ulang **tanpa jaringan** dari fixture mentah:
  `.\.venv\Scripts\python.exe scripts\capture_fase0.py --from-raw`

## 7. Yang masih perlu dikonfirmasi saat M6
- Format gaji untuk rentang vs angka tunggal; apakah selalu `per month`.
- ~~Konsistensi `jobListingDate` (relatif)~~ → **selesai**: waktu pasti diambil dari
  `listingDate` server-state (§2.1); teks relatif tetap disimpan sebagai fallback.
- Apakah `job-detail-work-type` selalu ada (bisa kosong pada sebagian lowongan).
