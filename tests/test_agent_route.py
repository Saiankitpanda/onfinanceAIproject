import json
from dataclasses import dataclass

from app.api import routes_documents


@dataclass
class FakeAnswer:
    answer: str
    source_clause_indices: list[int]
    confidence: str


@dataclass
class FakeRisk:
    clause_index: int
    clause_preview: str
    risk_type: str
    severity: str
    reason: str


def test_agent_route_returns_structured_response_without_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(routes_documents, "OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(
        routes_documents,
        "query_agent",
        lambda question, clauses: FakeAnswer(
            answer="Clause 0 answers the question.",
            source_clause_indices=[0],
            confidence="high",
        ),
    )
    monkeypatch.setattr(
        routes_documents,
        "flag_risky_clauses",
        lambda clauses: [
            FakeRisk(
                clause_index=1,
                clause_preview="The vendor shall indemnify the customer.",
                risk_type="indemnity",
                severity="high",
                reason="Indemnity can create significant liability.",
            )
        ],
    )

    document_id = "doc_agent_test"
    document_dir = tmp_path / "outputs" / document_id
    document_dir.mkdir(parents=True)
    (document_dir / "clauses.json").write_text(
        json.dumps(
            {
                "document_id": document_id,
                "clauses": [
                    {
                        "text": "1. Reporting is due within 15 days.",
                        "page_start": 1,
                    },
                    {
                        "text": "2. The vendor shall indemnify the customer.",
                        "page_start": 2,
                    },
                ],
            }
        )
    )

    payload = routes_documents.ask_agent.__wrapped__(
        request=None,
        document_id=document_id,
        body=routes_documents.AgentRequest(question="When is reporting due?"),
    )

    assert payload == {
        "answer": "Clause 0 answers the question.",
        "source_clauses": [
            {
                "index": 0,
                "preview": "1. Reporting is due within 15 days.",
                "page": 1,
            }
        ],
        "risky_clauses": [
            {
                "index": 1,
                "preview": "The vendor shall indemnify the customer.",
                "risk_type": "indemnity",
                "severity": "high",
                "reason": "Indemnity can create significant liability.",
            }
        ],
        "confidence": "high",
    }
