import os

from app.services.agent_service import run_clause_agent


def test_agent_returns_api_key_message(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_clause_agent(
        task="summarize",
        clauses=[{"clause_id": "1", "text": "This is a clause."}],
        question="What does it say?",
    )

    assert "OPENAI_API_KEY is missing" in result


def test_agent_returns_clause_empty_message(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy_api_key")

    result = run_clause_agent(task="summarize", clauses=[], question="Any question?")

    assert "No clauses were provided" in result
