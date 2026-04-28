"""Tests for the Supabase client pool (singleton pattern)."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the singleton state between tests."""
    from services import supabase_pool

    supabase_pool._sync_client = None
    supabase_pool._async_client = None
    yield
    supabase_pool._sync_client = None
    supabase_pool._async_client = None


@patch("services.supabase_pool.settings")
@patch("services.supabase_pool._create_sync")
def test_get_sync_client_returns_singleton(mock_create, mock_settings):
    """get_sync_client() should return the same instance on repeated calls."""
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_service_key = "test-key"
    fake_client = MagicMock()
    mock_create.return_value = fake_client

    from services.supabase_pool import get_sync_client

    c1 = get_sync_client()
    c2 = get_sync_client()

    assert c1 is c2
    mock_create.assert_called_once()


@patch("services.supabase_pool.settings")
@patch("services.supabase_pool._create_async")
@pytest.mark.asyncio
async def test_get_async_client_returns_singleton(mock_create, mock_settings):
    """get_async_client() should return the same instance on repeated calls."""
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_service_key = "test-key"
    fake_client = AsyncMock()
    mock_create.return_value = fake_client

    from services.supabase_pool import get_async_client

    c1 = await get_async_client()
    c2 = await get_async_client()

    assert c1 is c2
    mock_create.assert_called_once()


@patch("services.supabase_pool.settings")
@patch("services.supabase_pool._create_sync")
def test_get_sync_client_creates_on_first_call(mock_create, mock_settings):
    """First call creates the client; subsequent calls reuse it."""
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_service_key = "test-key"
    mock_create.return_value = MagicMock()

    from services.supabase_pool import get_sync_client

    get_sync_client()
    mock_create.assert_called_once_with("https://test.supabase.co", "test-key")


@patch("services.supabase_pool.settings")
@patch("services.supabase_pool._create_async")
@pytest.mark.asyncio
async def test_get_async_client_creates_on_first_call(mock_create, mock_settings):
    """First call creates the client; subsequent calls reuse it."""
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_service_key = "test-key"
    mock_create.return_value = AsyncMock()

    from services.supabase_pool import get_async_client

    await get_async_client()
    mock_create.assert_called_once_with("https://test.supabase.co", "test-key")
