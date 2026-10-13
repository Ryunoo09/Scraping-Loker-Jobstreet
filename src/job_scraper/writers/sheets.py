"""Writer Google Sheets berbasis ``gspread`` (spec §7, §11).

Penulisan dilakukan **sekali per run** lewat ``append_rows`` (batch), bukan satu
baris per permintaan, supaya aman dari batas kuota API (spec §11).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import gspread
from gspread.exceptions import GSpreadException
from gspread.utils import ValueInputOption

from ..config import GoogleSheetsConfig
from ..exceptions import WriterError
from ..models import Job
from .base import HEADERS, job_to_row

logger = logging.getLogger(__name__)


class GoogleSheetsWriter:
    """Append-only ke satu worksheet Google Sheets.

    Args:
        config: Bagian ``output.google_sheets`` dari config tervalidasi.

    Raises:
        WriterError: Bila koneksi/otentikasi atau worksheet tidak bisa diakses.
    """

    def __init__(self, config: GoogleSheetsConfig) -> None:
        self._config = config
        self._header_ready = False
        try:
            client = gspread.service_account(filename=config.credentials_file)
            spreadsheet = client.open_by_key(config.spreadsheet_id)
            self._worksheet = spreadsheet.worksheet(config.worksheet_name)
        except (GSpreadException, OSError, ValueError) as exc:
            raise WriterError(
                f"Gagal terhubung ke Google Sheets (spreadsheet_id={config.spreadsheet_id}): {exc}"
            ) from exc

    def ensure_header(self) -> None:
        """Tulis header bila baris pertama masih kosong (idempoten)."""
        if self._header_ready:
            return
        try:
            existing = self._worksheet.row_values(1)
            if not existing:
                self._worksheet.insert_row(list(HEADERS), 1)
                logger.info("Menulis header ke worksheet '%s'", self._config.worksheet_name)
            elif existing[: len(HEADERS)] != list(HEADERS):
                logger.warning(
                    "Header worksheet '%s' tidak sesuai standar; dibiarkan apa adanya "
                    "(tidak menimpa data).",
                    self._config.worksheet_name,
                )
        except (GSpreadException, OSError) as exc:
            raise WriterError(f"Gagal menyiapkan header Google Sheets: {exc}") from exc
        self._header_ready = True

    def append(self, jobs: Sequence[Job]) -> None:
        """Tambahkan ``jobs`` sebagai baris baru lewat satu panggilan batch."""
        if not jobs:
            return
        self.ensure_header()
        rows = [job_to_row(job) for job in jobs]
        try:
            self._worksheet.append_rows(rows, value_input_option=ValueInputOption.user_entered)
        except (GSpreadException, OSError) as exc:
            raise WriterError(f"Gagal menulis ke Google Sheets: {exc}") from exc
        logger.info("Menulis %d baris ke worksheet '%s'", len(rows), self._config.worksheet_name)
