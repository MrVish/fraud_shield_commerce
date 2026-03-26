import { useState, useCallback } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useActionData, useSubmit, useNavigation } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  Badge,
  DataTable,
  ButtonGroup,
  Button,
  Modal,
  TextField,
  Banner,
  InlineStack,
  Box,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { getOrderDetail, overrideOrder } from "../lib/scoring-api.server";
import type { OrderScore, ScoringSignal } from "../lib/types";

interface LoaderData {
  score: OrderScore | null;
  signals: ScoringSignal[];
  override: Record<string, unknown> | null;
  error: string | null;
}

interface ActionData {
  success?: boolean;
  error?: string;
}

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const orderId = params.orderId;
  if (!orderId) {
    return { score: null, signals: [], override: null, error: "Missing order ID" } satisfies LoaderData;
  }

  try {
    const detail = await getOrderDetail(1, orderId);
    return {
      score: detail.score,
      signals: detail.signals,
      override: detail.override,
      error: null,
    } satisfies LoaderData;
  } catch (e) {
    console.error("[ShieldCommerce] Order detail load error:", e);
    return {
      score: null,
      signals: [],
      override: null,
      error: "Unable to load order details.",
    } satisfies LoaderData;
  }
};

export const action = async ({ request, params }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  const formData = await request.formData();
  const overrideAction = formData.get("action") as string;
  const reason = formData.get("reason") as string;
  const scoreId = parseInt(formData.get("scoreId") as string, 10);

  if (!overrideAction || !reason || isNaN(scoreId)) {
    return { error: "Missing required fields" } satisfies ActionData;
  }

  try {
    await overrideOrder(1, scoreId, overrideAction, reason);
    return { success: true } satisfies ActionData;
  } catch (e) {
    console.error("[ShieldCommerce] Override error:", e);
    return { error: "Failed to override order." } satisfies ActionData;
  }
};

function riskBadgeTone(level: string): "critical" | "warning" | "success" | "attention" {
  switch (level) {
    case "critical": return "critical";
    case "high": return "warning";
    case "medium": return "attention";
    default: return "success";
  }
}

export default function OrderDetail() {
  const { score, signals, override, error } = useLoaderData<LoaderData>();
  const actionData = useActionData<ActionData>();
  const submit = useSubmit();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  const [modalOpen, setModalOpen] = useState(false);
  const [overrideAction, setOverrideAction] = useState("");
  const [reason, setReason] = useState("");

  const handleOverrideClick = useCallback((action: string) => {
    setOverrideAction(action);
    setModalOpen(true);
  }, []);

  const handleModalClose = useCallback(() => {
    setModalOpen(false);
    setOverrideAction("");
    setReason("");
  }, []);

  const handleSubmit = useCallback(() => {
    if (!score) return;
    const formData = new FormData();
    formData.set("action", overrideAction);
    formData.set("reason", reason);
    formData.set("scoreId", String(score.id));
    submit(formData, { method: "POST" });
    handleModalClose();
  }, [score, overrideAction, reason, submit, handleModalClose]);

  if (error && !score) {
    return (
      <Page backAction={{ url: "/app/orders" }} title="Order Detail">
        <Banner tone="critical">
          <p>{error}</p>
        </Banner>
      </Page>
    );
  }

  if (!score) {
    return (
      <Page backAction={{ url: "/app/orders" }} title="Order Detail">
        <Banner tone="warning">
          <p>Order not found.</p>
        </Banner>
      </Page>
    );
  }

  const signalRows = signals.map((signal) => [
    signal.signal_name,
    signal.signal_value,
    String(signal.signal_weight),
    signal.raw_data_json ? JSON.stringify(signal.raw_data_json) : "-",
  ]);

  return (
    <Page
      backAction={{ url: "/app/orders" }}
      title={`Order ${score.shopify_order_id}`}
    >
      <TitleBar title={`Order ${score.shopify_order_id}`} />
      <BlockStack gap="500">
        {actionData?.success && (
          <Banner tone="success">
            <p>Override applied successfully.</p>
          </Banner>
        )}
        {actionData?.error && (
          <Banner tone="critical">
            <p>{actionData.error}</p>
          </Banner>
        )}

        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between">
                  <BlockStack gap="200">
                    <Text as="h2" variant="headingLg">
                      Risk Score
                    </Text>
                    <InlineStack gap="300" blockAlign="center">
                      <Text as="p" variant="heading2xl">
                        {score.risk_score}
                      </Text>
                      <Badge tone={riskBadgeTone(score.risk_level)}>
                        {score.risk_level.toUpperCase()}
                      </Badge>
                    </InlineStack>
                  </BlockStack>
                  <BlockStack gap="200">
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Recommendation
                    </Text>
                    <Text as="p" variant="headingMd">
                      {score.recommendation}
                    </Text>
                  </BlockStack>
                </InlineStack>

                <InlineStack gap="400">
                  <Box>
                    <Text as="p" variant="bodyMd" tone="subdued">Rule Score</Text>
                    <Text as="p" variant="headingMd">{score.rule_score ?? "N/A"}</Text>
                  </Box>
                  <Box>
                    <Text as="p" variant="bodyMd" tone="subdued">ML Score</Text>
                    <Text as="p" variant="headingMd">{score.ml_score ?? "N/A"}</Text>
                  </Box>
                  <Box>
                    <Text as="p" variant="bodyMd" tone="subdued">Scored At</Text>
                    <Text as="p" variant="headingMd">
                      {new Date(score.created_at).toLocaleString()}
                    </Text>
                  </Box>
                </InlineStack>

                {override && (
                  <Banner tone="info">
                    <p>
                      Override applied: {String((override as Record<string, unknown>).action)} - {String((override as Record<string, unknown>).reason)}
                    </p>
                  </Banner>
                )}

                <ButtonGroup>
                  <Button
                    variant="primary"
                    tone="success"
                    onClick={() => handleOverrideClick("approve")}
                    loading={isSubmitting}
                  >
                    Approve
                  </Button>
                  <Button
                    onClick={() => handleOverrideClick("hold")}
                    loading={isSubmitting}
                  >
                    Hold
                  </Button>
                  <Button
                    variant="primary"
                    tone="critical"
                    onClick={() => handleOverrideClick("cancel")}
                    loading={isSubmitting}
                  >
                    Cancel
                  </Button>
                </ButtonGroup>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        <Card>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd">
              Signal Breakdown
            </Text>
            <DataTable
              columnContentTypes={["text", "text", "numeric", "text"]}
              headings={["Signal", "Finding", "Points", "Explanation"]}
              rows={signalRows}
            />
          </BlockStack>
        </Card>

        <Modal
          open={modalOpen}
          onClose={handleModalClose}
          title={`${overrideAction.charAt(0).toUpperCase() + overrideAction.slice(1)} Order`}
          primaryAction={{
            content: "Confirm",
            onAction: handleSubmit,
            loading: isSubmitting,
          }}
          secondaryActions={[
            { content: "Cancel", onAction: handleModalClose },
          ]}
        >
          <Modal.Section>
            <TextField
              label="Reason for override"
              value={reason}
              onChange={setReason}
              multiline={3}
              autoComplete="off"
              placeholder="Explain why you are overriding this recommendation..."
            />
          </Modal.Section>
        </Modal>
      </BlockStack>
    </Page>
  );
}
