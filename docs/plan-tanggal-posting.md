# Rencana: Menyimpan Waktu Posting Loker (posted_at)

> **Status: SELESAI (M1–M5).** Keputusan §5 ditutup 2026-10-20.
> Tanggal: 2026-10-20 · Berdasar spec `planning-job-scraper-jobstreet.md` §7 & §8.
>
> Keputusan terkunci: **D1(a)** waktu pasti dari JSON · **D2(a)** kolom H = tanggal+jam WIB,
> tetap 14 kolom · **D3** simpan `posted_at` (bukan `last_seen`) · **D4** ISO 8601 UTC di DB.
>
> **Hasil:** `Job.posted_at` diisi dari `listingDate` server-state; kolom H = WIB
> `YYYY-MM-DD HH:MM` (fallback teks relatif); `seen_jobs.posted_at` + migrasi idempoten
> (`COALESCE` menjaga nilai lama bila run berikutnya tidak punya waktu pasti); fixture baru
> `tests/fixtures/listing_dates_01.html`. Gate hijau: `pytest` 175 test, coverage 97%,
> `ruff`/`mypy`/`bandit` bersih. DB asli (359 baris) termigrasi tanpa data hilang.

Tujuan dokumen ini: menyimpan **kapan lowongan diposting (waktu asli)** — bukan hanya
teks relatif seperti `"12 jam yang lalu"` yang sekarang dipakai.

---

## 1. Kondisi sekarang

| Hal | Kondisi saat ini | Lokasi |
|---|---|---|
| Field tanggal posting | `Job.posted_date: str \| None` — **teks relatif** (`12 jam yang lalu`) | `models.py:38` |
| Sumber nilai | `[data-automation="jobListingDate"]` dari kartu | `parsers.py:33,105` |
| Tanggal ditemukan | `Job.found_date` = `date.today()` (ISO date) | `models.py:41` |
| Halaman detail | **Tidak** mengisi tanggal posting (`apply_detail` mengabaikan) | `parsers.py:291` |
| Spreadsheet | Kolom H "Tanggal Posting" = teks relatif | `writers/base.py:71` |
| SQLite | `seen_jobs` **tidak menyimpan** `posted_date` sama sekali; hanya `first_seen`, `status`, `score` | `storage.py:14-23` |

Kesimpulan: teks relatif tidak bisa dipakai untuk menyortir/menyaring "lowongan terbaru",
dan nilainya hilang begitu run selesai (tidak persist ke DB).

---

## 2. Data waktu pasti yang tersedia (hasil cek fixture)

Di file **mentah** `tests/fixtures/_raw/search_page_01.html` ada blok JSON server-state:

```html
<script data-automation="server-state">
  window.SEEK_REDUX_DATA = { ... "jobs": [ { ... } ] ... }
</script>
```

Setiap objek lowongan memuat (contoh nyata, job id `95227572`):

| Key JSON | Contoh nilai | Catatan |
|---|---|---|
| `id` | `"95227572"` | sama dengan `data-job-id` di kartu → kunci pencocokan |
| `listingDate` | `"2026-10-13T02:58:53.000Z"` | **waktu posting pasti (UTC, ISO 8601)** |
| `listingDateDisplay` | `"12 jam yang lalu"` | teks relatif (yang sekarang dipakai) |
| `locations[].label` | `"Pondokgede, Jawa Barat"` | (tidak dipakai di rencana ini) |

Halaman detail (`_raw/detail_01.html`) juga memuat `listedAt.dateTimeUtc` dengan nilai sama,
tapi **kartu sudah cukup** — tidak perlu buka detail hanya untuk tanggal.

> ⚠️ Fixture bersih sudah membuang `<script>` (`scripts/capture_fase0.py:31`), jadi
> data ini **tidak ada** di `tests/fixtures/*.html`. Perlu fixture baru (lihat M1).

---

## 3. Masalah teknis yang harus ditangani

1. **Sumber nilai baru.** Perlu mengekstrak `listingDate` dari JSON server-state, lalu
   memetakannya ke kartu berdasarkan `id`/`job_id`.
2. **Fixture tidak punya JSON.** Test offline tidak akan menguji jalur ini kecuali kita
   menambahkan fixture (disanitasi: tanpa token/`key_live_`).
