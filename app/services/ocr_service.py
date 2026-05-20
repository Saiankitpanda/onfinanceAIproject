import io

import pymupdf
import pytesseract
from PIL import Image

from app.services.ocr_preprocess_service import preprocess_for_ocr

TESSERACT_CONFIG = "--oem 3 --psm 6"


def _combine_bboxes(blocks: list[dict]) -> list[float]:
    x0 = min(b["bbox"][0] for b in blocks)
    y0 = min(b["bbox"][1] for b in blocks)
    x1 = max(b["bbox"][2] for b in blocks)
    y1 = max(b["bbox"][3] for b in blocks)
    return [x0, y0, x1, y1]


def group_words_into_lines(blocks: list[dict], y_tolerance: int = 12) -> list[dict]:
    """Group OCR word blocks into line-level blocks.

    The input blocks are expected to be word-level OCR blocks with
    `page`, `text`, `bbox`, `confidence`.
    """
    if not blocks:
        return []

    words = sorted(
        blocks,
        key=lambda b: (b["page"], b["bbox"][1], b["bbox"][0]),
    )

    lines: list[dict] = []
    current: dict | None = None

    for word in words:
        text = (word.get("text") or "").strip()
        if not text:
            continue

        x0, y0, x1, y1 = word["bbox"]
        y_center = (y0 + y1) / 2.0

        if (
            current is None
            or word["page"] != current["page"]
            or abs(y_center - current["y_center"]) > y_tolerance
        ):
            current = {
                "page": word["page"],
                "words": [word],
                "y_center": y_center,
            }
            lines.append(current)
            continue

        current["words"].append(word)
        # Keep a running mean of the line center to be robust to slight drift.
        n = len(current["words"])
        current["y_center"] = (current["y_center"] * (n - 1) + y_center) / n

    # Build final line blocks.
    out: list[dict] = []
    block_order = 0

    for line in lines:
        line_words = sorted(line["words"], key=lambda w: w["bbox"][0])
        line_text = " ".join(w["text"].strip() for w in line_words if w.get("text"))
        if not line_text:
            continue

        bbox = _combine_bboxes(line_words)
        confs = [float(w.get("confidence", 0)) for w in line_words]
        confidence = round(sum(confs) / len(confs), 2) if confs else 0.0

        out.append(
            {
                "page": line["page"],
                "text": line_text,
                "bbox": bbox,
                "confidence": confidence,
                "block_order": block_order,
            }
        )
        block_order += 1

    return out


def _ocr_pil_image(image: Image.Image, page_number: int):
    processed = preprocess_for_ocr(image)

    data = pytesseract.image_to_data(
        processed,
        output_type=pytesseract.Output.DICT,
        config=TESSERACT_CONFIG,
    )

    word_blocks = []

    for i in range(len(data["text"])):
        text = data["text"][i].strip()

        if not text:
            continue

        confidence = float(data["conf"][i])

        if confidence < 40:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        word_blocks.append(
            {
                "page": page_number,
                "text": text,
                "bbox": [x, y, x + w, y + h],
                "confidence": confidence / 100,
                "block_order": i,
            }
        )

    return group_words_into_lines(word_blocks)


def ocr_image_file(file_path: str):
    image = Image.open(file_path)
    return _ocr_pil_image(image=image, page_number=1)


def ocr_pdf_file(file_path: str):
    doc = pymupdf.open(file_path)
    all_line_blocks = []
    block_order = 0

    for page_index, page in enumerate(doc):
        page_number = page_index + 1

        pix = page.get_pixmap(dpi=250)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))

        page_lines = _ocr_pil_image(image=image, page_number=page_number)
        for line in page_lines:
            line["block_order"] = block_order
            block_order += 1
            all_line_blocks.append(line)

    return all_line_blocks
