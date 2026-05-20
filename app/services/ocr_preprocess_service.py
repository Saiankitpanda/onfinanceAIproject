from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Preprocess an image to improve OCR quality.

    Steps:
    - convert to grayscale
    - resize (upscale) to help OCR
    - denoise
    - adaptive thresholding
    - return a cleaned PIL image
    """
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")

    gray = image.convert("L")
    np_img = np.array(gray)

    # Upscale small scans to improve character shapes for OCR.
    h, w = np_img.shape[:2]
    scale = 2.0 if max(h, w) < 1800 else 1.5
    resized = cv2.resize(
        np_img, dsize=None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
    )

    # Denoise while preserving edges.
    denoised = cv2.fastNlMeansDenoising(resized, h=12)

    # Improve contrast and binarize using adaptive thresholding.
    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    # Light morphology to connect broken strokes and reduce speckle noise.
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    return Image.fromarray(cleaned)
