"""Verify GZipMiddleware compresses large JSON responses."""

from fastapi.testclient import TestClient

from main import app


def test_large_json_response_is_gzipped():
    client = TestClient(app)
    # Public OpenAPI schema is ~30KB and unauthenticated.
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_small_response_not_gzipped():
    client = TestClient(app)
    response = client.get("/docs", headers={"Accept-Encoding": "gzip"})
    if int(response.headers.get("content-length", "9999")) < 1024:
        assert response.headers.get("content-encoding") != "gzip"
