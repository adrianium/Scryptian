-- Add SEO / marketplace fields to the existing `actions` table.
-- Safe to run multiple times (uses `if not exists`).

alter table public.actions
  add column if not exists long_description text not null default '',
  add column if not exists features text[] not null default '{}',
  add column if not exists demo_gif text,
  add column if not exists runs_count integer not null default 0,
  add column if not exists installs_count integer not null default 0,
  add column if not exists category text,
  add column if not exists tags text[] not null default '{}',
  add column if not exists unit text,
  add column if not exists price_per_unit integer not null default 0,
  add column if not exists min_price integer not null default 0;
