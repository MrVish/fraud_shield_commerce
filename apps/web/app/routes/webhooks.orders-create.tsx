import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload } = await authenticate.webhook(request);

  const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
  const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

  try {
    const scoringPayload = {
      order_id: String(payload.id),
      merchant_id: 1, // TODO: resolve from shop domain
      email: payload.email || "",
      ip_address: payload.browser_ip || payload.client_details?.browser_ip || "",
      shipping_country: payload.shipping_address?.country_code || "",
      shipping_state: payload.shipping_address?.province_code || "",
      billing_country: payload.billing_address?.country_code || "",
      billing_state: payload.billing_address?.province_code || "",
      order_total: parseFloat(payload.total_price || "0"),
      currency: payload.currency || "USD",
      line_items: (payload.line_items || []).map((item: any) => ({
        title: item.title, quantity: item.quantity, price: item.price,
      })),
      customer_id: String(payload.customer?.id || ""),
      is_first_order: payload.customer?.orders_count === 1,
      phone: payload.phone || payload.billing_address?.phone || "",
      card_brand: payload.payment_details?.credit_card_company || "",
      card_bin: payload.payment_details?.credit_card_bin || "",
      avs_result: payload.payment_details?.avs_result_code || "",
      cvv_result: payload.payment_details?.cvv_result_code || "",
      created_at: payload.created_at || "",
    };

    await fetch(`${SCORING_ENGINE_URL}/api/v1/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": SCORING_API_KEY },
      body: JSON.stringify(scoringPayload),
    });
  } catch (error) {
    console.error(`[ShieldCommerce] Error scoring order ${payload.id}:`, error);
  }

  return new Response("OK", { status: 200 });
};
