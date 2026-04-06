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


def test_health_response_structure(client):
    """Health endpoint should return exactly the expected structure."""
    response = client.get("/api/health")
    data = response.json()
    assert set(data.keys()) == {"status"}
    assert data["status"] == "ok"


def test_cors_allows_all_methods(client):
    """CORS should allow all HTTP methods."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_allows_credentials(client):
    """CORS should allow credentials."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_allows_all_headers(client):
    """CORS should allow all request headers."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    allow_headers = response.headers.get("access-control-allow-headers", "")
    assert "authorization" in allow_headers.lower()


def test_nonexistent_route_returns_404(client):
    """Accessing a route that does not exist should return 404."""
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
