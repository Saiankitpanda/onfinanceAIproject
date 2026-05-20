import io

from fastapi.testclient import TestClient

from app.api import routes_documents
from app.main import app


def make_pdf_bytes():
    # Minimal PDF header bytes; processor functions are monkeypatched in the test
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\ntrailer\n%%EOF\n"


def test_full_pipeline_upload_process_and_fetch(tmp_path, monkeypatch):
    # Redirect upload/output dirs to temp
    routes_documents.UPLOAD_DIR = str(tmp_path / "uploads")
    routes_documents.OUTPUT_DIR = str(tmp_path / "outputs")

    # Ensure dirs exist
    (tmp_path / "uploads").mkdir()
    (tmp_path / "outputs").mkdir()

    # Monkeypatch extraction pipeline to avoid heavy deps
    sample_blocks = [
        {"page": 1, "text": "1. Clause 1: Do X.", "bbox": [0, 0, 100, 10]},
        {"page": 1, "text": "2. Clause 2: Do Y.", "bbox": [0, 12, 100, 22]},
    ]

    # Patch the names used by routes_documents (they were imported at module level)
    monkeypatch.setattr(routes_documents, "is_text_pdf", lambda path: True)
    monkeypatch.setattr(
        routes_documents, "extract_text_blocks_from_pdf", lambda path: sample_blocks
    )
    monkeypatch.setattr(routes_documents, "ocr_pdf_file", lambda path: sample_blocks)
    monkeypatch.setattr(routes_documents, "ocr_image_file", lambda path: sample_blocks)

    client = TestClient(app)

    pdf_bytes = make_pdf_bytes()

    files = {"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    resp = client.post("/documents/upload", files=files)
    assert resp.status_code == 200, resp.text
    meta = resp.json()
    assert meta["status"] == "uploaded"
    doc_id = meta["document_id"]

    # Process
    resp2 = client.post(f"/documents/{doc_id}/process")
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()
    assert data["status"] == "processed"
    assert data["total_blocks"] == len(sample_blocks)
    assert data["total_clauses"] >= 0

    # Fetch OCR blocks
    resp3 = client.get(f"/documents/{doc_id}/ocr")
    assert resp3.status_code == 200, resp3.text
    ocr = resp3.json()
    assert ocr["total_blocks"] == len(sample_blocks)

    # Fetch clauses
    resp4 = client.get(f"/documents/{doc_id}/clauses")
    assert resp4.status_code == 200, resp4.text
    clauses = resp4.json()
    assert clauses["document_id"] == doc_id
