-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- conversations
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- messages
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'text'
                    CHECK (type IN ('text', 'plan', 'approval', 'image', 'save', 'regenerate', 'regenerate_composite', 'regenerate_text', 'topics', 'script', 'saved', 'topic_selection', 'background', 'photo_grid', 'composite', 'photo_selected', 'final_thumbnail', 'text_prompt', 'submit_text', 'outline', 'research')),
    image_url       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_select ON conversations
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY conversations_insert ON conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY conversations_update ON conversations
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY conversations_delete ON conversations
    FOR DELETE USING (auth.uid() = user_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_select ON messages
    FOR SELECT USING (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );
CREATE POLICY messages_insert ON messages
    FOR INSERT WITH CHECK (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );
CREATE POLICY messages_delete ON messages
    FOR DELETE USING (
        conversation_id IN (SELECT id FROM conversations WHERE user_id = auth.uid())
    );

-- channel_personas
CREATE TABLE channel_personas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    channel_name TEXT NOT NULL,
    language    TEXT NOT NULL,
    persona_text TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER update_channel_personas_updated_at
    BEFORE UPDATE ON channel_personas
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_channel_personas_user_id ON channel_personas(user_id);

-- RLS
ALTER TABLE channel_personas ENABLE ROW LEVEL SECURITY;

CREATE POLICY channel_personas_select ON channel_personas
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY channel_personas_insert ON channel_personas
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY channel_personas_update ON channel_personas
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY channel_personas_delete ON channel_personas
    FOR DELETE USING (auth.uid() = user_id);

-- user_memories
CREATE TABLE user_memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    source_action   TEXT NOT NULL CHECK (source_action IN ('approved', 'rejected')),
    source_feedback TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_memories_user_id ON user_memories(user_id);

ALTER TABLE user_memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_memories_select ON user_memories
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_memories_delete ON user_memories
    FOR DELETE USING (auth.uid() = user_id);

-- Migration: add script_template to channel_personas
-- ALTER TABLE channel_personas ADD COLUMN script_template JSONB DEFAULT NULL;

-- Migration: add text_style to channel_personas
-- ALTER TABLE channel_personas ADD COLUMN text_style JSONB DEFAULT NULL;

-- Migration: add model to conversations
-- ALTER TABLE conversations ADD COLUMN model TEXT DEFAULT NULL;

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;

-- photo_embeddings
CREATE TABLE photo_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name   TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding   vector(1024),
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, file_name)
);

CREATE INDEX idx_photo_embeddings_user_id ON photo_embeddings(user_id);

-- RPC function for photo similarity search
CREATE OR REPLACE FUNCTION match_photos(
    query_embedding vector(1024),
    match_user_id UUID,
    match_count INT DEFAULT 3
)
RETURNS TABLE (
    file_name TEXT,
    description TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pe.file_name,
        pe.description,
        1 - (pe.embedding <=> query_embedding) AS similarity
    FROM photo_embeddings pe
    WHERE pe.user_id = match_user_id
    ORDER BY pe.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
