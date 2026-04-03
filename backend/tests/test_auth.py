import jwt
import time
from unittest.mock import patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from auth import get_current_user


def create_test_token(user_id: str, secret: str, expired: bool = False) -> str:
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": int(time.time()) + (-3600 if expired else 3600),
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_token_returns_user_id(valid_user_id):
    secret = "test-jwt-secret"
    token = create_test_token(valid_user_id, secret)

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == valid_user_id


def test_missing_token_returns_401():
    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 401


def test_expired_token_returns_401(valid_user_id):
    secret = "test-jwt-secret"
    token = create_test_token(valid_user_id, secret, expired=True)

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_invalid_jwt_format_returns_401():
    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = "test-jwt-secret"
        response = client.get(
            "/test", headers={"Authorization": "Bearer not-a-valid-jwt"}
        )

    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_wrong_audience_returns_401():
    secret = "test-jwt-secret"
    payload = {
        "sub": "user-123",
        "aud": "wrong-audience",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_without_sub_claim_returns_401():
    secret = "test-jwt-secret"
    payload = {
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")

    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)

    with patch("auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = secret
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert "no sub claim" in response.json()["detail"]


def test_authorization_header_without_bearer_prefix_returns_401():
    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    client = TestClient(app)
    response = client.get("/test", headers={"Authorization": "Token some-token"})
    assert response.status_code == 401
    assert "Missing authorization token" in response.json()["detail"]
