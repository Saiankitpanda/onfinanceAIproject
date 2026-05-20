import os
import re
from uuid import uuid4


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return f"upload_{uuid4().hex}"

    base_name = os.path.basename(filename)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)
    safe_name = safe_name.strip("._")

    if not safe_name:
        return f"upload_{uuid4().hex}"

    return safe_name