3. **Migrasi SQLite.** Database `data/seen_jobs.db` yang sudah ada tidak punya kolom baru →
   butuh `ALTER TABLE ADD COLUMN` yang idempoten.
4. **Header spreadsheet.** File Excel/Sheets yang sudah ada **tidak akan menulis ulang header**
   (prinsip append-only). Menambah kolom baru berarti header lama tidak muncul.
5. **Zona waktu.** `listingDate` UTC; tampilan sebaiknya WIB (UTC+7).

---

## 4. Definisi selesai (DoD)

- Setiap `Job` menyimpan **waktu posting pasti** dalam ISO 8601 UTC (mis. `2026-10-13T02:58:53Z`).
- Nilai itu **masuk ke spreadsheet** (kolom tanggal posting) sebagai WIB yang bisa diurutkan.
- Nilai itu **tersimpan di SQLite** untuk lowongan yang dicatat.
- Bila JSON tidak tersedia/berubah → fallback ke teks relatif, **tidak crash**.
- Semua test offline (`pytest`) hijau, `ruff`/`mypy`/`bandit` bersih, coverage ≥ 90%.

---

## 5. Keputusan (SUDAH DITUTUP 2026-10-20)

**D1 — Sumber waktu.** ✅ **(a)** Ambil `listingDate` pasti dari JSON server-state; fallback ke
teks relatif bila JSON tidak tersedia/berubah.

**D2 — Bentuk kolom spreadsheet.** ✅ **(a)** Kolom H "Tanggal Posting" diisi **tanggal+jam WIB**
(`2026-10-13 09:58`, format `YYYY-MM-DD HH:MM`) supaya bisa diurutkan. **Tetap 14 kolom** →
header file lama tidak bermasalah. Teks relatif **tidak** ditambahkan sebagai kolom baru.

**D3 — Nilai di SQLite.** ✅ Simpan **`posted_at`** (waktu posting). **Tidak** menyimpan
`last_seen` (bukan yang dimaksud).

**D4 — Format tanggal di SQLite.** ✅ **ISO 8601 UTC** (`2026-10-13T02:58:53Z`).

> Konsekuensi dari D2(a): kolom F/H lama tidak berubah jumlahnya; hanya isi kolom H yang
> berubah dari teks relatif → tanggal+jam WIB.

---

## 6. Rancangan perubahan per modul

### 6.1 `models.py`
Tambah field baru pada `Job` (dan mungkin `JobDetail`):
```python
posted_at: str | None = None      # ISO 8601 UTC, mis. "2026-10-13T02:58:53Z"
```
`posted_date` (teks relatif) **dipertahankan** sebagai fallback/rujukan.
Decorator `field_validator` opsional untuk menormalkan ke `...Z`.

### 6.2 `parsers.py` (satu-satunya tempat selector)
- Fungsi baru `parse_listing_dates(html) -> dict[str, str]`:
  - cari `<script data-automation="server-state">`, ambil isi `window.SEEK_REDUX_DATA = {...}`;
  - `json.loads`, telusuri rekursif mencari objek yang punya `id` (digit) + `listingDate`;
  - kembalikan `{job_id: listingDate}`.
  - Bila `json.JSONDecodeError`/pola tidak ketemu → kembalikan `{}` (fallback, tanpa error).
- `_parse_card` tetap ambil teks relatif (`posted_date`).
- `parse_search_page` mengambil mapping di atas, lalu mengisi `posted_at` tiap kartu
  (cocokkan `posted_at` via `job_id`).
- Tambah util `to_wib(iso_utc) -> str | None` (format `YYYY-MM-DD HH:MM`, timezone Asia/Jakarta)
  — boleh di `utils.py` agar bisa diuji terpisah.
- Konsisten dengan aturan repo: **selector baru harus berdasar fixture nyata**, bukan tebakan
  (fixture dari M1).

### 6.3 `storage.py`
- Skema `seen_jobs` + `posted_at TEXT` (dan `posted_date TEXT` bila D3 memilihnya).
- **Migrasi idempoten**: baca `PRAGMA table_info(seen_jobs)`; kalau kolom belum ada,
  `ALTER TABLE seen_jobs ADD COLUMN ...`. Dipanggil di `__init__` setelah `executescript`.
