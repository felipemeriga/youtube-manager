def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_headers(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    )
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORS middleware won't set allow-origin for disallowed origins
    assert response.headers.get("access-control-allow-origin") != "http://evil.com"
