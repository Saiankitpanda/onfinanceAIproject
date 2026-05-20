from fastapi.testclient import TestClient

from app.api import routes_documents
from app.main import app


client = TestClient(app)


def test_upload_rejects_txt_file():
    response = client.post(
        "/documents/upload",
        files={"file": ("bad.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type"


def test_upload_sanitizes_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(routes_documents, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(routes_documents, "OUTPUT_DIR", str(tmp_path / "outputs"))

    response = client.post(
        "/documents/upload",
        files={"file": ("../../unsafe file.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "unsafe_file.pdf"


def test_process_document_with_mocked_pdf_extraction(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    document_id = "doc_test1234"
    document_upload_dir = upload_dir / document_id
    document_output_dir = output_dir / document_id

    document_upload_dir.mkdir(parents=True)
    document_output_dir.mkdir(parents=True)
    pdf_path = document_upload_dir / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    (document_output_dir / "metadata.json").write_text(
        '{"document_id":"doc_test1234","filename":"sample.pdf","file_path":"'
        + str(pdf_path)
        + '","file_type":".pdf","status":"uploaded"}'
    )

    monkeypatch.setattr(routes_documents, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(routes_documents, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(routes_documents, "is_text_pdf", lambda path: True)
    monkeypatch.setattr(
        routes_documents,
        "extract_text_blocks_from_pdf",
        lambda path: [
            {
                "page": 1,
                "text": "1. Applicability",
                "bbox": [0, 0, 100, 20],
                "confidence": 1.0,
                "block_order": 0,
            },
            {
                "page": 1,
                "text": "This circular applies to all entities.",
                "bbox": [0, 25, 200, 45],
                "confidence": 1.0,
                "block_order": 1,
            },
        ],
    )

    response = client.post(f"/documents/{document_id}/process")

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["total_clauses"] == 1
