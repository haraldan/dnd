"""Core PyMuPDF logic: clip header bands and overlay them onto a spells PDF.

This module is web-framework-agnostic and importable on its own (see
``tests/test_merge.py`` and the CLI-style ``__main__`` block below).
"""

from __future__ import annotations

import pymupdf  # PyMuPDF

from .config import Config


def _open(pdf_bytes: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=pdf_bytes, filetype="pdf")


def header_page_info(header_bytes: bytes) -> dict:
    """Return page count and per-page sizes (points) for the header PDF."""
    doc = _open(header_bytes)
    try:
        pages = [
            {"width": round(p.rect.width, 2), "height": round(p.rect.height, 2)}
            for p in doc
        ]
        return {"page_count": len(doc), "pages": pages}
    finally:
        doc.close()


def page_count(pdf_bytes: bytes) -> int:
    doc = _open(pdf_bytes)
    try:
        return len(doc)
    finally:
        doc.close()


def render_band(
    doc: pymupdf.Document,
    page_index: int,
    y0: float,
    y1: float,
    dpi: int,
) -> tuple[pymupdf.Pixmap | None, float]:
    """Rasterize a full-width horizontal strip ``[y0, y1]`` from ``page_index``.

    Returns ``(pixmap, band_height)``. If the range is empty, returns ``(None, 0)``.
    """
    page = doc.load_page(page_index)
    width = page.rect.width
    height = page.rect.height
    lo = max(0.0, min(y0, y1))
    hi = min(height, max(y0, y1))
    band_height = hi - lo
    if band_height <= 0:
        return None, 0.0
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    clip = pymupdf.Rect(0, lo, width, hi)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=True)  # type: ignore[attr-defined]
    return pix, band_height


def build_output(header_bytes: bytes, spells_bytes: bytes, cfg: Config) -> bytes:
    """Insert the tuned header bands onto every page of the spells PDF.

    - The modifiers band is placed on the first page, and on non-first pages only
      when ``cfg.include_modifiers_on_rest`` is set.
    - The slots band is placed only on the first page, and only when
      ``cfg.include_slots_on_first`` is set. When present it sits above the
      modifiers band (slots on top).
    - On non-first pages, ``cfg.top_margin`` points of whitespace are added above
      the modifiers band so it isn't flush against the top edge.
    - Content is pushed down by ``cfg.push_offset`` points below the top of the
      modifiers band, so the slots band (page 1) and the top margin (pages 2+)
      above it are accounted for automatically.

    Returns the merged PDF as bytes. Output page size matches each spells page.
    """
    cfg.validate()
    header_doc = _open(header_bytes)
    spells_doc = _open(spells_bytes)
    output_doc = pymupdf.open()
    try:
        page_index = min(cfg.header_page_index, len(header_doc) - 1)

        slots_pix, slots_h = render_band(
            header_doc, page_index, cfg.slots_y0, cfg.slots_y1, cfg.render_dpi
        )
        mods_pix, mods_h = render_band(
            header_doc, page_index, cfg.modifiers_y0, cfg.modifiers_y1, cfg.render_dpi
        )

        for i in range(len(spells_doc)):
            src = spells_doc.load_page(i)
            page_width = src.rect.width
            page_height = src.rect.height
            new_page = output_doc.new_page(width=page_width, height=page_height)  # type: ignore[attr-defined]

            # Lay out header bands from the top, tracking where the modifiers band
            # starts so the content shift can account for the slots band (page 1)
            # or the top margin (pages 2+) sitting above it.
            bands: list[tuple[pymupdf.Pixmap, float, float]] = []  # (pix, y_top, h)
            mods_top: float | None = None
            if i == 0:
                y = 0.0
                if cfg.include_slots_on_first and slots_pix is not None:
                    bands.append((slots_pix, y, slots_h))
                    y += slots_h
                if mods_pix is not None:
                    mods_top = y
                    bands.append((mods_pix, y, mods_h))
            elif cfg.include_modifiers_on_rest and mods_pix is not None:
                mods_top = cfg.top_margin
                bands.append((mods_pix, cfg.top_margin, mods_h))

            for pix, y_top, h in bands:
                rect = pymupdf.Rect(0, y_top, page_width, y_top + h)
                new_page.insert_image(rect, pixmap=pix)

            # Content is pushed down by push_offset measured from the top of the
            # modifiers band, so page 1 (slots band above) and pages 2+ (top margin
            # above) shift accordingly. Pages with no header are left unshifted.
            shift = (mods_top + cfg.push_offset) if mods_top is not None else 0.0
            content_rect = pymupdf.Rect(0, shift, page_width, shift + page_height)
            new_page.show_pdf_page(content_rect, spells_doc, i)

        return output_doc.tobytes()
    finally:
        output_doc.close()
        spells_doc.close()
        header_doc.close()


if __name__ == "__main__":
    import argparse
    import pathlib

    parser = argparse.ArgumentParser(description="Insert header bands onto a spells PDF.")
    parser.add_argument("header", type=pathlib.Path, help="header PDF")
    parser.add_argument("spells", type=pathlib.Path, help="spells PDF")
    parser.add_argument("-o", "--output", type=pathlib.Path, default="out.pdf")
    parser.add_argument("--page", type=int, default=0, help="header page index")
    args = parser.parse_args()

    cfg = Config(header_page_index=args.page)
    out = build_output(args.header.read_bytes(), args.spells.read_bytes(), cfg)
    args.output.write_bytes(out)
    print(f"Wrote {args.output}")
