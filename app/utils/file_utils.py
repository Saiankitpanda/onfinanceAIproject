import os
import re
from uuid import uuid4


def sanitize_filename(filename: str | None) -> str:
    """
    Convert uploaded filename into a safe filename.

    Prevents:
    - path traversal like ../../secret.txt
    - unsafe symbols
    - empty filenames
    """

    if not filename:
        return f"upload_{uuid4().hex}"

    base_name = os.path.basename(filename)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
    safe_name = safe_name.strip("._")

    if not safe_name:
        return f"upload_{uuid4().hex}"

    return safe_name


def is_allowed_magic(file_path: str, allowed_extensions: list[str]) -> bool:
    """Check the file magic bytes to ensure the saved file matches an allowed type.

    Supports basic checks for PDF, PNG, JPEG, and TIFF.
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
    except Exception:
        return False

    header_lower = header

    # PDF
    if ".pdf" in allowed_extensions and header_lower.startswith(b"%PDF-"):
        return True

    # PNG
    if ".png" in allowed_extensions and header_lower.startswith(b"\x89PNG\r\n\x1a\n"):
        return True

    # JPEG (starts with FF D8 FF)
    if any(ext in allowed_extensions for ext in [".jpg", ".jpeg"]) and header_lower.startswith(b"\xff\xd8\xff"):
        return True

    # TIFF (little/big endian)
    if ".tiff" in allowed_extensions and (header_lower.startswith(b"II*\x00") or header_lower.startswith(b"MM\x00*")):
        return True

    return False
