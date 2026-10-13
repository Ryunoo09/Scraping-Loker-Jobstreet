# Panduan Investigasi Fase 0 — JobStreet

> Tugas ini **milikmu** (sesuai keputusan Q1). Saya tidak akan menebak selector apa pun.
> Hasil dari panduan ini adalah satu-satunya sumber untuk menulis `parsers.py` (M6) dan
> `scraper.py` (M5). Bisa kamu kerjakan **paralel** dengan M1–M4 yang saya bangun.

Tujuan: mengetahui **dari mana setiap field data diambil** di `id.jobstreet.com`.

Semua selector/URL di dokumen lain hanyalah **placeholder**. Hasil di sini yang menjadi acuan.

---

## 1. Siapkan

1. Buka `https://id.jobstreet.com` di Chrome/Edge **di laptopmu** (bukan headless).
2. Buka DevTools: `F12` (atau klik kanan → Inspect).
3. Lakukan pencarian manual, misalnya kata kunci `IT Support`, lokasi `Semarang`.

---

## 2. Yang perlu dicatat (A–F)

### A. Pola URL hasil pencarian
- Salin URL setelah menekan Search.
- Tentukan bagian mana yang berisi: kata kunci, lokasi, dan **halaman** (page).
- Contoh yang diharapkan (bentuknya saja, belum tentu benar):
  `https://id.jobstreet.com/id/it-support-jobs/in-Semarang?page=2`
- Catat: **bagaimana cara berpindah halaman** (parameter `page`? tombol Next?).

### B. Pola URL halaman detail + lokasi Job ID
- Klik satu lowongan, salin URL-nya.
- Tentukan di mana **Job ID** berada (biasanya deretan angka di URL).
- Contoh bentuk: `https://id.jobstreet.com/job/91234567` → Job ID = `91234567`.
- Jika Job ID tidak ada di URL, cari di HTML (`data-job-id`, atribut, atau JSON tertanam).

### C. Ada endpoint JSON?
Ini yang paling menghemat waktu kalau ada.
1. Di DevTools → tab **Network** → filter **Fetch/XHR**.
2. Muat ulang halaman hasil pencarian.
3. Cari request yang **response-nya berisi daftar lowongan** (JSON).
4. Kalau ada: catat URL request, method, parameter penting, dan **salin 1 contoh response JSON**.
5. Kalau tidak ada / terlalu rumit: tulis "tidak ada, pakai HTML".

### D. Selector kartu lowongan (daftar hasil)
Di tab **Elements**, temukan elemen pembungkus satu kartu lowongan, lalu catat selector-nya.
**Utamakan atribut `data-automation`** (lebih stabil) daripada nama class acak.

Untuk satu kartu, catat selector tiap field:

| Field | Selector | Contoh nilai |
|---|---|---|
| Kartu (pembungkus) | | |
| Judul | | |
| Nama perusahaan | | |
| Lokasi | | |
| Link (href) | | |
| Gaji (bila ada) | | |
| Tipe kerja (bila ada) | | |
| Tanggal posting (bila ada) | | |

### E. Selector halaman detail
Di halaman satu lowongan, catat:

| Field | Selector | Catatan |
|---|---|---|
| Judul | | |
| Perusahaan | | |
| Lokasi | | |
| Deskripsi penuh | | |
| Tipe kerja | | |
| Gaji | | |
| Tanggal posting | | |

### F. Tanda blokir / CAPTCHA (bila muncul)
- Apakah muncul halaman verifikasi/CAPTCHA saat membuka banyak halaman cepat?
- Catat ciri halamannya (teks/judul/selector) supaya saya bisa mendeteksi lebih awal.

---

## 3. Simpan fixture (WAJIB)

Simpan **3–5 contoh** ke `tests/fixtures/` agar parser bisa diuji **tanpa internet**:

1. **HTML kartu hasil pencarian**: klik kanan elemen `<html>` → Copy → Copy outerHTML,
   atau di console: `copy(document.documentElement.outerHTML)`, lalu tempel ke
   `tests/fixtures/search_page_01.html`.
2. **HTML detail** satu lowongan → `tests/fixtures/detail_01.html`.
3. **Response JSON** (bila ada di langkah C) → `tests/fixtures/search_response_01.json`.

> Simpan **apa adanya** (raw). Jangan dibersihkan/dirapikan — saya butuh struktur aslinya.

Nama file bebas, tetapi sebutkan di catatan file mana untuk apa.

---

## 4. Format hasil yang saya butuhkan (isi di README atau file ini)

```text
[URL PENCARIAN]
- Contoh: ...
- Parameter keyword: ...
- Parameter lokasi: ...
- Pagination: ... (contoh URL halaman 2: ...)

[JOB ID]
- Lokasi: URL path / atribut / JSON
- Contoh: https://id.jobstreet.com/job/91234567  ->  91234567

[ENDPOINT JSON]
- Ada? ya/tidak
- URL: ...
- Contoh file fixture: tests/fixtures/search_response_01.json

[SELECTOR]
- Kartu: ...
- Judul: ...
- Perusahaan: ...
- Lokasi: ...
- Link: ... (ambil dari atribut apa?)
- Gaji: ...
- Tipe kerja: ...
- Tanggal posting: ...
- Deskripsi (detail): ...

[PAGINATION]
- Cara pindah halaman: ...
- Maksimal halaman yang terlihat: ...

[ANTI-BOT]
- CAPTCHA muncul? ya/tidak; ciri: ...

[FIXTURES]
- tests/fixtures/search_page_01.html  -> daftar hasil pencarian
- tests/fixtures/detail_01.html       -> halaman detail
- tests/fixtures/search_response_01.json -> (bila ada)

[CALON HASH FALLBACK] (bila Job ID tidak ditemukan)
- Contoh teks untuk company+title+location: ...
```

---

## 5. Checklist selesai

- [ ] Pola URL pencarian & pagination dicatat
- [ ] Lokasi Job ID diketahui (+ contoh)
- [ ] Sudah dipastikan ada/tidaknya endpoint JSON
- [ ] Selector semua field kartu dicatat (utamakan `data-automation`)
- [ ] Selector field halaman detail dicatat (khususnya deskripsi penuh)
- [ ] 3–5 fixture tersimpan di `tests/fixtures/` (HTML dan/atau JSON)
- [ ] Ciri CAPTCHA (bila ada) dicatat
- [ ] Catatan diisi di README

Kalau ada yang tidak yakin, kirim saja apa adanya + screenshot — saya bantu menyimpulkan
polanya, tetapi **keputusan akhir selector tetap dari hasil observasimu**.
