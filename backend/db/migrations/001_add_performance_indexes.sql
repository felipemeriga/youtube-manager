-- Performance indexes for vector similarity search and ORDER BY queries
-- Run this migration in the Supabase SQL Editor

-- IVFFLAT indexes for pgvector cosine similarity search.
-- These replace full-table scans with indexed lookups for match_photos()
-- and match_thumbnail_memories() RPC functions.
-- lists=100 is appropriate for tables with <10k rows.
CREATE INDEX IF NOT EXISTS idx_photo_embeddings_embedding
    ON photo_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_thumbnail_memories_embedding
    ON thumbnail_memories
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Sort indexes for ORDER BY queries that currently require full table scans
CREATE INDEX IF NOT EXISTS idx_messages_created_at
    ON messages (created_at);

CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_memories_created_at
    ON user_memories (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_thumbnail_memories_created_at
    ON thumbnail_memories (created_at DESC);
