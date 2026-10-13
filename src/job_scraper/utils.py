"""Utilitas umum: logging, jeda acak, dan normalisasi teks."""

from __future__ import annotations

import logging
import random
import time
import unicodedata
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_LOGGING_CONFIGURED = False


def setup_logging(log_path: Path, level: int = logging.INFO) -> None:
    """Siapkan logging ke terminal dan file (dengan rotasi).

    Idempoten: pemanggilan kedua tidak menambah handler baru.

    Args:
        log_path: Lokasi file log; folder induk dibuat bila belum ada.
        level: Level logging minimum.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _LOGGING_CONFIGURED = True


def random_delay(min_sec: float, max_sec: float) -> float:
    """Tidur selama durasi acak di antara ``min_sec`` dan ``max_sec``.

    Args:
        min_sec: Batas bawah jeda (detik).
        max_sec: Batas atas jeda (detik).

    Returns:
        Durasi (detik) yang benar-benar dipakai untuk tidur.
    """
    # Jeda kesopanan scraping: acak non-kripto memang disengaja (nosec B311).
    delay = random.uniform(min_sec, max_sec)  # nosec B311
    time.sleep(delay)
    return delay


def normalize_text(text: str | None) -> str:
    """Rapikan teks untuk pencocokan.

    Melakukan normalisasi Unicode NFKC, menyatukan seluruh whitespace menjadi
    satu spasi, lalu mengubah ke huruf kecil.

    Args:
        text: Teks masukan; ``None`` diperlakukan sebagai string kosong.

    Returns:
        Teks yang sudah dinormalisasi.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return " ".join(normalized.split()).lower()
