import re


def normalize_text(text: str):
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(\d+)\s+\.", r"\1.", text)
    text = re.sub(r"\(\s*([a-z])\s*\)", r"(\1)", text)
    return text


def detect_clause_type(text: str):
    text = normalize_text(text)

    if re.match(r"^\d+\.\d+\.\d+\s+", text):
        return "sub_sub_clause"

    if re.match(r"^\d+\.\d+\s+", text):
        return "sub_clause"

    if re.match(r"^\d+\.\s+", text):
        return "main_clause"

    if re.match(r"^\([a-z]\)\s+", text.lower()):
        return "alpha_clause"

    if re.match(r"^\([ivxlcdm]+\)\s+", text.lower()):
        return "roman_clause"

    if re.match(r"^clause\s+\d+", text.lower()):
        return "clause_word"

    if re.match(r"^section\s+\d+", text.lower()):
        return "section_word"

    return None


def extract_clause_id(text: str):
    text = normalize_text(text)

    patterns = [
        r"^(\d+\.\d+\.\d+)",
        r"^(\d+\.\d+)",
        r"^(\d+)\.",
        r"^(\([a-z]\))",
        r"^(\([ivxlcdm]+\))",
        r"^(clause\s+\d+)",
        r"^(section\s+\d+)"
    ]

    for pattern in patterns:
        match = re.match(pattern, text.lower())
        if match:
            return match.group(1)

    return None


def sort_blocks(blocks):
    return sorted(
        blocks,
        key=lambda block: (
            block["page"],
            block["bbox"][1],
            block["bbox"][0]
        )
    )


def group_blocks_into_clauses(blocks):
    sorted_blocks = sort_blocks(blocks)
    clauses = []
    current_clause = None

    for block in sorted_blocks:
        text = normalize_text(block["text"])
        clause_type = detect_clause_type(text)

        if clause_type:
            if current_clause:
                clauses.append(current_clause)

            clause_id = extract_clause_id(text)

            current_clause = {
                "clause_id": clause_id,
                "clause_type": clause_type,
                "text": text,
                "page_start": block["page"],
                "page_end": block["page"],
                "blocks": [block]
            }

        else:
            if current_clause:
                current_clause["text"] += " " + text
                current_clause["page_end"] = block["page"]
                current_clause["blocks"].append(block)

    if current_clause:
        clauses.append(current_clause)

    return clauses

