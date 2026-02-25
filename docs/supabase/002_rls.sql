-- Ambara transcript editor: Row Level Security policies
-- Run this after 001_schema.sql in the Supabase SQL editor.

-- Enable RLS on all tables
alter table runs enable row level security;
alter table clips enable row level security;
alter table clip_edits enable row level security;

-- runs: authenticated read-only
create policy "Authenticated read runs"
  on runs for select to authenticated using (true);

-- clips: authenticated read + update
create policy "Authenticated read clips"
  on clips for select to authenticated using (true);

create policy "Authenticated update clip corrections"
  on clips for update to authenticated
  using (true)
  with check (true);

-- clip_edits: authenticated read + insert
create policy "Authenticated read clip_edits"
  on clip_edits for select to authenticated using (true);

create policy "Authenticated insert clip_edits"
  on clip_edits for insert to authenticated
  with check (true);
