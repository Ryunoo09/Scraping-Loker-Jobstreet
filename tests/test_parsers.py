"""Test parser berbasis fixture Fase 0 (offline, tanpa jaringan).

Fixture berasal dari HTML asli (lihat ``docs/fase0-hasil.md``). Test ini adalah
regression test untuk saat JobStreet mengubah tampilan (spec §15).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from job_scraper.exceptions import StructureChangedError
from job_scraper.models import Job, JobDetail
from job_scraper.parsers import (
    BASE_URL,
    _extract_requirements,
    apply_detail,
    parse_detail_page,
    parse_salary_min_idr,
    parse_search_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def search_html() -> str:
    """HTML halaman hasil pencarian (fixture Fase 0)."""
    return (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail_html() -> str:
    """HTML halaman detail satu lowongan (fixture Fase 0)."""
    return (FIXTURES / "detail_01.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# parse_search_page
# --------------------------------------------------------------------------- #


def test_parse_search_page_returns_cards(search_html: str) -> None:
    jobs = parse_search_page(search_html)

    assert len(jobs) >= 20


def test_first_card_fields(search_html: str) -> None:
    job = parse_search_page(search_html)[0]

    assert job.job_id == "95227572"
    assert job.title == "Junior Programmer"
    assert job.company == "PT Universal Tatalaksana"
    assert job.location == "Pondokgede, Jawa Barat"
    assert job.url.startswith(f"{BASE_URL}/id/job/95227572")
    assert job.salary_min_idr == 4_000_000
    assert job.posted_date == "12 jam yang lalu"
    assert job.description is None
    assert job.work_type is None
    assert job.found_date == date.today().isoformat()


def test_all_cards_have_required_fields_and_unique_ids(search_html: str) -> None:
    jobs = parse_search_page(search_html)

    assert all(job.job_id and job.title and job.url for job in jobs)
    assert len({job.job_id for job in jobs}) == len(jobs)


def test_card_without_salary_has_no_amount(search_html: str) -> None:
    jobs = parse_search_page(search_html)
    without_salary = [job for job in jobs if job.salary_text is None]

    assert without_salary
    assert all(job.salary_min_idr is None for job in without_salary)


def test_every_salary_text_is_parsed(search_html: str) -> None:
    jobs = parse_search_page(search_html)
    with_salary = [job for job in jobs if job.salary_text is not None]

    assert with_salary
    assert all(job.salary_min_idr is not None and job.salary_min_idr > 0 for job in with_salary)


def test_empty_page_returns_empty_list() -> None:
    assert parse_search_page("<html><body></body></html>") == []


def test_base_url_override() -> None:
    html = (
        '<article data-automation="normalJob" data-job-id="1">'
        '<a data-automation="jobTitle" href="/id/job/1">X</a></article>'
    )

    jobs = parse_search_page(html, base_url="https://example.test")

    assert jobs[0].url == "https://example.test/id/job/1"


def test_missing_optional_fields_become_empty_strings() -> None:
    html = (
        '<article data-automation="normalJob" data-job-id="7">'
        '<a data-automation="jobTitle" href="/id/job/7">Tanpa Detail</a>'
        '<span data-automation="jobCompany"></span></article>'
    )

    job = parse_search_page(html)[0]

    assert job.company == ""
    assert job.location == ""
    assert job.salary_text is None


def test_card_without_title_raises() -> None:
    html = '<article data-automation="normalJob" data-job-id="1"></article>'

    with pytest.raises(StructureChangedError, match="judul"):
        parse_search_page(html)


def test_card_without_href_raises() -> None:
    html = (
        '<article data-automation="normalJob" data-job-id="1">'
        '<a data-automation="jobTitle">X</a></article>'
    )

    with pytest.raises(StructureChangedError, match="href"):
        parse_search_page(html)


def test_job_id_falls_back_to_href() -> None:
    html = (
        '<article data-automation="normalJob">'
        '<a data-automation="jobTitle" href="/id/job/12345?type=standard">X</a></article>'
    )

    assert parse_search_page(html)[0].job_id == "12345"


def test_card_without_job_id_raises() -> None:
    html = (
        '<article data-automation="normalJob">'
        '<a data-automation="jobTitle" href="/id/jobs/beranda">X</a></article>'
    )

    with pytest.raises(StructureChangedError, match="Job ID"):
        parse_search_page(html)


# --------------------------------------------------------------------------- #
# parse_detail_page
# --------------------------------------------------------------------------- #


def test_parse_detail_page_fields(detail_html: str) -> None:
    detail = parse_detail_page(detail_html)

    assert detail.title == "Junior Programmer"
    assert detail.company == "PT Universal Tatalaksana"
    assert detail.location == "Pondokgede, Jawa Barat"
    assert detail.work_type == "Full time"
    assert detail.salary_min_idr == 4_000_000
    assert detail.description is not None
    assert "Junior Programmer" in detail.description
    assert len(detail.description) > 500
    assert detail.requirements is not None
    assert "Logika Pemrograman" in detail.requirements or "algoritma" in detail.requirements


@pytest.mark.parametrize(
    ("header", "expected_items"),
    [
        ("Kualifikasi", ["harus bisa"]),
        ("Persyaratan", ["minimal"]),
        ("Keterampilan dan Kualifikasi", ["harus bisa", "Python"]),
    ],
)
def test_extract_requirements_with_various_headers(header: str, expected_items: list[str]) -> None:
    """Test _extract_requirements dengan berbagai variasi header seksi."""
    from bs4 import BeautifulSoup

    html = (
        f"<div><p><strong>Deskripsi</strong></p>"
        f"<p>Kami mencari kandidat terbaik</p>"
        f"<p><strong>{header}</strong></p>"
        f"<ul><li><p>harus bisa Python</p></li><li><p>minimal 2 tahun</p></li></ul>"
        f"<p><strong>Manfaat</strong></p>"
        f"<ul><li><p>Gaji kompetitif</p></li></ul>"
        f"</div>"
    )
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one("div")
    result = _extract_requirements(element)

    assert result is not None
    for item in expected_items:
        assert item in result


def test_description_whitespace_is_normalized(detail_html: str) -> None:
    description = parse_detail_page(detail_html).description

    assert description is not None
    assert "\n" not in description
    assert "  " not in description


def test_detail_page_missing_elements_yields_empty_model() -> None:
    assert parse_detail_page("<html></html>") == JobDetail()


# --------------------------------------------------------------------------- #
# apply_detail
# --------------------------------------------------------------------------- #


def test_apply_detail_fills_description_work_type_and_salary(
    search_html: str, detail_html: str
) -> None:
    job = parse_search_page(search_html)[0]
    detail = parse_detail_page(detail_html)

    merged = apply_detail(job, detail)

    assert merged is not job
    assert merged.job_id == job.job_id
    assert merged.description == detail.description
    assert merged.requirements == detail.requirements
    assert merged.work_type == "Full time"
    assert merged.salary_text == detail.salary_text
    assert merged.salary_min_idr == 4_000_000


def test_apply_detail_keeps_card_data_when_detail_empty(make_job: Callable[..., Job]) -> None:
    job = make_job(salary_text="Rp 9.000.000 per month", salary_min_idr=9_000_000)

    merged = apply_detail(job, JobDetail())

    assert merged.salary_text == "Rp 9.000.000 per month"
    assert merged.salary_min_idr == 9_000_000
    assert merged.description is None
    assert merged.requirements is None
    assert merged.work_type is None


# --------------------------------------------------------------------------- #
# parse_salary_min_idr
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Rp 4.000.000 - Rp 6.000.000 per month", 4_000_000),
        ("Rp 5,000,000 - Rp 6,000,000 per month", 5_000_000),
        ("Rp15.000.000 per month", 15_000_000),
        ("Rp 8 juta per month", 8_000_000),
        ("Rp 4,5 juta", 4_500_000),
        ("Rp 4.5 juta", 4_500_000),
        ("Rp 1.500,5 juta", 1_500_500_000),
        ("Rp 400 ribu", 400_000),
        ("Rp 1,5 miliar per year", 1_500_000_000),
        ("Competitive", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_salary_min_idr(text: str | None, expected: int | None) -> None:
    assert parse_salary_min_idr(text) == expected
