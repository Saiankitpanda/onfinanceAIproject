from app.services.agent_service import flag_risky_clauses, query_agent


def test_query_agent_falls_back_locally_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = query_agent(
        question="What does it say about applicability?",
        clauses=[
            {
                "clause_id": "1",
                "clause_type": "main_clause",
                "text": "1. Applicability. This circular applies to all entities.",
                "page_start": 1,
                "page_end": 1,
            }
        ],
    )

    assert "[Local fallback]" in result.answer
    assert result.source_clause_indices == [0]
    assert result.confidence == "low"


def test_query_agent_returns_low_confidence_without_match(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = query_agent(
        question="When is reporting due?",
        clauses=[
            {
                "clause_id": "1",
                "clause_type": "main_clause",
                "text": "1. Applicability. This circular applies to all entities.",
                "page_start": 1,
                "page_end": 1,
            }
        ],
    )

    assert "No matching clause found" in result.answer
    assert result.source_clause_indices == []
    assert result.confidence == "low"


def test_flag_risky_clauses_uses_local_keyword_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    flags = flag_risky_clauses(
        [
            {
                "text": "The vendor shall indemnify the customer against all claims.",
                "page_start": 2,
            },
            {
                "text": "This clause contains ordinary notice information.",
                "page_start": 3,
            },
        ]
    )

    assert len(flags) == 1
    assert flags[0].clause_index == 0
    assert flags[0].risk_type == "indemnity"
    assert flags[0].severity == "high"
