"""Shared Supabase client singletons.

Instead of creating a new client per request (which exhausts the HTTP/2
connection pool under load), this module provides cached singletons for
both sync and async Supabase clients.
"""

from supabase import create_client as _create_sync
from supabase._async.client import create_client as _create_async

from config import settings

_sync_client = None
_async_client = None


def get_sync_client():
    """Return a shared synchronous Supabase client (singleton)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = _create_sync(
            settings.supabase_url, settings.supabase_service_key
        )
    return _sync_client


async def get_async_client():
    """Return a shared asynchronous Supabase client (singleton)."""
    global _async_client
    if _async_client is None:
        _async_client = await _create_async(
            settings.supabase_url, settings.supabase_service_key
        )
    return _async_client
