// paddle_checkout.js — Cloudflare Worker: create a Paddle checkout for Slippers.
//
// The desktop app POSTs { user_id, price_id }, we create a Paddle transaction
// and return the checkout URL to open in the browser.
//
// Setup:
//   1. Deploy this Worker.
//   2. Add secret: PADDLE_API_KEY (live: pdl_live_...)
//   3. Update PRICES below with each price_id you add in Paddle.
//
// Required API key permission: transaction.write

// 1 slipper = 1000 micro-slippers. The wallet balance is stored in micro-slippers,
// so the webhook multiplies the human slipper amount by this scale before crediting.
const SLIPPER_SCALE = 1000;

// Map Paddle price IDs to the number of slippers they grant.
// Paddle prices have no "slippers" field, so we keep the mapping here.
const PRICES = {
  "pri_01m35eacd1ak226p80qe74c5es": 5000,  // $5  -> 5,000 slippers
  "pri_01m35eb4mhvs36qksw814rt1fg": 11000, // $10 -> 11,000 slippers
  "pri_01m35ec7qtnxt3xpxy4w6zvnaq": 23000, // $20 -> 23,000 slippers
  "pri_01m35edejvhf8dk5tpvtrzxk2n": 60000, // $50 -> 60,000 slippers
};

const PADDLE_API_URL = "https://api.paddle.com"; // production (sandbox: https://sandbox-api.paddle.com)

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return json({ error: "Method not allowed" }, 405);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }

    const userId = String(body.user_id || "").trim();
    const priceId = String(body.price_id || "").trim();
    if (!userId) {
      return json({ error: "user_id is required" }, 400);
    }

    const slippers = PRICES[priceId];
    if (!slippers) {
      return json({ error: "Unknown price_id" }, 400);
    }

    const res = await fetch(`${PADDLE_API_URL}/transactions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.PADDLE_API_KEY}`,
      },
      body: JSON.stringify({
        items: [{ price_id: priceId, quantity: 1 }],
        custom_data: {
          user_id: userId,
          slippers: slippers,
        },
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      return json({ error: `Paddle ${res.status}: ${text}` }, 502);
    }

    const data = await res.json();
    const url = data && data.data && data.data.checkout && data.data.checkout.url;
    if (!url) {
      return json({ error: "No checkout URL in Paddle response" }, 502);
    }

    return json({ url });
  },
};
