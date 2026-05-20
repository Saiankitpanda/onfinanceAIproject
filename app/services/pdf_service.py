import pymupdf


def extract_text_blocks_from_pdf(file_path: str):
    doc = pymupdf.open(file_path)
    blocks = []

    for page_index, page in enumerate(doc):
        page_number = page_index + 1
        page_blocks = page.get_text("blocks")

        for block_index, block in enumerate(page_blocks):
            x0, y0, x1, y1, text, *_ = block

            clean_text = text.strip().replace("\n", " ")

            if clean_text:
                blocks.append(
                    {
                        "page": page_number,
                        "text": clean_text,
                        "bbox": [x0, y0, x1, y1],
                        "confidence": 1.0,
                        "block_order": block_index,
                    }
                )

    return blocks


def is_text_pdf(file_path: str, min_text_length: int = 50):
    doc = pymupdf.open(file_path)
    total_text = ""

    for page in doc:
        total_text += page.get_text()

    return len(total_text.strip()) >= min_text_length
