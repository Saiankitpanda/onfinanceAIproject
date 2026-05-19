import pymupdf
import pytesseract
from PIL import Image
import io


def ocr_image_file(file_path: str):
    image = Image.open(file_path)

    data = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT
    )

    blocks = []

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

        blocks.append({
            "page": 1,
            "text": text,
            "bbox": [x, y, x + w, y + h],
            "confidence": confidence / 100,
            "block_order": i
        })

    return blocks


def ocr_pdf_file(file_path: str):
    doc = pymupdf.open(file_path)
    all_blocks = []

    for page_index, page in enumerate(doc):
        page_number = page_index + 1

        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))

        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT
        )

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

            all_blocks.append({
                "page": page_number,
                "text": text,
                "bbox": [x, y, x + w, y + h],
                "confidence": confidence / 100,
                "block_order": i
            })

    return all_blocks

