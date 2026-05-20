-- Pin the image-gen provider per conversation so all artifacts in a single
-- thumbnail conversation share a consistent style. Locked at creation time;
-- changing providers means starting a new conversation.
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS image_provider TEXT DEFAULT 'gemini'
        CHECK (image_provider IN ('gemini', 'openai'));
