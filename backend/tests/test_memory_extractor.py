from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.memory_extractor import MAX_MEMORIES, extract_memory


def make_sb(memories=None):
    """Build a mock async Supabase client."""
    sb = MagicMock()

    # .select().eq().order().execute() — async
    select_chain = MagicMock()
    select_chain.execute = AsyncMock(
        return_value=MagicMock(data=memories if memories is not None else [])
    )
    select_chain.order = MagicMock(return_value=select_chain)
    select_chain.eq = MagicMock(return_value=select_chain)
    sb.table.return_value.select.return_value = select_chain

    # .delete().eq().execute() — async
    delete_chain = MagicMock()
    delete_chain.execute = AsyncMock(return_value=MagicMock(data=[]))
    delete_chain.eq = MagicMock(return_value=delete_chain)
    sb.table.return_value.delete.return_value = delete_chain

    # .insert().execute() — async
    insert_chain = MagicMock()
    insert_chain.execute = AsyncMock(return_value=MagicMock(data=[{"id": "new-id"}]))
    sb.table.return_value.insert.return_value = insert_chain

    return sb


@pytest.mark.asyncio
async def test_insert_new_memory_when_llm_returns_preference():
    sb = make_sb(memories=[])

    with patch(
        "services.memory_extractor.ask_llm",
        new=AsyncMock(return_value="Prefers short scripts under 10 minutes"),
    ):
        await extract_memory(sb, "user-1", "approve", "AI trends", "too long")

    sb.table.return_value.insert.assert_called_once_with(
        {
            "user_id": "user-1",
            "content": "Prefers short scripts under 10 minutes",
            "source_action": "approve",
            "source_feedback": "too long",
        }
    )
    sb.table.return_value.insert.return_value.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_when_llm_returns_skip():
    sb = make_sb(memories=[])

    with patch("services.memory_extractor.ask_llm", new=AsyncMock(return_value="SKIP")):
        await extract_memory(sb, "user-1", "approve", "AI trends", "looks good")

    sb.table.return_value.insert.assert_not_called()
    sb.table.return_value.delete.assert_not_called()


@pytest.mark.asyncio
async def test_replace_existing_memory_when_llm_returns_replace():
    existing = [
        {
            "id": "old-id-123",
            "content": "Prefers long scripts",
            "created_at": "2026-01-01",
        }
    ]
    sb = make_sb(memories=existing)

    with patch(
        "services.memory_extractor.ask_llm",
        new=AsyncMock(
            return_value="REPLACE:old-id-123 Prefers scripts under 10 minutes"
        ),
    ):
        await extract_memory(sb, "user-1", "reject", "AI trends", "too long")

    # Should delete old memory
    sb.table.return_value.delete.return_value.eq.assert_called_with("id", "old-id-123")
    sb.table.return_value.delete.return_value.eq.return_value.execute.assert_awaited_once()

    # Should insert new memory
    sb.table.return_value.insert.assert_called_once_with(
        {
            "user_id": "user-1",
            "content": "Prefers scripts under 10 minutes",
            "source_action": "reject",
            "source_feedback": "too long",
        }
    )
    sb.table.return_value.insert.return_value.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_evict_oldest_when_at_memory_cap():
    existing = [
        {"id": f"mem-{i}", "content": f"Memory {i}", "created_at": f"2026-01-{i:02d}"}
        for i in range(1, MAX_MEMORIES + 1)
    ]
    # Oldest is last (ordered by created_at desc)
    oldest = existing[-1]
    sb = make_sb(memories=existing)

    with patch(
        "services.memory_extractor.ask_llm",
        new=AsyncMock(return_value="New preference about pacing"),
    ):
        await extract_memory(sb, "user-1", "approve", "Content strategy", "")

    # Should delete oldest
    sb.table.return_value.delete.return_value.eq.assert_called_with("id", oldest["id"])
    sb.table.return_value.delete.return_value.eq.return_value.execute.assert_awaited_once()

    # Should insert new memory
    sb.table.return_value.insert.assert_called_once_with(
        {
            "user_id": "user-1",
            "content": "New preference about pacing",
            "source_action": "approve",
            "source_feedback": "",
        }
    )
    sb.table.return_value.insert.return_value.execute.assert_awaited_once()
