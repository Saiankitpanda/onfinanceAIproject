from app.services.clause_service import group_blocks_into_clauses


def test_group_blocks_into_clauses():
    blocks = [
        {
            "page": 1,
            "text": "1. Applicability",
            "bbox": [0, 0, 100, 20],
            "confidence": 1.0,
        },
        {
            "page": 1,
            "text": "This circular applies to all entities.",
            "bbox": [0, 25, 200, 45],
            "confidence": 1.0,
        },
        {
            "page": 1,
            "text": "2. Reporting",
            "bbox": [0, 60, 100, 80],
            "confidence": 1.0,
        },
    ]

    clauses = group_blocks_into_clauses(blocks)

    assert len(clauses) == 2
    assert clauses[0]["clause_id"] == "1"
    assert "This circular applies" in clauses[0]["text"]
    assert clauses[1]["clause_id"] == "2"
