-- Background job tracking for the API worker.
-- Run this after 006_paragraphs.sql in the Supabase SQL editor.

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('ingest', 'redraft', 'export')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'done', 'failed')),
  progress integer not null default 0,
  progress_message text,
  params jsonb not null default '{}',
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists jobs_set_updated_at on jobs;
create trigger jobs_set_updated_at
before update on jobs
for each row execute function set_updated_at();

create index if not exists jobs_status_created_idx
  on jobs (status, created_at desc);
