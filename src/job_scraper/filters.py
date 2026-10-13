"""Filter dan scoring lowongan — fungsi murni tanpa I/O (spec §9).

Semua teks dinormalisasi lebih dulu (lihat :func:`job_scraper.utils.normalize_text`).

Strategi pencocokan:

* **Judul (penolakan)** memakai pencocokan **kata utuh** untuk keyword satu kata,
  supaya ``lead`` tidak ikut menolak ``leader`` atau ``misleading`` (spec §9).
* **Deskripsi, perusahaan, tipe kerja, dan scoring** memakai **substring**, karena
  biasanya berupa frasa dan/atau demi daya tangkap (recall) — mis. exclude
  perusahaan memang "cocok sebagian nama" (spec §6).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .config import AppConfig, FiltersConfig
from .models import EvalResult, Job
from .utils import normalize_text

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _keyword_matches(haystack: str, keyword: str, *, whole_word: bool) -> bool:
    """Cek satu keyword pada teks yang sudah dinormalisasi.

    Args:
        haystack: Teks sumber (sudah lowercase).
        keyword: Keyword yang dicari (sudah lowercase).
        whole_word: Bila ``True`` dan keyword satu kata, harus cocok sebagai
            kata utuh.
    """
    if whole_word and _WORD_RE.fullmatch(keyword):
        return re.search(rf"\b{re.escape(keyword)}\b", haystack) is not None
    return keyword in haystack


def _first_match(
    text: str | None, keywords: Sequence[str], *, whole_word: bool = False
) -> str | None:
    """Kembalikan keyword pertama yang cocok, atau ``None``."""
    haystack = normalize_text(text)
    if not haystack:
        return None
    for keyword in keywords:
        needle = normalize_text(keyword)
        if needle and _keyword_matches(haystack, needle, whole_word=whole_word):
            return keyword
    return None


def passes_prefilter(job: Job, filters: FiltersConfig) -> bool:
    """Saring murah berbasis data kartu saja: judul dan nama perusahaan."""
    if _first_match(job.title, filters.exclude_title_keywords, whole_word=True):
        return False
    return _first_match(job.company, filters.exclude_companies) is None


def _sum_weights(haystack: str, weights: Mapping[str, int]) -> int:
    """Jumlahkan bobot keyword yang muncul di ``haystack``."""
    if not haystack:
        return 0
    return sum(
        weight
        for keyword, weight in weights.items()
        if _keyword_matches(haystack, normalize_text(keyword), whole_word=False)
    )


def _score(job: Job, cfg: AppConfig) -> EvalResult:
    """Hitung skor 0-100 dan bandingkan dengan ambang minimum."""
    scoring = cfg.scoring
    score = (
        _sum_weights(normalize_text(job.title), scoring.title_keywords)
        + _sum_weights(normalize_text(job.description), scoring.description_keywords)
        + _sum_weights(normalize_text(job.location), scoring.location_bonus)
    )
    score = min(score, 100)

    if score < scoring.min_score:
        return EvalResult(passed=False, score=score, reason="low_score")
    return EvalResult(passed=True, score=score, reason="")


def evaluate(job: Job, cfg: AppConfig) -> EvalResult:
    """Terapkan filter wajib lalu hitung skor kecocokan.

    Urutan evaluasi (spec §9):
    1. deskripsi mengandung frasa terlarang → tolak;
    2. tipe kerja tidak diizinkan (bila diketahui) → tolak;
    3. gaji di bawah minimum / tidak diketahui (bila diatur) → tolak;
    4. scoring, lalu bandingkan dengan ``scoring.min_score``.
    """
    filters = cfg.filters

    if _first_match(job.description, filters.exclude_description_keywords):
        return EvalResult(passed=False, reason="desc_excluded")

    if filters.work_types and job.work_type and not _first_match(job.work_type, filters.work_types):
        return EvalResult(passed=False, reason="work_type")

    if filters.min_salary_idr is not None:
        if job.salary_min_idr is None:
            if not filters.keep_if_salary_unknown:
                return EvalResult(passed=False, reason="salary_unknown")
        elif job.salary_min_idr < filters.min_salary_idr:
            return EvalResult(passed=False, reason="salary_low")

    return _score(job, cfg)
