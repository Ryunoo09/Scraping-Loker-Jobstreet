"""Test parser LinkedIn berbasis fixture asli (tanpa jaringan)."""

from __future__ import annotations

from pathlib import Path

import pytest

from linkedin_scraper.exceptions import StructureChangedError
from linkedin_scraper.models import JobDetail
from linkedin_scraper.parsers import apply_detail, parse_detail_page, parse_search_page

FIXTURES = Path(__file__).parent / "fixtures" / "linkedin"
CARDS_01 = (FIXTURES / "guest_cards_01.html").read_text(encoding="utf-8")
CARDS_02 = (FIXTURES / "guest_cards_02.html").read_text(encoding="utf-8")
DETAIL = (FIXTURES / "detail_01.html").read_text(encoding="utf-8")


def test_search_page_returns_ten_cards() -> None:
    assert len(parse_search_page(CARDS_01)) == 10


def test_first_card_fields() -> None:
    job = parse_search_page(CARDS_01)[0]
    assert job.job_id == "4446754033"
    assert job.title == "Laravel Programmer"
    assert job.company == "PT. Reinovasi Zona Kreasi Indonesia"
    assert job.location == "Depok"
    assert job.url.startswith("https://id.linkedin.com/jobs/view/")
    assert job.posted_at == "2026-07-30"
    assert job.posted_date_text == "2 bulan yang lalu"


def test_pagination_returns_different_cards() -> None:
    first_page = parse_search_page(CARDS_01)
    second_page = parse_search_page(CARDS_02)
    assert len(second_page) == 10
    assert first_page[0].job_id != second_page[0].job_id


def test_empty_page_returns_empty_list() -> None:
    assert parse_search_page("<html><body></body></html>") == []


def test_card_without_title_raises() -> None:
    html = '<div class="base-card" data-entity-urn="urn:li:jobPosting:1"></div>'
    with pytest.raises(StructureChangedError, match="judul"):
        parse_search_page(html)


def test_card_without_link_raises() -> None:
    html = (
        '<div class="base-card" data-entity-urn="urn:li:jobPosting:1">'
        '<h3 class="base-search-card__title">Dev</h3></div>'
    )
    with pytest.raises(StructureChangedError, match="link detail"):
        parse_search_page(html)


def test_job_id_falls_back_to_href() -> None:
    html = (
        '<div class="base-card">'
        '<h3 class="base-search-card__title">Dev</h3>'
        '<a class="base-card__full-link" href="https://x/jobs/view/foo-bar-999?position=1"></a>'
        "</div>"
    )
    job = parse_search_page(html)[0]
    assert job.job_id == "999"


def test_card_without_job_id_raises() -> None:
    html = (
        '<div class="base-card">'
        '<h3 class="base-search-card__title">Dev</h3>'
        '<a class="base-card__full-link" href="https://x/jobs/view/no-number"></a>'
        "</div>"
    )
    with pytest.raises(StructureChangedError, match="Job ID"):
        parse_search_page(html)


def test_detail_page_fields() -> None:
    detail = parse_detail_page(DETAIL)
    assert detail.title == "Laravel Programmer"
    assert detail.company == "PT. Reinovasi Zona Kreasi Indonesia"
    assert detail.location == "Depok"
    assert detail.posted_date_text == "2 bulan yang lalu"
    assert detail.description is not None
    assert "Minimum education" in detail.description
    assert detail.requirements is not None
    assert "Minimum education" in detail.requirements


def test_detail_missing_returns_none() -> None:
    detail = parse_detail_page("<html></html>")
    assert detail.title is None
    assert detail.description is None
    assert detail.requirements is None


def test_apply_detail_merges_description() -> None:
    job = parse_search_page(CARDS_01)[0]
    merged = apply_detail(job, JobDetail(description="desc", requirements="req"))
    assert merged.description == "desc"
    assert merged.requirements == "req"
    assert merged.title == job.title


def test_apply_detail_marks_complete_when_description_present() -> None:
    job = parse_search_page(CARDS_01)[0]
    assert job.detail_complete is False
    merged = apply_detail(job, JobDetail(description="desc"))
    assert merged.detail_complete is True


def test_apply_detail_empty_keeps_card_data() -> None:
    job = parse_search_page(CARDS_01)[0]
    merged = apply_detail(job, JobDetail())
    assert merged.description is None
    assert merged.requirements is None
    assert merged.detail_complete is False
    assert merged.job_id == job.job_id
    assert merged.title == job.title
    assert merged.company == job.company


def test_apply_detail_partial_does_not_wipe_existing_requirements() -> None:
    job = parse_search_page(CARDS_01)[0].model_copy(update={"requirements": "lama"})
    merged = apply_detail(job, JobDetail(description="desc"))
    assert merged.requirements == "lama"
