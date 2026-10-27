"""Hierarki error untuk scraper LinkedIn.

Selalu pakai exception spesifik (bukan ``Exception`` generik) agar pemanggil bisa
membedakan config salah, jaringan gagal, struktur situs berubah, dan writer gagal.
"""

from __future__ import annotations


class LinkedInError(Exception):
    """Kesalahan dasar seluruh paket."""


class ConfigError(LinkedInError):
    """File config tidak ada, YAML rusak, atau isinya tidak valid."""


class ScraperError(LinkedInError):
    """Gagal mengambil halaman: jaringan, timeout, atau respons tak terduga."""


class RateLimitError(ScraperError):
    """LinkedIn membalas 429 setelah semua percobaan ulang habis."""


class StructureChangedError(LinkedInError):
    """Kartu/field wajib tidak ditemukan — selector kemungkinan sudah berubah."""


class StorageError(LinkedInError):
    """Operasi SQLite gagal."""


class WriterError(LinkedInError):
    """Gagal menulis hasil ke spreadsheet."""
