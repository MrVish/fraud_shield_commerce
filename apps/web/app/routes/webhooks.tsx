import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload } = await authenticate.webhook(request);

  switch (topic) {
    case "CUSTOMERS_DATA_REQUEST":
      console.log(`[GDPR] Data request for shop ${shop}, customer ${payload.customer?.id}`);
      // TODO: Return stored customer scoring data
      break;
    case "CUSTOMERS_REDACT":
      console.log(`[GDPR] Customer redact for shop ${shop}, customer ${payload.customer?.id}`);
      // TODO: Delete customer-related scoring data from scoring engine
      break;
    case "SHOP_REDACT":
      console.log(`[GDPR] Shop redact for ${shop}`);
      // TODO: Delete all merchant data from scoring engine (48hrs after uninstall)
      break;
    default:
      console.log(`[Webhooks] Received ${topic} for ${shop}`);
  }

  return new Response("OK", { status: 200 });
};
