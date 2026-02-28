-- Add paragraphs metadata to clips for unsplit chapter audio.
-- Run this after 004_reading_type.sql in the Supabase SQL editor.
--
-- When non-null, the clip carries the full chapter audio and needs
-- manual splitting in the editor. Each entry has {heading, text}.
-- After splitting, the original clip is deleted and replaced by
-- individual clips with paragraphs = null.

alter table clips
  add column if not exists paragraphs jsonb;