- `mark()` menulis kedua kolom; `first_seen` tidak berubah.
- Tambah getter `get_posted_at(job_id)` (opsional, untuk test & debugging).

### 6.4 `writers/base.py`
- `job_to_row()` mengisi kolom H dari `job.posted_at` yang diformat WIB; fallback ke
  `job.posted_date` (teks relatif) bila kosong.
- Jumlah & urutan kolom mengikuti keputusan D2.

### 6.5 `cli.py`
- Tidak ada perubahan alur wajib; pastikan `posted_at` ikut tersimpan saat `db.mark(...)`.
- Opsional: masuk `pending_*.json` otomatis karena `model_dump(mode="json")` (sudah otomatis).

### 6.6 Dokumen
- `docs/fase0-hasil.md`: catat penemuan `listingDate` di `SEEK_REDUX_DATA` (§2) sebagai
  sumber resmi, menggantikan poin "tanggal relatif" (§7 baris 89).
- `README.md`: perbarui tabel kolom output & bagian "Arsitektur".

---

## 7. Milestone & urutan kerja

| # | Milestone | Isi | DoD |
|---|---|---|---|
| **M1** | Fixture baru | Perluas `scripts/capture_fase0.py` supaya menyimpan **cuplikan server-state tanpa token** ke `tests/fixtures/listing_dates_01.html` (hanya blok `jobs[]` dengan `id`+`listingDate`+`listingDateDisplay`, tanpa `key_live_`/`loginId`). Verifikasi manual tidak ada rahasia. | File fixture ada, bersih, bisa dibaca `json.loads` |
| **M2** | Model + parser | Field `posted_at`; `parse_listing_dates()`; `to_wib()`; integrasi ke `parse_search_page`; fallback aman. | Unit test baru hijau |
| **M3** | Storage + migrasi | Kolom baru + migrasi idempoten + `mark()` menulis kolom. | Test DB lama (skema lama) tetap bisa dibuka & ter-migrasi |
| **M4** | Spreadsheet | Kolom H terisi WIB yang sortable; fallback relatif. | Test writer hijau; cek manual di `jobs.xlsx` |
| **M5** | Dokumen + gate | Update `fase0-hasil.md`, `README.md`; jalankan quality gate. | `pytest`, `ruff`, `mypy`, `bandit` hijau |

Batas kerja: **satu milestone per sesi**, berhenti di akhir milestone untuk kamu verifikasi
(mengikuti gaya `EXECUTION-PLAN.md`).

---

## 8. Test yang terdampak / baru

- Baru: `tests/test_parsers.py::test_parse_listing_dates_*` (happy path, JSON rusak → `{}`,
  key hilang → `{}`), `test_to_wib_*` (UTC→WIB, input kosong/None).
- Baru: `tests/test_storage.py::test_migration_adds_posted_at` (buka DB skema lama → kolom muncul).
- Ubah: `test_models.py` (field baru), `test_writers.py` (kolom H baru), `test_cli.py`
  (nilai tersimpan ke DB).

---

## 9. Risiko & mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Struktur JSON `SEEK_REDUX_DATA` berubah | `posted_at` kosong semua | Fallback ke teks relatif; parsing rekursif (bukan posisi kaku); log `warning` bila 0 mapping |
| Fixture baru memuat rahasia | Kebocoran token | Sanitasi ketat di M1 + review manual sebelum commit |
| Header spreadsheet lama tak ikut berubah | Kolom baru tanpa nama | Jalur D2(a) menghindari kolom baru; kalau D2(b) → instruksi tambah header manual / util sekali pakai |
| Timezone salah | Tanggal geser 1 hari | Selalu konversi dari UTC → WIB di satu util teruji |
| DB lama korup saat migrasi | Data hilang | `ALTER TABLE ADD COLUMN` tidak destruktif; backup otomatis `seen_jobs.db` sebelum migrasi (opsional) |

---

## 10. Di luar lingkup (tidak dikerjakan)

- Menyaring/menyortir *berdasarkan* tanggal posting (hanya menyimpan + menampilkan).
- Ambil tanggal dari halaman detail (kartu sudah cukup).
- Filter baru di `config.yaml` (mis. `max_age_days`) — bisa jadi rencana terpisah kalau mau.