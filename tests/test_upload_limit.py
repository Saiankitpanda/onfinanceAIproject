import io
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes_documents


def test_oversized_upload_fails(monkeypatch):
    # Make the max upload size very small to trigger fast-fail
    monkeypatch.setattr(routes_documents, "MAX_UPLOAD_SIZE", 10)

    client = TestClient(app)

    # Send a payload larger than 10 bytes
    files = {"file": ("big.pdf", io.BytesIO(b"0" * 1024), "application/pdf")}

    resp = client.post("/documents/upload", files=files)
    assert resp.status_code == 413
