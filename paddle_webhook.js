// paddle_webhook.js — Cloudflare Worker: Paddle webhook -> Supabase credit_slippers.
//
// Setup:
//   1. Deploy this Worker.
//   2. Add secrets:
//      - PADDLE_WEBHOOK_SECRET     (pdl_ntfset_..., from Notifications in the Paddle dashboard)
//      - SUPABASE_URL              (https://<project>.supabase.co)
//      - SUPABASE_SERVICE_ROLE_KEY
//   3. Paddle Dashboard -> Notifications -> Webhooks -> Add endpoint:
//      https://<your-worker>.workers.dev/webhook
//      Events: transaction.completed
//
// Reuses the existing Supabase function credit_slippers(p_user, p_amount, p_session)
// defined in supabase_wallet.sql. The Paddle transaction id is used as the
// idempotency key (one transaction = one credit).

const SLIPPER_SCALE = 1000;

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

// Paddle signs the payload "ts:rawBody" with HMAC-SHA256.
// Header format: "ts=<unix>;h1=<hex>"
async function verifySignature(rawBody, signature, secret) {
  if (!signature || !secret) return false;

  const parts = signature.split(";").map((p) => p.trim());
  const ts = parts.find((p) => p.startsWith("ts="))?.slice(3);
  const h1 = parts.find((p) => p.startsWith("h1="))?.slice(3);
  if (!ts || !h1) return false;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  return crypto.subtle.verify(
    "HMAC",
    key,
    hexToBytes(h1),
    encoder.encode(`${ts}:${rawBody}`),
  );
}

async function creditSlippers(env, userId, microSlippers, txnId) {
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/credit_slippers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify({ p_user: userId, p_amount: microSlippers, p_session: txnId }),
  });

  if (!res.ok) {
    throw new Error(`Supabase ${res.status}: ${await res.text()}`);
  }
  return res.text();
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const rawBody = await request.text();
    const signature = request.headers.get("paddle-signature") || "";

    const valid = await verifySignature(rawBody, signature, env.PADDLE_WEBHOOK_SECRET);
    if (!valid) {
      return new Response("Invalid signature", { status: 400 });
    }

    let event;
    try {
      event = JSON.parse(rawBody);
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    if (event.event_type === "transaction.completed") {
      const txn = event.data || {};
      const userId = txn.custom_data?.user_id;
      const slippers = txn.custom_data?.slippers;

      if (userId && slippers) {
        const microSlippers = Number(slippers) * SLIPPER_SCALE;
        try {
          const bal = await creditSlippers(env, userId, microSlippers, txn.id);
          console.log("[paddle] credited:", { userId, slippers, bal });
        } catch (e) {
          console.log("[paddle] credit failed:", e.message);
          return new Response(`Credit failed: ${e.message}`, { status: 500 });
        }
      } else {
        console.log("[paddle] skipped: missing custom_data user_id/slippers");
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
