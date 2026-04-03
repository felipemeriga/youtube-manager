from unittest.mock import patch
import os


def test_settings_loads_from_env_vars():
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "SUPABASE_JWT_SECRET": "test-jwt-secret",
        "GEMINI_API_KEY": "test-gemini-key",
        "GUARDIAN_URL": "http://custom-guardian:3000",
        "GUARDIAN_API_KEY": "test-guardian-key",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.supabase_url == "https://test.supabase.co"
    assert s.guardian_url == "http://custom-guardian:3000"
    assert s.cors_origins == "http://localhost:3000,http://localhost:5173"


def test_settings_guardian_url_default():
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "SUPABASE_JWT_SECRET": "test-jwt-secret",
        "GEMINI_API_KEY": "test-gemini-key",
        "GUARDIAN_API_KEY": "test-guardian-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.guardian_url == "http://server-guardian:3000"
    assert s.cors_origins == "http://localhost:5173"
