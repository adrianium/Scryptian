// Scryptian LLM proxy — Cloudflare Worker
//
// Setup:
//   1. Create a Worker in the Cloudflare dashboard and paste this file.
//   2. Add a secret: OPENROUTER_API_KEY = sk-or-...
//   3. Deploy and call: POST https://<your-worker>.workers.dev/v1/chat/completions
//
// The desktop app talks to this Worker instead of OpenRouter directly, so the
// API key never ships in the app.

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

// The single model used for every request — keeps costs 100% predictable.
const MODEL = "meta-llama/llama-3.3-70b-instruct";

// Fixed-window rate limit (per Worker isolate; approximate for MVP).
const RATE_LIMIT = new Map();

function rateLimit(ip, limit = 30, windowMs = 60_000) {
  const now = Date.now();
  const entry = RATE_LIMIT.get(ip);
  if (!entry || entry.resetAt <= now) {
    RATE_LIMIT.set(ip, { count: 1, resetAt: now + windowMs });
    return true;
  }
  entry.count += 1;
  return entry.count <= limit;
}

function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...cors() },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors() });
    }

    if (request.method !== "POST" || url.pathname !== "/v1/chat/completions") {
      return json({ error: "Not found" }, 404);
    }

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (!rateLimit(ip)) {
      return json({ error: "Rate limit exceeded. Try again later." }, 429);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }

    // Always use the fixed model — ignore whatever the client sends.
    body.model = MODEL;

    // Cap output to avoid runaway bills.
    body.max_tokens = Math.min(body.max_tokens || 1024, 2048);

    const upstream = await fetch(OPENROUTER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "HTTP-Referer": "https://scryptian.app",
        "X-Title": "Scryptian",
      },
      body: JSON.stringify(body),
    });

    // Pass through SSE streaming if requested.
    if (body.stream) {
      return new Response(upstream.body, {
        status: upstream.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          ...cors(),
        },
      });
    }

    const data = await upstream.json();
    return new Response(JSON.stringify(data), {
      status: upstream.status,
      headers: { "Content-Type": "application/json", ...cors() },
    });
  },
};
