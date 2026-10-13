"""Hierarki exception proyek.

Semua error yang disengaja diturunkan dari :class:`JobScraperError` agar pemanggil
bisa menangkap satu tipe dasar tanpa menelan bug tak terduga.
"""

from __future__ import annotations


class JobScraperError(Exception):
    """Base untuk semua error yang disengaja di proyek ini."""


class ConfigError(JobScraperError):
    """config.yaml tidak ada, tidak bisa dibaca, atau isinya tidak valid."""


class ScraperError(JobScraperError):
    """Base untuk kegagalan saat scraping."""


class StructureChangedError(ScraperError):
    """Selector/struktur yang diharapkan tidak ditemukan (situs kemungkinan berubah).

    Run harus berhenti bersih dan tidak menulis data setengah jadi.
    """


class CaptchaDetectedError(ScraperError):
    """Halaman CAPTCHA/verifikasi terdeteksi; berhenti tanpa retry agresif."""


class StorageError(JobScraperError):
    """Kegagalan pada penyimpanan lokal (SQLite)."""


class WriterError(JobScraperError):
    """Kegagalan saat menulis ke spreadsheet/Excel."""
