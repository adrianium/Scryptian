import { defineConfig } from 'astro/config';

// The canonical domain is used for sitemap.xml, canonical URLs and Open Graph.
// Override locally with SITE_URL in site/.env if needed.
const site = process.env.SITE_URL || 'https://scryptian.com';

export default defineConfig({
  site,
  output: 'static',
  trailingSlash: 'always',
});
