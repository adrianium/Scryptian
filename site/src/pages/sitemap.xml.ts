import type { APIRoute } from 'astro';
import { fetchActions } from '../lib/actions';

export const GET: APIRoute = async ({ site }) => {
  const base = (site?.toString() || 'https://scryptian.com').replace(/\/$/, '');
  const actions = await fetchActions();

  const urls = [
    { loc: `${base}/`, priority: '1.0' },
    ...actions.map((a) => ({
      loc: `${base}/actions/${a.id}/`,
      priority: '0.8',
    })),
  ];

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) => `  <url>
    <loc>${u.loc}</loc>
    <priority>${u.priority}</priority>
  </url>`,
  )
  .join('\n')}
</urlset>`;

  return new Response(body, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
