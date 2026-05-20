from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_present(monkeypatch):
    # Ensure deterministic behavior: treat as production unless overridden
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "SECURITY_CSP", "default-src 'self'; script-src 'self'; style-src 'self';"
    )

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200

    # Check headers presence and values
    assert "Content-Security-Policy" in resp.headers
    assert (
        resp.headers["Content-Security-Policy"]
        == "default-src 'self'; script-src 'self'; style-src 'self';"
    )
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
