from unittest.mock import patch
import os


def test_settings_loads_from_env_vars():
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
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
        "GEMINI_API_KEY": "test-gemini-key",
        "GUARDIAN_API_KEY": "test-guardian-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.guardian_url == "http://server-guardian:3000"
    assert s.cors_origins == "http://localhost:5173"


def test_settings_missing_required_fields_raises():
    """Settings without required env vars should raise a validation error."""
    import pytest
    from pydantic import ValidationError

    with patch.dict(os.environ, {}, clear=True):
        from config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)


def test_settings_missing_only_gemini_key_raises():
    """Settings missing just one required field should raise."""
    import pytest
    from pydantic import ValidationError

    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "GUARDIAN_API_KEY": "test-guardian-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)


def test_settings_cors_origins_default():
    """Default CORS origin should be localhost:5173."""
    env_vars = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "GEMINI_API_KEY": "test-gemini-key",
        "GUARDIAN_API_KEY": "test-guardian-key",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        from config import Settings

        s = Settings(_env_file=None)

    assert s.cors_origins == "http://localhost:5173"
