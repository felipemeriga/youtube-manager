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
                    CHECK (type IN ('text', 'plan', 'approval', 'image', 'save', 'regenerate')),
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
