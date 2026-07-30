"""End-to-end checks for the core merge library, using the sample PDF as both
the header file and the spells file."""

import pathlib

import pymupdf
import pytest

from spellhdr import Config, build_output, header_page_info

SAMPLE = pathlib.Path(__file__).resolve().parent.parent / "Halfling_druid.pdf"


@pytest.fixture(scope="module")
def sample_bytes():
    if not SAMPLE.exists():
        pytest.skip(f"sample PDF not found: {SAMPLE}")
    return SAMPLE.read_bytes()


def test_header_page_info(sample_bytes):
    info = header_page_info(sample_bytes)
    assert info["page_count"] == 6
    assert info["pages"][0]["width"] > 0
    assert info["pages"][0]["height"] > 0


def test_build_output_page_count_matches_spells(sample_bytes):
    cfg = Config(header_page_index=0)
    out = build_output(sample_bytes, sample_bytes, cfg)
    doc = pymupdf.open(stream=out, filetype="pdf")
    try:
        assert len(doc) == header_page_info(sample_bytes)["page_count"]
        # Output pages keep the spells page size.
        assert round(doc[0].rect.width) == 595
        assert round(doc[0].rect.height) == 792
    finally:
        doc.close()


def test_slots_only_on_first_page(sample_bytes):
    """First page carries more image area (slots + modifiers) than later pages
    (modifiers only), so its rasterized image bytes are larger."""
    cfg = Config(
        header_page_index=0,
        slots_y0=550, slots_y1=660,
        modifiers_y0=130, modifiers_y1=185,
        include_slots_on_first=True,
    )
    out = build_output(sample_bytes, sample_bytes, cfg)
    doc = pymupdf.open(stream=out, filetype="pdf")
    try:
        first_images = doc.get_page_images(0)
        second_images = doc.get_page_images(1)
        # Page 1: slots band + modifiers band. Page 2: modifiers band only.
        assert len(first_images) == len(second_images) + 1
    finally:
        doc.close()


def test_slots_toggle_off(sample_bytes):
    cfg = Config(header_page_index=0, include_slots_on_first=False)
    out = build_output(sample_bytes, sample_bytes, cfg)
    doc = pymupdf.open(stream=out, filetype="pdf")
    try:
        # With slots off, first page has the same band count as later pages.
        assert len(doc.get_page_images(0)) == len(doc.get_page_images(1))
    finally:
        doc.close()
