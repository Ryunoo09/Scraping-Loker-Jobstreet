# Hasil Investigasi Fase 0 — LinkedIn (guest, terverifikasi)

> Sumber: fixture HTML nyata dari `tests/fixtures/linkedin/` (diambil via
> `scripts/capture_linkedin.py`).
> **Semua selector & pola URL di bawah berasal dari respons nyata, bukan tebakan.**
> Ini menjadi acuan tunggal `linkedin_scraper/scraper.py` (L2) dan
> `linkedin_scraper/parsers.py` (L3).

Tanggal: 2026-10-27 · Situs: `www.linkedin.com` (endpoint guest, tanpa login).

---

## 1. Ringkasan pendekatan

- Sumber data = **endpoint guest**, HTML polos, **tanpa login**.
- Halaman `/jobs/search` penuh **memberi HTTP 429** (proteksi bot), jadi tidak dipakai.
- Endpoint guest **tidak** butuh JavaScript → cukup HTTP GET + User-Agent browser.
- Rate limit agresif: satu permintaan bisa 429; retry dengan jeda 15 dtk berhasil.
- Tidak ada risiko ban akun karena tanpa kredensial.

---

## 2. Pola URL terverifikasi

| Keperluan | Pola | Bukti |
|---|---|---|
| Kartu lowongan | `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={kw}&location={loc}&start={n}` | `guest_cards_01/02.html` |
| Detail lowongan | `https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jobId}` | `detail_01.html` |
| Halaman pencarian penuh | `/jobs/search?...` | **diblokir 429** — jangan dipakai |

- `start` 0-based, **10 kartu per halaman**; `start=10` menghasilkan 10 kartu berbeda
  (paginasi terbukti).
- `location` menerima teks bebas (`Indonesia`) dan menghasilkan lokasi lintas kota.
- Filter rentang waktu **terbukti**: `f_TPR=r604800` (7 hari) mengembalikan 10 kartu
  dengan tanggal `2026-10-22` … `2026-10-27` (hari ini 2026-10-27).
- `f_JT` (tipe kerja) dan `f_E` (level pengalaman) **belum diuji** — verifikasi saat L2
  jika fitur itu dipakai; jangan dianggap benar sebelum dibuktikan.

---

## 3. Selector — kartu (`guest_cards_01.html`, `guest_cards_02.html`)

| Field | Selector | Contoh / catatan |
|---|---|---|
| Kartu | `div.base-card` | tepat 10 elemen per halaman |
| Job ID | `div.base-card@data-entity-urn` | `urn:li:jobPosting:4446754033` → ambil digit akhir |
| Link detail | `a.base-card__full-link@href` | absolut ke `/jobs/view/...` (sudah berisi ID) |
| Judul | `.base-search-card__title` | `Laravel Programmer` |
| Perusahaan | `.base-search-card__subtitle` | `PT. Reinovasi Zona Kreasi Indonesia` |
| Lokasi | `.job-search-card__location` | `Depok` (kota saja) |
| Tanggal posting | `time@datetime` (atau `.job-search-card__listdate`) | `2026-07-30` — **tanggal saja**, bukan jam |
| Teks relatif | `time` (text) | `2 bulan yang lalu` |
| Benefit badge | `.job-posting-benefits__text` | `Actively Hiring` (tidak selalu ada) |

- Tidak ada `data-automation` seperti JobStreet; selector berbasis class yang stabil
  pada sampel ini tetapi **wajib diuji ulang** tiap kali situs berubah.

---

## 4. Selector — detail (`detail_01.html`)

| Field | Selector | Contoh |
|---|---|---|
| Judul | `.top-card-layout__title` | `Laravel Programmer` |
| Perusahaan | `.topcard__org-name-link` | `PT. Reinovasi Zona Kreasi Indonesia` |
| Lokasi | `.topcard__flavor--bullet` (dalam `.topcard__flavor-row`) | `Depok` |
| Waktu relatif | `.posted-time-ago__text` | `2 bulan yang lalu` |
| Jumlah pelamar | `.num-applicants__caption` | `Lebih dari 200 pelamar` |
| Deskripsi | `.show-more-less-html__markup` | HTML `<ul><li>…</li></ul>` lengkap |
| Penanda halaman detail | `.top-card-layout__title` | ada = detail valid |

---

## 5. Yang **tidak** tersedia di guest

| Field | Status |
|---|---|
| Gaji | **Tidak ada** di kartu maupun detail guest |
| Tipe kerja (Full-time/Contract/…) | **Tidak ada** |
| Seniority level / Job function | **Tidak ada** |
| Waktu posting lengkap (jam) | **Tidak ada** — kartu hanya `YYYY-MM-DD` |
| Deskripsi kualifikasi terpisah | Tidak ada seksi terpisah; seluruh isi ada di deskripsi |

Implikasi: `salary_text`, `work_type`, dan `salary_min_idr` akan `None` pada mode guest.
Filter gaji/tipe kerja tidak bisa diandalkan; scoring tetap jalan lewat judul, deskripsi,
dan lokasi.

---

## 6. Batasan & perilaku yang harus ditangani

- **429 Too Many Requests** muncul walau dengan jeda 2 dtk. Wajib retry + backoff
  (15 dtk berhasil pada pengambilan detail).
- **10 kartu/halaman**; paginasi lewat `start` kelipatan 10.
- Detail ≈ 61 KB HTML; deskripsi penuh tersedia.
- Detail tidak memuat `<time datetime>` absolut — pakai tanggal dari kartu.
- Guest kemungkinan berhenti mengembalikan hasil setelah beberapa halaman; deteksi
  0 kartu → berhenti.
- Angka `start` besar bisa memicu 429; batasi halaman (default kecil).

---

## 7. Fixture yang disimpan

| File | Isi |
|---|---|
| `tests/fixtures/linkedin/guest_cards_01.html` | 10 kartu, `start=0` |
| `tests/fixtures/linkedin/guest_cards_02.html` | 10 kartu, `start=10` (paginasi) |
| `tests/fixtures/linkedin/detail_01.html` | detail `4446754033`, deskripsi penuh |
| `tests/fixtures/linkedin/_raw/` | salinan mentah (gitignored) |

---

## 8. Keputusan desain dari hasil ini

1. Scraper guest **cukup HTTP** (`urllib`), tidak perlu Playwright.
2. `posted_at` LinkedIn **date-only** (`YYYY-MM-DD`); jangan paksa format jam.
3. `detail_incomplete` tidak perlu flag terpisah — cukup isi `None` untuk gaji/tipe kerja.
4. Retry/backoff 429 wajib ada di scraper (L2), bukan opsional.
5. Selector disimpan **hanya** di `linkedin_scraper/parsers.py`; jangan tersebar.

---

## 9. Perintah reproduksi

```powershell
.\\.venv\\Scripts\\python.exe scripts\\capture_linkedin.py
```
