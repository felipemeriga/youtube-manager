import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings():
    with patch("config.settings") as mock:
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_service_key = "test-service-key"
        mock.gemini_api_key = "test-gemini-key"
        mock.guardian_url = "http://localhost:3000"
        mock.guardian_api_key = "test-guardian-key"
        mock.cors_origins = "http://localhost:5173"
        yield mock


@pytest.fixture
def client(mock_settings):
    from main import app

    return TestClient(app)


@pytest.fixture
def valid_user_id():
    return "550e8400-e29b-41d4-a716-446655440000"
