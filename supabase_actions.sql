-- Recreate the store registry as `actions`.
-- Columns mirror manifest.json (translated to English) plus the minimal
-- store-only fields: id (slug) and published (RLS visibility).

create table if not exists public.actions (
  id text primary key,
  title text not null,
  description text not null default '',
  author text not null default 'Scryptian',
  author_id text,
  price integer not null default 0,
  unit text,
  price_per_unit integer not null default 0,
  min_price integer not null default 0,
  mode text not null default 'cloud',
  entry text not null,
  version text not null default '1.0.0',
  published boolean not null default true,
  long_description text not null default '',
  features text[] not null default '{}',
  demo_gif text,
  runs_count integer not null default 0,
  installs_count integer not null default 0,
  category text,
  tags text[] not null default '{}'
);

alter table public.actions enable row level security;

drop policy if exists "public can read published actions" on public.actions;
create policy "public can read published actions"
on public.actions for select
to anon
using (published = true);

insert into storage.buckets (id, name, public)
values ('actions', 'actions', true)
on conflict (id) do update set public = true;
