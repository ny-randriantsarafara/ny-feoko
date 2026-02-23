-- Ambara transcript editor: Storage bucket and policies
-- Run this after 002_rls.sql in the Supabase SQL editor.
--
-- IMPORTANT: First create the bucket manually in the Supabase dashboard:
--   Storage > New bucket > Name: "clips" > Public: OFF

-- Authenticated users can read audio clips
create policy "Authenticated read clips storage"
  on storage.objects for select to authenticated
  using (bucket_id = 'clips');
