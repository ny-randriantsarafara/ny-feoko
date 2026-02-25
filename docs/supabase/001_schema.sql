-- Ambara transcript editor: database schema
-- Run this in the Supabase SQL editor after creating the project.

-- 1) Extraction runs
create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  source text,
  created_at timestamptz not null default now()
);

-- 2) Clips (source of truth)
create table if not exists clips (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references runs(id) on delete cascade,

  file_name text not null,
  source_file text,
  start_sec double precision,
  end_sec double precision,
  duration_sec double precision,

  speech_score double precision,
  music_score double precision,

  draft_transcription text,
  corrected_transcription text,

  status text not null default 'pending'
    check (status in ('pending', 'corrected', 'discarded')),
  priority double precision not null default 0,

  corrected_at timestamptz,
  corrected_by text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (run_id, file_name)
);

-- 3) History log (append-only)
create table if not exists clip_edits (
  id uuid primary key default gen_random_uuid(),
  clip_id uuid not null references clips(id) on delete cascade,

  editor_id text,
  field text not null,
  old_value text,
  new_value text,
  reason text,

  created_at timestamptz not null default now()
);

-- 4) Keep updated_at current
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists clips_set_updated_at on clips;
create trigger clips_set_updated_at
before update on clips
for each row execute function set_updated_at();

-- 5) Indexes for queue queries
create index if not exists clips_run_status_priority_idx
  on clips (run_id, status, priority desc);

create index if not exists clip_edits_clip_created_idx
  on clip_edits (clip_id, created_at desc);
