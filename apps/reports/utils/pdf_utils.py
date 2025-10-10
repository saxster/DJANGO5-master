"""
PDF Utilities

Utility functions for PDF manipulation and highlighting.

Extracted from apps/reports/views/pdf_views.py
Date: 2025-10-10
"""


def highlight_text_in_pdf(
    input_pdf_path, output_pdf_path, texts_to_highlight, page_required
):
    """Highlight specified texts in PDF and optionally filter pages"""
    import fitz  # PyMuPDF library

    # Open the PDF
    document = fitz.open(input_pdf_path)
    pages_to_keep = []
    orange_color = (1, 0.647, 0)  # RGB values for orange

    # Normalize the texts_to_highlight to a flat list
    if any(isinstance(item, list) for item in texts_to_highlight):
        normalized_texts_to_highlight = [
            text for sublist in texts_to_highlight for text in sublist
        ]
    else:
        normalized_texts_to_highlight = texts_to_highlight

    # Function to handle text splitting
    def find_and_highlight_text(page, text):
        """Search for text and highlight it if not already highlighted."""
        words = page.get_text("words")  # Extract words as bounding boxes
        existing_highlights = page.annots()  # Get existing annotations on the page

        # Helper function to check if a bounding box overlaps with existing highlights
        def is_already_highlighted(bbox):
            if not existing_highlights:
                return False
            for annot in existing_highlights:
                if annot.rect.intersects(fitz.Rect(bbox)):
                    return True
            return False

        for i, word in enumerate(words):
            if text.startswith(word[4]):
                combined_text = word[4]
                bbox = [word[:4]]  # Collect bounding boxes
                j = i + 1

                # Try to combine subsequent words
                while j < len(words) and not combined_text == text:
                    combined_text += words[j][4]
                    bbox.append(words[j][:4])
                    j += 1

                if combined_text == text:
                    # Highlight only if not already highlighted
                    if not any(is_already_highlighted(box) for box in bbox):
                        for box in bbox:
                            highlight = page.add_highlight_annot(fitz.Rect(box))
                            highlight.set_colors(
                                stroke=orange_color
                            )  # Set highlight color
                            highlight.update()
                        return True
        return False

    # Check and highlight text on each page
    for page_num in range(document.page_count):
        page = document[page_num]
        page_has_highlight = False
        for text in normalized_texts_to_highlight:
            if text and find_and_highlight_text(page, text):
                page_has_highlight = True

        # Logic to determine whether to keep the page
        if page_required:
            if page_has_highlight or page_num == 0:  # Always keep the first page
                pages_to_keep.append(page_num)
        else:
            if (
                page_has_highlight
                or page_num == 0
                or page_num == document.page_count - 1
            ):  # Keep first, last, and highlighted pages
                pages_to_keep.append(page_num)

    # Create a new document with all pages to be kept
    new_document = fitz.open()
    for page_num in pages_to_keep:
        new_document.insert_pdf(document, from_page=page_num, to_page=page_num)

    # Save the updated PDF
    new_document.save(output_pdf_path)
    new_document.close()
    document.close()
