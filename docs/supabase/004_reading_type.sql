-- Add run type to distinguish extraction runs from reading sessions,
-- and RLS policies for the reading feature.
-- Run this after 003_storage.sql in the Supabase SQL editor.

-- 1) Add type column to runs
alter table runs
  add column if not exists type text not null default 'extraction';

alter table runs
  drop constraint if exists runs_type_check;

alter table runs
  add constraint runs_type_check check (type in ('extraction', 'reading'));

-- 2) RLS: allow authenticated users to insert runs and clips
create policy "Authenticated insert runs"
  on runs for insert to authenticated
  with check (true);

create policy "Authenticated insert clips"
  on clips for insert to authenticated
  with check (true);

-- 3) Storage: allow authenticated uploads and overwrites
create policy "Authenticated upload clips storage"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'clips');

create policy "Authenticated overwrite clips storage"
  on storage.objects for update to authenticated
  using (bucket_id = 'clips');
