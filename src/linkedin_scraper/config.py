"""Memuat dan memvalidasi ``config_linkedin.yaml`` dengan Pydantic v2."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .exceptions import ConfigError


class _StrictModel(BaseModel):
    """Base config: menolak key tak dikenal supaya salah ketik cepat ketahuan."""

    model_config = ConfigDict(extra="forbid")


class SearchConfig(_StrictModel):
    """Kriteria pencarian di LinkedIn (guest)."""

    keywords: list[str]
    location: str = "Indonesia"
    posted_within_days: int | None = Field(default=None, ge=1)
    work_types: list[str] = Field(default_factory=list)  # kode f_JT, mis. "F"
    experience_levels: list[int] = Field(default_factory=list)  # kode f_E
    max_pages_per_query: int = Field(default=2, ge=1)
    fetch_detail: bool = True

    @field_validator("keywords")
    @classmethod
    def _non_empty_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("harus berisi minimal satu nilai")
        return cleaned

    @field_validator("location")
    @classmethod
    def _non_empty_location(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("harus berisi minimal satu nilai")
        return value.strip()


class FiltersConfig(_StrictModel):
    """Aturan penolakan sebelum scoring."""

    exclude_title_keywords: list[str] = Field(default_factory=list)
    exclude_description_keywords: list[str] = Field(default_factory=list)
    exclude_companies: list[str] = Field(default_factory=list)


class ScoringConfig(_StrictModel):
    """Bobot kecocokan dan ambang skor minimum."""

    min_score: int = Field(default=0, ge=0, le=100)
    title_keywords: dict[str, int] = Field(default_factory=dict)
    description_keywords: dict[str, int] = Field(default_factory=dict)
    location_bonus: dict[str, int] = Field(default_factory=dict)


class GoogleSheetsConfig(_StrictModel):
    """Pengaturan output Google Sheets (spreadsheet terpisah)."""

    spreadsheet_id: str
    worksheet_name: str = "LinkedIn"
    credentials_file: str = "credentials/service_account.json"


class ExcelConfig(_StrictModel):
    """Pengaturan output Excel lokal."""

    file_path: str = "data/linkedin_jobs.xlsx"


class OutputConfig(_StrictModel):
    """Tujuan penulisan hasil."""

    type: Literal["google_sheets", "excel"]
    google_sheets: GoogleSheetsConfig | None = None
    excel: ExcelConfig | None = None

    @model_validator(mode="after")
    def _check_output(self) -> Self:
        if self.type == "google_sheets":
            if self.google_sheets is None:
                raise ValueError("output.google_sheets wajib diisi saat type = 'google_sheets'")
            spreadsheet_id = self.google_sheets.spreadsheet_id.strip()
            if not spreadsheet_id or spreadsheet_id.startswith("ISI_"):
                raise ValueError(
                    "output.google_sheets.spreadsheet_id masih placeholder atau kosong"
                )
        elif self.excel is None:
            raise ValueError("output.excel wajib diisi saat type = 'excel'")
        return self


class ScraperConfig(_StrictModel):
    """Perilaku HTTP scraper: kesopanan dan stabilitas."""

    delay_min_sec: float = Field(default=6.0, ge=0)
    delay_max_sec: float = Field(default=15.0, ge=0)
    page_timeout_sec: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    max_jobs_per_run: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def _check_delays(self) -> Self:
        if self.delay_min_sec > self.delay_max_sec:
            raise ValueError("delay_min_sec tidak boleh lebih besar dari delay_max_sec")
        return self


class AppConfig(_StrictModel):
    """Isi lengkap ``config_linkedin.yaml``."""

    search: SearchConfig
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    output: OutputConfig
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)


def _format_validation_error(exc: ValidationError) -> str:
    """Ubah ``ValidationError`` menjadi daftar pesan yang mudah dibaca."""
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "nilai tidak valid"))
        lines.append(f"  - {location}: {message}")
    return "\n".join(lines)


def load_config(path: Path) -> AppConfig:
    """Muat dan validasi config LinkedIn.

    Raises:
        ConfigError: File tidak ada, YAML rusak, atau isi tidak valid.
    """
    if not path.is_file():
        raise ConfigError(f"File config tidak ditemukan: {path}")

    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML tidak valid di {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Isi {path} harus berupa mapping YAML pada level teratas")

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise ConfigError(f"Config tidak valid di {path}:\n{detail}") from exc
