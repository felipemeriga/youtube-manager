import time
from unittest.mock import patch, MagicMock

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from auth import get_current_user

# Generate a test EC key pair for ES256
_private_key = ec.generate_private_key(ec.SECP256R1())
_public_key = _private_key.public_key()


def create_test_token(
    user_id: str = "test-user",
    expired: bool = False,
    audience: str = "authenticated",
    include_sub: bool = True,
    kid: str = "test-kid",
) -> str:
    payload = {
        "aud": audience,
        "exp": int(time.time()) + (-3600 if expired else 3600),
        "iat": int(time.time()),
    }
    if include_sub:
        payload["sub"] = user_id
    return jwt.encode(
        payload,
        _private_key,
        algorithm="ES256",
        headers={"kid": kid},
    )


def _mock_jwks_client():
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_key
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return mock_client


def _create_app_and_client():
    app = FastAPI()

    @app.get("/test")
    async def test_route(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    return TestClient(app)


def test_valid_token_returns_user_id(valid_user_id):
    token = create_test_token(user_id=valid_user_id)
    client = _create_app_and_client()

    with patch("auth._jwks_client", _mock_jwks_client()):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == valid_user_id


def test_missing_token_returns_401():
    client = _create_app_and_client()
    response = client.get("/test")
    assert response.status_code == 401


def test_expired_token_returns_401(valid_user_id):
    token = create_test_token(user_id=valid_user_id, expired=True)
    client = _create_app_and_client()

    with patch("auth._jwks_client", _mock_jwks_client()):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_invalid_jwt_format_returns_401():
    client = _create_app_and_client()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("bad")

    with patch("auth._jwks_client", mock_client):
        response = client.get(
            "/test", headers={"Authorization": "Bearer not-a-valid-jwt"}
        )

    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_wrong_audience_returns_401():
    token = create_test_token(audience="wrong-audience")
    client = _create_app_and_client()

    with patch("auth._jwks_client", _mock_jwks_client()):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_without_sub_claim_returns_401():
    token = create_test_token(include_sub=False)
    client = _create_app_and_client()

    with patch("auth._jwks_client", _mock_jwks_client()):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert "no sub claim" in response.json()["detail"]


def test_authorization_header_without_bearer_prefix_returns_401():
    client = _create_app_and_client()
    response = client.get("/test", headers={"Authorization": "Token some-token"})
    assert response.status_code == 401
    assert "Missing authorization token" in response.json()["detail"]


def test_empty_bearer_token_returns_401():
    """Bearer prefix with empty token string should fail validation."""
    client = _create_app_and_client()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError(
        "Not enough segments"
    )

    with patch("auth._jwks_client", mock_client):
        response = client.get("/test", headers={"Authorization": "Bearer "})

    assert response.status_code == 401


def test_jwks_client_network_error_is_unhandled():
    """When JWKS client cannot fetch signing keys, PyJWKClientError propagates.

    PyJWKClientError is not a subclass of InvalidTokenError or ExpiredSignatureError,
    so the auth handler does not catch it. This documents the current behavior gap.
    """
    import pytest

    client = _create_app_and_client()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError(
        "Failed to fetch JWKS"
    )

    with patch("auth._jwks_client", mock_client):
        with pytest.raises(jwt.PyJWKClientError, match="Failed to fetch JWKS"):
            client.get("/test", headers={"Authorization": "Bearer some-token"})


def test_expired_token_detail_message():
    """Expired token should return specific 'Token expired' detail."""
    token = create_test_token(expired=True)
    client = _create_app_and_client()

    with patch("auth._jwks_client", _mock_jwks_client()):
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_missing_auth_header_detail_message():
    """Missing Authorization header should return specific detail message."""
    client = _create_app_and_client()
    response = client.get("/test")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authorization token"


def test_empty_authorization_header_returns_401():
    """Empty Authorization header string should fail."""
    client = _create_app_and_client()
    response = client.get("/test", headers={"Authorization": ""})
    assert response.status_code == 401
    assert "Missing authorization token" in response.json()["detail"]


def test_bearer_only_whitespace_returns_401():
    """Authorization header 'Bearer   ' (whitespace only) should fail."""
    client = _create_app_and_client()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("bad")

    with patch("auth._jwks_client", mock_client):
        response = client.get("/test", headers={"Authorization": "Bearer    "})

    assert response.status_code == 401
