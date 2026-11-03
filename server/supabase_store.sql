create table if not exists public.skills (
  id text primary key,
  title text not null,
  description text not null default '',
  author text not null default 'Scryptian',
  filename text not null,
  type text not null default 'single',
  archive text,
  storage_path text,
  download_url text,
  version text,
  min_app_version text,
  needs_llm boolean not null default true,
  background boolean not null default false,
  settings jsonb not null default '[]'::jsonb,
  published boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.skills enable row level security;

drop policy if exists "public can read published skills" on public.skills;
create policy "public can read published skills"
on public.skills for select
to anon
using (published = true);

insert into storage.buckets (id, name, public)
values ('skills', 'skills', true)
on conflict (id) do update set public = true;

insert into public.skills
  (id, title, description, author, filename, type, archive, storage_path, version, min_app_version, needs_llm, background)
values
  ('translate-ru', 'Translate to Russian', 'Translate text to Russian (Google Translate)', 'Scryptian', 'translate_ru.py', 'single', null, 'translate_ru.py', '1.0.0', '0.5.1', false, false),
  ('translate-es', 'Translate to Spanish', 'Translate text to Spanish (Google Translate)', 'Scryptian', 'translate_es.py', 'single', null, 'translate_es.py', '1.0.0', '0.5.1', false, false),
  ('translate-de', 'Translate to German', 'Translate text to German (Google Translate)', 'Scryptian', 'translate_de.py', 'single', null, 'translate_de.py', '1.0.0', '0.5.1', false, false),
  ('translate-fr', 'Translate to French', 'Translate text to French (Google Translate)', 'Scryptian', 'translate_fr.py', 'single', null, 'translate_fr.py', '1.0.0', '0.5.1', false, false),
  ('translate-zh', 'Translate to Chinese', 'Translate text to Chinese (Google Translate)', 'Scryptian', 'translate_zh.py', 'single', null, 'translate_zh.py', '1.0.0', '0.5.1', false, false),
  ('translate-pdf', 'Translate PDF file', 'Pick a PDF, choose a language, and save a translated copy', 'Scryptian', 'translate_pdf', 'bundle', 'translate_pdf.zip', 'translate_pdf.zip', '1.8.1', '0.5.1', false, true),
  ('wikipedia', 'Wikipedia', 'Select a word or topic and get a clean Wikipedia summary', 'Scryptian', 'wikipedia', 'bundle', 'wikipedia.zip', 'wikipedia.zip', '1.1.0', '0.5.1', false, false)
on conflict (id) do update set
  title = excluded.title,
  description = excluded.description,
  author = excluded.author,
  filename = excluded.filename,
  type = excluded.type,
  archive = excluded.archive,
  storage_path = excluded.storage_path,
  version = excluded.version,
  min_app_version = excluded.min_app_version,
  needs_llm = excluded.needs_llm,
  background = excluded.background,
  published = true,
  updated_at = now();
