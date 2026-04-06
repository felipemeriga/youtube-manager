-- Add mode column to conversations table
-- Values: 'thumbnail' (default, backward compatible) or 'script'
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'thumbnail';
