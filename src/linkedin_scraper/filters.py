"""Filter dan scoring lowongan LinkedIn — fungsi murni tanpa I/O.

Mode guest tidak menyediakan gaji/tipe kerja, jadi yang dievaluasi hanya judul,
perusahaan, deskripsi, dan lokasi.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .config import AppConfig, FiltersConfig
from .models import EvalResult, JobLinkedIn
from .utils import normalize_text

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _keyword_matches(haystack: str, keyword: str, *, whole_word: bool) -> bool:
    """Cek satu keyword pada teks yang sudah dinormalisasi."""
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


def passes_prefilter(job: JobLinkedIn, filters: FiltersConfig) -> bool:
    """Saring murah berbasis data kartu: judul dan nama perusahaan."""
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


def _score(job: JobLinkedIn, cfg: AppConfig) -> EvalResult:
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


def evaluate(job: JobLinkedIn, cfg: AppConfig) -> EvalResult:
    """Terapkan filter wajib lalu hitung skor kecocokan."""
    if _first_match(job.description, cfg.filters.exclude_description_keywords):
        return EvalResult(passed=False, reason="desc_excluded")
    return _score(job, cfg)
