# Cara Pakai — LinkedIn Scraper (mandiri)

Fitur ini **terpisah total** dari scraper JobStreet. Tidak ada file JobStreet yang
berubah. Data, config, database, dan log punya jalur sendiri.

> **Batasan penting:** mode guest (tanpa login) hanya memberi ±10 kartu/halaman,
> tanpa gaji/tipe kerja, dan sering kena rate limit (429). Detail deskripsi bersifat
> best-effort. Lihat [`fase0-linkedin.md`](fase0-linkedin.md).

---

## 1. Setup

```powershell
# 1) salin contoh config
copy config_linkedin.example.yaml config_linkedin.yaml

# 2) edit config_linkedin.yaml sesuai kebutuhan

# 3) validasi config
.\\.venv\\Scripts\\python.exe linkedin_main.py --check-config
```

Tidak perlu setup tambahan selain dependensi yang sudah dipakai JobStreet
(`playwright` tidak dipakai di sini; cukup `urllib` bawaan Python).

---

## 2. Menjalankan

```powershell
# simulasi, tidak menulis apa pun
.\\.venv\\Scripts\\python.exe linkedin_main.py --dry-run --limit 3

# jalankan sungguhan (tulis ke data/linkedin_jobs.xlsx)
.\\.venv\\Scripts\\python.exe linkedin_main.py --limit 20

# nilai ulang lowongan yang dulu ditolak
.\\.venv\\Scripts\\python.exe linkedin_main.py --reset-rejected

# config lain
.\\.venv\\Scripts\\python.exe linkedin_main.py --config config_lain.yaml
```

### Opsi CLI

| Opsi | Arti |
|---|---|
| `--config PATH` | path ke `config_linkedin.yaml` |
| `--check-config` | validasi config lalu keluar |
| `--dry-run` | simulasi tanpa menulis DB/spreadsheet |
| `--limit N` | batasi jumlah lowongan yang diproses |
| `--reset-rejected` | hapus catatan lowongan ditolak |

---

## 3. Output

| Item | Lokasi |
|---|---|
| Spreadsheet | `data/linkedin_jobs.xlsx` (default) |
| Database dedup | `data/linkedin_seen.db` |
| Log | `logs/linkedin_scraper.log` |
| Sheet | 15 kolom (A–O), termasuk "Detail Lengkap?" |

Kolom "Status Lamaran" (J) dan "Catatan" (K) milikmu — tidak pernah ditimpa.
Penulisan bersifat **append-only**.

---

## 4. Batasan mode guest

- 10 kartu per halaman; paginasi lewat `start` kelipatan 10.
- Gaji dan tipe kerja **tidak tersedia** → kolom F/G kosong.
- Tanggal posting hanya tanggal (`YYYY-MM-DD`), bukan jam.
- Sering 429 → scraper otomatis retry dengan backoff (default 3×).
  Jika masih gagal, run berhenti dengan exit code 1.
- Bila endpoint berubah, cukup perbaiki `src/linkedin_scraper/parsers.py`
  dan perbarui fixture di `tests/fixtures/linkedin/`.

---

## 5. Testing

```powershell
# hanya test LinkedIn + coverage
.\\.venv\\Scripts\\pytest.exe tests -k linkedin --cov=linkedin_scraper --cov-report=term-missing --cov-fail-under=90

# lint & type & security
.\\.venv\\Scripts\\ruff.exe check .
.\\.venv\\Scripts\\mypy.exe
.\\.venv\\Scripts\\bandit.exe -r src
```

---

## 6. Etika & ketentuan layanan

Scraping LinkedIn melanggar Ketentuan Layanan mereka. Gunakan hanya untuk
pengumpulan data pribadi skala kecil, tanpa upaya menembus proteksi bot, dan
dengan jeda yang sopan. Tidak ada login/akun yang dipakai, sehingga tidak ada
risiko ban akun — tetapi volume permintaan tetap dibatasi.
