# Scryptian Web — Actions Marketplace

Static Astro site that generates a landing page for every published action
from the Supabase `actions` table.

## Setup

```bash
cd site
npm install
cp .env.example .env   # fill SUPABASE_URL and SUPABASE_ANON_KEY
```

## Develop

```bash
npm run dev
```

## Build (static)

```bash
npm run build
npm run preview
```

The build output goes to `site/dist/` and is ready to deploy to Cloudflare Pages.

## How it works

- `src/lib/actions.ts` fetches published actions from Supabase at build time.
- `src/pages/actions/[slug].astro` generates one SEO landing page per action
  (title, meta description, canonical, Open Graph, `SoftwareApplication` schema).
- `src/pages/sitemap.xml.ts` and `src/pages/robots.txt.ts` are generated from
  the same action list.

## Environment variables

| Variable | Description |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase public anon key |
| `SITE_URL` | Canonical domain (default `https://scryptian.com`) |

## Install deep link

The install button uses `scryptian://install/<id>`. The desktop app needs to
register this custom protocol to handle it.
