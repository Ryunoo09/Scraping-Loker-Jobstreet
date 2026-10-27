"""Writer output LinkedIn: Excel lokal, Google Sheets, dan null (dry-run)."""

from __future__ import annotations

from pathlib import Path

from ..config import OutputConfig
from ..exceptions import WriterError
from .base import HEADERS, JobWriter, NullWriter, job_to_row
from .excel import ExcelWriter
from .sheets import GoogleSheetsWriter

__all__ = [
    "HEADERS",
    "ExcelWriter",
    "GoogleSheetsWriter",
    "JobWriter",
    "NullWriter",
    "build_writer",
    "job_to_row",
]


def build_writer(cfg: OutputConfig, *, dry_run: bool = False) -> JobWriter:
    """Pilih writer sesuai ``cfg.type`` dan siapkan headernya."""
    if dry_run:
        return NullWriter()

    if cfg.type == "google_sheets":
        if cfg.google_sheets is None:
            raise WriterError("output.google_sheets wajib diisi saat type = 'google_sheets'")
        writer: JobWriter = GoogleSheetsWriter(cfg.google_sheets)
    else:
        if cfg.excel is None:
            raise WriterError("output.excel wajib diisi saat type = 'excel'")
        writer = ExcelWriter(Path(cfg.excel.file_path))

    writer.ensure_header()
    return writer
