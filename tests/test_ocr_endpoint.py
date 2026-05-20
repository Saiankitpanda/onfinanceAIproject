import json

from fastapi.testclient import TestClient

from app.api import routes_documents
from app.main import app

client = TestClient(app)


def test_ocr_endpoint_returns_saved_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(routes_documents, "OUTPUT_DIR", str(tmp_path / "outputs"))

    document_id = "doc_ocr_test"
    document_dir = tmp_path / "outputs" / document_id
    document_dir.mkdir(parents=True)

    payload = {
        "document_id": document_id,
        "filename": "sample.pdf",
        "processing_mode": "ocr_pdf",
        "total_blocks": 0,
        "blocks": [],
    }

    (document_dir / "ocr_blocks.json").write_text(json.dumps(payload))

    response = client.get(f"/documents/{document_id}/ocr")

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["processing_mode"] == "ocr_pdf"
