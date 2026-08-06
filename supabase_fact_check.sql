insert into public.skills
  (id, title, description, author, filename, type, needs_llm, background, version, min_app_version)
values
  ('fact-check', 'Fact Check', 'Verify a claim using AI analysis', 'Scryptian', 'fact_check.py', 'single', true, false, '1.0.0', '0.5.6')
on conflict (id) do update set
  title = excluded.title,
  description = excluded.description,
  author = excluded.author,
  filename = excluded.filename,
  type = excluded.type,
  needs_llm = excluded.needs_llm,
  background = excluded.background,
  version = excluded.version,
  min_app_version = excluded.min_app_version,
  published = true,
  updated_at = now();
