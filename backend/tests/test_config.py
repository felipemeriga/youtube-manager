from unittest.mock import patch
import os


def test_settings_loads_from_env_vars():
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "GEMINI_API_KEY": "test-gemini-key",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.supabase_url == "https://test.supabase.co"
    assert s.cors_origins == "http://localhost:3000,http://localhost:5173"


def test_settings_missing_required_fields_raises():
    import pytest
    from pydantic import ValidationError

    with patch.dict(os.environ, {}, clear=True):
        from config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)


def test_settings_missing_only_gemini_key_raises():
    import pytest
    from pydantic import ValidationError

    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)


def test_settings_cors_origins_default():
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "GEMINI_API_KEY": "test-gemini-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.cors_origins == "http://localhost:5173"
