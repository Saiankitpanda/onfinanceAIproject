from app.services.agent_service import run_clause_agent


def test_agent_falls_back_locally_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_clause_agent(
        task="summarize",
        clauses=[{"clause_id": "1", "clause_type": "main_clause", "text": "1. Applicability. This circular applies to all entities.", "page_start": 1, "page_end": 1}],
        question="What does it say?",
    )

    assert "Local agent summary" in result
    assert "Clause 1" in result


def test_agent_returns_local_answer_for_question(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy_api_key")
    monkeypatch.setenv("AGENT_USE_OPENAI", "0")

    clauses = [
        {
            "clause_id": "2",
            "clause_type": "main_clause",
            "text": "2. Reporting. Regulated entities shall submit reports within 15 days.",
            "page_start": 2,
            "page_end": 2,
        }
    ]

    result = run_clause_agent(
        task="answer_question",
        clauses=clauses,
        question="When is reporting due?",
    )

    assert "Local answer based on the matching clauses" in result or "Question understood" in result
    assert "Clause 2" in result
