def combine_bboxes(blocks):
    x_min = min(block["bbox"][0] for block in blocks)
    y_min = min(block["bbox"][1] for block in blocks)
    x_max = max(block["bbox"][2] for block in blocks)
    y_max = max(block["bbox"][3] for block in blocks)

    return [x_min, y_min, x_max, y_max]


def average_confidence(blocks):
    if not blocks:
        return 0

    total = sum(block.get("confidence", 0) for block in blocks)
    return round(total / len(blocks), 2)


def enrich_clauses_with_annotations(clauses):
    enriched = []

    for clause in clauses:
        blocks = clause.get("blocks", [])

        if not blocks:
            continue

        bbox = combine_bboxes(blocks)

        enriched_clause = {
            "clause_id": clause["clause_id"],
            "clause_type": clause["clause_type"],
            "text": clause["text"],
            "page_start": clause["page_start"],
            "page_end": clause["page_end"],
            "bbox": bbox,
            "confidence": average_confidence(blocks)
        }

        enriched.append(enriched_clause)

    return enriched


def build_page_annotations(clauses):
    pages = {}

    for clause in clauses:
        page = clause["page_start"]

        if page not in pages:
            pages[page] = []

        pages[page].append({
            "clause_id": clause["clause_id"],
            "clause_type": clause["clause_type"],
            "bbox": clause["bbox"],
            "label": f"Clause {clause['clause_id']}"
        })

    return [
        {
            "page_number": page,
            "annotations": annotations
        }
        for page, annotations in pages.items()
    ]

