// Build-time data layer: fetch published actions from the public Supabase REST API.

export interface Action {
  id: string;
  title: string;
  description: string;
  author: string;
  author_id: string | null;
  price: number;
  unit: string | null;
  price_per_unit: number;
  mode: string;
  entry: string;
  version: string;
  published: boolean;
  long_description: string;
  features: string[];
  demo_gif: string | null;
  runs_count: number;
  installs_count: number;
  category: string | null;
  tags: string[];
}

const SUPABASE_URL = (import.meta.env.SUPABASE_URL || '').replace(/\/$/, '');
const SUPABASE_ANON_KEY = import.meta.env.SUPABASE_ANON_KEY || '';

export function isConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

export async function fetchActions(): Promise<Action[]> {
  if (!isConfigured()) {
    return [];
  }

  const url = `${SUPABASE_URL}/rest/v1/actions?select=*&published=eq.true&order=title.asc`;
  try {
    const res = await fetch(url, {
      headers: {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      console.error(`[scryptian-web] Failed to fetch actions: ${res.status} ${res.statusText}`);
      return [];
    }

    const data = (await res.json()) as Action[];
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.error('[scryptian-web] Error fetching actions:', err);
    return [];
  }
}

export function isFree(action: Action): boolean {
  return (!action.price || action.price <= 0) && (!action.price_per_unit || action.price_per_unit <= 0);
}

const SLIPPER_SCALE = 1000;

function formatSlippers(micro: number): string {
  if (micro % SLIPPER_SCALE === 0) return String(micro / SLIPPER_SCALE);
  return (micro / SLIPPER_SCALE).toFixed(2).replace(/\.?0+$/, '');
}

function usd(micro: number): string {
  const d = micro / 1000000;
  if (d >= 0.001) return '$' + d.toFixed(3).replace(/\.?0+$/, '');
  return '<$0.001';
}

export function formatPrice(action: Action): string {
  const ppu = Number(action.price_per_unit || 0);
  const unit = (action.unit || '').trim();
  if (ppu > 0 && unit) {
    return `${formatSlippers(ppu)} slippers / ${unit} (~${usd(ppu)})`;
  }
  const price = Number(action.price || 0);
  if (price > 0) {
    return `${formatSlippers(price)} slippers (~${usd(price)})`;
  }
  return 'Free';
}

export function modeLabel(action: Action): string {
  return (action.mode || 'cloud').trim().toLowerCase() === 'local' ? 'Local' : 'Cloud';
}

export function installUrl(action: Action): string {
  return `scryptian://install/${encodeURIComponent(action.id)}`;
}

export function formatCount(n: number): string {
  if (!n || n <= 0) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}
