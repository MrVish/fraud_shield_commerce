import { useCallback } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useSubmit, useNavigation } from "@remix-run/react";
import {
  Page,
  Card,
  Text,
  BlockStack,
  InlineGrid,
  Button,
  List,
  Badge,
  Banner,
  Box,
  Divider,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import type { PlanTier } from "../lib/types";

interface PlanConfig {
  tier: PlanTier;
  name: string;
  price: number;
  features: string[];
}

const PLANS: PlanConfig[] = [
  {
    tier: "starter",
    name: "Starter",
    price: 29,
    features: [
      "Real-time fraud scoring",
      "Risk signal breakdown",
      "Basic dashboard",
      "Email alerts",
    ],
  },
  {
    tier: "growth",
    name: "Growth",
    price: 69,
    features: [
      "Everything in Starter",
      "Custom scoring rules",
      "Chargeback tracking",
      "Priority support",
    ],
  },
  {
    tier: "pro",
    name: "Pro",
    price: 149,
    features: [
      "Everything in Growth",
      "Advanced analytics",
      "API access",
      "Webhook integrations",
    ],
  },
  {
    tier: "scale",
    name: "Scale",
    price: 249,
    features: [
      "Everything in Pro",
      "Bulk order actions",
      "Data exports",
      "Custom ML model training",
    ],
  },
];

interface LoaderData {
  currentPlan: PlanTier;
}

interface ActionData {
  confirmationUrl?: string;
  error?: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  // TODO: fetch actual plan from merchant record
  return { currentPlan: "starter" as PlanTier } satisfies LoaderData;
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { admin } = await authenticate.admin(request);

  const formData = await request.formData();
  const planTier = formData.get("plan") as PlanTier;
  const planName = formData.get("planName") as string;
  const price = formData.get("price") as string;

  try {
    const response = await admin.graphql(
      `#graphql
      mutation AppSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!) {
        appSubscriptionCreate(
          name: $name
          lineItems: $lineItems
          returnUrl: $returnUrl
          test: true
        ) {
          appSubscription {
            id
          }
          confirmationUrl
          userErrors {
            field
            message
          }
        }
      }`,
      {
        variables: {
          name: `ShieldCommerce ${planName}`,
          returnUrl: `https://${new URL(request.url).host}/app/billing`,
          lineItems: [
            {
              plan: {
                appRecurringPricingDetails: {
                  price: { amount: parseFloat(price), currencyCode: "USD" },
                },
              },
            },
          ],
        },
      },
    );

    const responseJson = await response.json();
    const data = responseJson.data?.appSubscriptionCreate;

    if (data?.userErrors?.length > 0) {
      return { error: data.userErrors.map((e: { message: string }) => e.message).join(", ") } satisfies ActionData;
    }

    if (data?.confirmationUrl) {
      return { confirmationUrl: data.confirmationUrl } satisfies ActionData;
    }

    return { error: "Failed to create subscription." } satisfies ActionData;
  } catch (e) {
    console.error("[ShieldCommerce] Billing error:", e);
    return { error: "Failed to process billing request." } satisfies ActionData;
  }
};

export default function Billing() {
  const { currentPlan } = useLoaderData<LoaderData>();
  const submit = useSubmit();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  const handleSelectPlan = useCallback(
    (plan: PlanConfig) => {
      const formData = new FormData();
      formData.set("plan", plan.tier);
      formData.set("planName", plan.name);
      formData.set("price", String(plan.price));
      submit(formData, { method: "POST" });
    },
    [submit],
  );

  return (
    <Page>
      <TitleBar title="Billing & Plans" />
      <BlockStack gap="500">
        <Banner tone="info">
          <p>
            You are currently on the <strong>{currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)}</strong> plan.
          </p>
        </Banner>

        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          {PLANS.map((plan) => {
            const isCurrent = plan.tier === currentPlan;
            return (
              <Card key={plan.tier}>
                <BlockStack gap="400">
                  <BlockStack gap="200">
                    <InlineGrid columns="1fr auto">
                      <Text as="h2" variant="headingLg">
                        {plan.name}
                      </Text>
                      {isCurrent && <Badge tone="success">Current</Badge>}
                    </InlineGrid>
                    <Text as="p" variant="heading2xl">
                      ${plan.price}
                      <Text as="span" variant="bodyMd" tone="subdued">
                        /mo
                      </Text>
                    </Text>
                  </BlockStack>

                  <Divider />

                  <List>
                    {plan.features.map((feature) => (
                      <List.Item key={feature}>{feature}</List.Item>
                    ))}
                  </List>

                  <Box>
                    {isCurrent ? (
                      <Button disabled fullWidth>
                        Current Plan
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        fullWidth
                        onClick={() => handleSelectPlan(plan)}
                        loading={isSubmitting}
                      >
                        {PLANS.indexOf(plan) > PLANS.findIndex((p) => p.tier === currentPlan)
                          ? "Upgrade"
                          : "Switch"}
                      </Button>
                    )}
                  </Box>
                </BlockStack>
              </Card>
            );
          })}
        </InlineGrid>
      </BlockStack>
    </Page>
  );
}
