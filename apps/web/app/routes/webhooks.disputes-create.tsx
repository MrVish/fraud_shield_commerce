import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload } = await authenticate.webhook(request);

  const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
  const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

  try {
    await fetch(`${SCORING_ENGINE_URL}/api/v1/chargebacks`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": SCORING_API_KEY },
      body: JSON.stringify({
        shop_domain: shop,
        shopify_order_id: String(payload.order_id),
        dispute_type: payload.type || "chargeback",
        amount: parseFloat(payload.amount || "0"),
        filed_at: payload.initiated_at || new Date().toISOString(),
      }),
    });
  } catch (error) {
    console.error(`[ShieldCommerce] Error recording chargeback:`, error);
  }

  return new Response("OK", { status: 200 });
};
