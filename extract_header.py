import fitz  # PyMuPDF

# Paths
NAME = "Elira"
header_pdf_path = f"{NAME}.pdf"
content_pdf_path = f"{NAME}_spellbook.pdf"
output_pdf_path = f"{NAME}_spells.pdf"
text = NAME
font_size = 14
text_x = 55
text_y = 78
fontname = "helv"

# Parameters
header_page_index = 3  # 4th page (zero-based index)
header_height = 100  # points; adjust as needed


# Parameters
header_page_index = 3  # 4th page (0-indexed)
header_height = 120  # in points (adjust as needed)

# Load PDFs
header_doc = fitz.open(header_pdf_path)
content_doc = fitz.open(content_pdf_path)

# Get dimensions from header page
header_page = header_doc.load_page(header_page_index)
page_width = header_page.rect.width
page_height = header_page.rect.height

# Define header rect
header_rect = fitz.Rect(0, 0, page_width, header_height)

# Render header part at high DPI (e.g. 300)
zoom = 600 / 72  # 72 DPI is default, 300 DPI for printing
mat = fitz.Matrix(zoom, zoom)

pix = header_page.get_pixmap(matrix=mat, clip=header_rect, alpha=True)  # type: ignore


# Create output PDF
output_doc = fitz.open()

for i in range(len(content_doc)):
    content_page = content_doc.load_page(i)
    new_page = output_doc.new_page(width=page_width, height=page_height)  # type: ignore

    # Insert header image (scaled back to original header height)
    rect_img = fitz.Rect(0, 0, page_width, header_height)
    new_page.insert_image(rect_img, pixmap=pix)

    # Insert content page shifted down by header_height
    shift = header_height - 30
    content_rect = fitz.Rect(0, shift, page_width, shift + page_height)

    new_page.show_pdf_page(content_rect, content_doc, i)

    # Estimate text width and height (roughly)
    text_width = fitz.get_text_length(text, fontname=fontname, fontsize=font_size)
    text_height = font_size + 4  # Add padding

    # Define the white rectangle behind the text
    bg_rect = fitz.Rect(
        text_x - 10, text_y - font_size, text_x + text_width + 4, text_y + 4
    )
    class_block_rect = fitz.Rect(70, 94, 120, 108)

    # Draw white rectangle
    new_page.draw_rect(bg_rect, color=(1, 1, 1), fill=(1, 1, 1))
    new_page.draw_rect(class_block_rect, color=(1, 1, 1), fill=(1, 1, 1))
    new_page.insert_text(
        fitz.Point(text_x, text_y),  # X, Y from top-left
        text,
        fontsize=font_size,
        fontname=fontname,
        fill=(0, 0, 0),
    )
output_doc.save(output_pdf_path)
print("✅ Combined PDF saved with rasterized header image")
