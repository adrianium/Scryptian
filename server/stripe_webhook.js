// stripe_webhook.js — Cloudflare Worker: Stripe webhook → Supabase credit_slippers.
//
// Setup:
//   1. Deploy this Worker.
//   2. Add secrets/vars:
//      - STRIPE_WEBHOOK_SECRET      (whsec_...)
//      - SUPABASE_URL               (https://<project>.supabase.co)
//      - SUPABASE_SERVICE_ROLE_KEY
//   3. Stripe Dashboard → Developers → Webhooks → Add endpoint:
//      https://<your-worker>.workers.dev/webhook
//      Events: checkout.session.completed
//   4. The app opens the Payment Link with ?client_reference_id=<user_id>.

async function verifyStripeEvent(request, secret) {
  const signature = request.headers.get("stripe-signature");
  if (!signature || !secret) return null;

  const payload = await request.text();

  const parts = signature.split(",").map((p) => p.trim());
  const ts = parts.find((p) => p.startsWith("t="))?.slice(2);
  const v1 = parts.find((p) => p.startsWith("v1="))?.slice(3);
  if (!ts || !v1) return null;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  const signedPayload = `${ts}.${payload}`;
  const valid = await crypto.subtle.verify(
    "HMAC",
    key,
    hexToBytes(v1),
    encoder.encode(signedPayload),
  );
  if (!valid) return null;

  return JSON.parse(payload);
}

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

async function creditSlippers(env, userId, amountCents, sessionId) {
  // 1 dollar = 1000 slippers, and Stripe amounts are in cents → 1 cent = 10 slippers.
  const slippers = amountCents * 10;

  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/credit_slippers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify({ p_user: userId, p_amount: slippers, p_session: sessionId }),
  });

  if (!res.ok) {
    throw new Error(`Supabase ${res.status}: ${await res.text()}`);
  }
  return res.text();
}

export default {
  async fetch(request, env) {
    console.log(`[webhook] ${request.method} ${request.url}`);

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let event;
    try {
      event = await verifyStripeEvent(request, env.STRIPE_WEBHOOK_SECRET);
    } catch (e) {
      console.log("[webhook] body parse error:", e.message);
      return new Response("Bad request", { status: 400 });
    }
    if (!event) {
      console.log("[webhook] invalid signature (secret set:", !!env.STRIPE_WEBHOOK_SECRET, ")");
      return new Response("Invalid signature", { status: 400 });
    }

    console.log("[webhook] event type:", event.type);

    if (event.type === "checkout.session.completed") {
      const session = event.data.object;
      console.log("[webhook] session:", {
        id: session.id,
        payment_status: session.payment_status,
        client_reference_id: session.client_reference_id,
        amount_total: session.amount_total,
      });

      if (session.payment_status === "paid") {
        const userId = session.client_reference_id;
        const amountCents = session.amount_total || 0;
        const sessionId = session.id;
        if (userId && amountCents > 0) {
          try {
            const bal = await creditSlippers(env, userId, amountCents, sessionId);
            console.log("[webhook] credited:", { userId, amountCents, bal });
          } catch (e) {
            console.log("[webhook] credit failed:", e.message);
            return new Response(`Credit failed: ${e.message}`, { status: 500 });
          }
        } else {
          console.log("[webhook] skipped: missing client_reference_id or amount");
        }
      } else {
        console.log("[webhook] skipped: payment_status =", session.payment_status);
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
