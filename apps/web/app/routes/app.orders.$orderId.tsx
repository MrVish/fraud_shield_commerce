import { useState, useCallback } from "react";
import { json } from "@remix-run/node";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useActionData, useSubmit, useNavigation } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  Badge,
  ButtonGroup,
  Button,
  Modal,
  TextField,
  Banner,
  InlineStack,
  Box,
  Divider,
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
  riskSummary: string;
}

interface ActionData {
  success?: boolean;
  error?: string;
}

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const orderId = params.orderId;
  if (!orderId) {
    return json({ score: null, signals: [], override: null, error: "Missing order ID", riskSummary: "" } satisfies LoaderData);
  }

  try {
    const detail = await getOrderDetail(1, orderId);
    const score: OrderScore = {
      id: detail.id,
      shopify_order_id: detail.shopify_order_id,
      risk_score: detail.risk_score ?? 0,
      risk_level: detail.risk_level ?? "low",
      signals_json: detail.signals_json ?? {},
      recommendation: detail.recommendation ?? "review",
      rule_score: detail.rule_score ?? null,
      ml_score: detail.ml_score ?? null,
      created_at: detail.created_at ?? new Date().toISOString(),
      risk_summary: (detail as any).risk_summary ?? "",
    };
    return json({
      score,
      signals: (detail.signals ?? []).map((s) => ({
        signal_name: s.name ?? "",
        signal_value: s.value ?? "",
        signal_weight: s.weight ?? 0,
        raw_data_json: s.raw_data ?? null,
      })),
      override: detail.override ?? null,
      error: null,
      riskSummary: (detail as any).risk_summary ?? "",
    } satisfies LoaderData);
  } catch (e) {
    console.error("[ShieldCommerce] Order detail load error:", e);
    return json({
      score: null,
      signals: [],
      override: null,
      error: "Unable to load order details.",
      riskSummary: "",
    } satisfies LoaderData);
  }
};

export const action = async ({ request, params }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  const formData = await request.formData();
  const overrideAction = formData.get("action") as string;
  const reason = formData.get("reason") as string;
  const scoreId = parseInt(formData.get("scoreId") as string, 10);

  if (!overrideAction || !reason || isNaN(scoreId)) {
    return json({ error: "Missing required fields" } satisfies ActionData);
  }

  try {
    await overrideOrder(1, scoreId, overrideAction, reason);
    return json({ success: true } satisfies ActionData);
  } catch (e) {
    console.error("[ShieldCommerce] Override error:", e);
    return json({ error: "Failed to override order." } satisfies ActionData);
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

function getScoreColor(score: number): string {
  if (score <= 30) return "#22C55E";
  if (score <= 60) return "#F59E0B";
  if (score <= 80) return "#EF4444";
  return "#991B1B";
}

function getScoreBgColor(score: number): string {
  if (score <= 30) return "#F0FDF4";
  if (score <= 60) return "#FFFBEB";
  if (score <= 80) return "#FEF2F2";
  return "#FEF2F2";
}

// Signal categories
const SIGNAL_CATEGORIES: Record<string, string[]> = {
  Payment: ["payment_method", "card_bin", "card_country", "avs_result", "cvv_result", "payment_velocity"],
  Behavioral: ["session_duration", "page_views", "checkout_speed", "time_on_site", "mouse_movement"],
  Geographic: ["ip_country", "shipping_country", "billing_country", "ip_proxy", "geo_mismatch", "distance"],
  "Order Pattern": ["order_amount", "order_velocity", "item_quantity", "discount_abuse", "gift_card", "repeat_customer"],
  "Digital Footprint": ["email_domain", "email_age", "phone_valid", "device_fingerprint", "browser_language"],
};

function categorizeSignal(signalName: string): string {
  for (const [category, signals] of Object.entries(SIGNAL_CATEGORIES)) {
    if (signals.some((s) => signalName.toLowerCase().includes(s.replace("_", "")) || signalName.toLowerCase().includes(s))) {
      return category;
    }
  }
  // Fallback: try to match partial keywords
  const name = signalName.toLowerCase();
  if (name.includes("pay") || name.includes("card") || name.includes("avs") || name.includes("cvv")) return "Payment";
  if (name.includes("ip") || name.includes("geo") || name.includes("country") || name.includes("distance")) return "Geographic";
  if (name.includes("email") || name.includes("phone") || name.includes("device") || name.includes("browser")) return "Digital Footprint";
  if (name.includes("amount") || name.includes("velocity") || name.includes("quantity") || name.includes("order")) return "Order Pattern";
  if (name.includes("session") || name.includes("page") || name.includes("checkout") || name.includes("mouse")) return "Behavioral";
  return "Other";
}

function ScoreCircle({ score, size = 140 }: { score: number; size?: number }) {
  const color = getScoreColor(score);
  const bgColor = getScoreBgColor(score);
  const circumference = 2 * Math.PI * 54;
  const progress = (score / 100) * circumference;

  return (
    <div
      style={{
        position: "relative",
        width: `${size}px`,
        height: `${size}px`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg width={size} height={size} viewBox="0 0 120 120">
        {/* Background circle */}
        <circle
          cx="60"
          cy="60"
          r="54"
          fill={bgColor}
          stroke="#E2E8F0"
          strokeWidth="8"
        />
        {/* Progress circle */}
        <circle
          cx="60"
          cy="60"
          r="54"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference - progress}`}
          transform="rotate(-90 60 60)"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: "32px", fontWeight: 700, color, lineHeight: 1 }}>
          {score}
        </div>
        <div style={{ fontSize: "11px", color: "#64748B", marginTop: "2px" }}>
          / 100
        </div>
      </div>
    </div>
  );
}

function SignalBar({
  signal,
  maxWeight,
}: {
  signal: ScoringSignal;
  maxWeight: number;
}) {
  const hasPoints = signal.signal_weight > 0;
  const barColor = hasPoints ? "#EF4444" : "#22C55E";
  const barBg = hasPoints ? "#FEE2E2" : "#DCFCE7";
  const widthPct = maxWeight > 0 ? Math.max((signal.signal_weight / maxWeight) * 100, 4) : 4;

  return (
    <div
      style={{
        padding: "12px 16px",
        borderBottom: "1px solid #F1F5F9",
      }}
    >
      <InlineStack align="space-between" blockAlign="start">
        <div style={{ flex: 1 }}>
          <Text as="p" variant="bodyMd" fontWeight="semibold">
            {signal.signal_name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </Text>
          <div style={{ marginTop: "6px" }}>
            <div
              style={{
                width: "100%",
                height: "8px",
                backgroundColor: barBg,
                borderRadius: "4px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${widthPct}%`,
                  height: "100%",
                  backgroundColor: barColor,
                  borderRadius: "4px",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          </div>
          {signal.signal_value && (
            <div style={{ marginTop: "4px" }}>
              <Text as="p" variant="bodySm" tone="subdued">
                {signal.signal_value}
              </Text>
            </div>
          )}
        </div>
        <div
          style={{
            minWidth: "60px",
            textAlign: "right",
            paddingLeft: "12px",
          }}
        >
          <Text as="p" variant="bodyMd" fontWeight="semibold">
            {hasPoints ? `+${signal.signal_weight}` : "0"}
          </Text>
          <Text as="p" variant="bodySm" tone="subdued">
            pts
          </Text>
        </div>
      </InlineStack>
    </div>
  );
}

function ScoreCompositionBar({
  ruleScore,
  mlScore,
  finalScore,
}: {
  ruleScore: number | null;
  mlScore: number | null;
  finalScore: number;
}) {
  const rs = ruleScore ?? 0;
  const ms = mlScore ?? 0;
  const total = rs + ms || 1;
  const rsPct = (rs / total) * 100;
  const msPct = (ms / total) * 100;

  return (
    <div>
      <InlineStack gap="400" blockAlign="center">
        <div style={{ textAlign: "center", flex: 1 }}>
          <Text as="p" variant="bodySm" tone="subdued">Rule Score</Text>
          <Text as="p" variant="headingLg">{ruleScore ?? "N/A"}</Text>
        </div>
        <div style={{ fontSize: "20px", color: "#CBD5E1" }}>+</div>
        <div style={{ textAlign: "center", flex: 1 }}>
          <Text as="p" variant="bodySm" tone="subdued">ML Score</Text>
          <Text as="p" variant="headingLg">{mlScore ?? "N/A"}</Text>
        </div>
        <div style={{ fontSize: "20px", color: "#CBD5E1" }}>=</div>
        <div style={{ textAlign: "center", flex: 1 }}>
          <Text as="p" variant="bodySm" tone="subdued">Final Score</Text>
          <Text as="p" variant="headingLg" fontWeight="bold">
            {finalScore}
          </Text>
        </div>
      </InlineStack>
      <div style={{ marginTop: "12px" }}>
        <div
          style={{
            display: "flex",
            width: "100%",
            height: "10px",
            borderRadius: "5px",
            overflow: "hidden",
            backgroundColor: "#E2E8F0",
          }}
        >
          {ruleScore !== null && (
            <div
              style={{
                width: `${rsPct}%`,
                backgroundColor: "#3B82F6",
                transition: "width 0.3s",
              }}
            />
          )}
          {mlScore !== null && (
            <div
              style={{
                width: `${msPct}%`,
                backgroundColor: "#8B5CF6",
                transition: "width 0.3s",
              }}
            />
          )}
        </div>
        <InlineStack align="space-between">
          <Text as="p" variant="bodySm" tone="subdued">
            <span style={{ color: "#3B82F6" }}>&#9632;</span> Rules
          </Text>
          <Text as="p" variant="bodySm" tone="subdued">
            <span style={{ color: "#8B5CF6" }}>&#9632;</span> ML Model
          </Text>
        </InlineStack>
      </div>
    </div>
  );
}

export default function OrderDetail() {
  const { score, signals, override, error, riskSummary } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
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

  // Group signals by category
  const maxWeight = Math.max(...signals.map((s) => s.signal_weight), 1);
  const groupedSignals: Record<string, ScoringSignal[]> = {};
  for (const signal of signals) {
    const cat = categorizeSignal(signal.signal_name);
    if (!groupedSignals[cat]) groupedSignals[cat] = [];
    groupedSignals[cat].push(signal);
  }

  // Sort categories to show ones with positive weights first
  const sortedCategories = Object.entries(groupedSignals).sort(([, a], [, b]) => {
    const aMax = Math.max(...a.map((s) => s.signal_weight));
    const bMax = Math.max(...b.map((s) => s.signal_weight));
    return bMax - aMax;
  });

  const totalSignalPoints = signals.reduce((sum, s) => sum + s.signal_weight, 0);

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

        {/* Risk Summary Banner */}
        {riskSummary && (
          <Card>
            <BlockStack gap="200">
              <InlineStack gap="200" blockAlign="center">
                <div style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: score.risk_level === "critical" ? "#991B1B" : score.risk_level === "high" ? "#EF4444" : score.risk_level === "medium" ? "#F59E0B" : "#22C55E",
                  flexShrink: 0,
                }} />
                <Text as="h2" variant="headingMd">Risk Summary</Text>
              </InlineStack>
              <Text as="p" variant="bodyMd">
                {riskSummary}
              </Text>
            </BlockStack>
          </Card>
        )}

        <Layout>
          {/* Score Hero */}
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <div style={{ display: "flex", justifyContent: "center", paddingTop: "8px" }}>
                  <ScoreCircle score={score.risk_score} size={160} />
                </div>
                <div style={{ textAlign: "center" }}>
                  <Badge tone={riskBadgeTone(score.risk_level)} size="large">
                    {score.risk_level.toUpperCase()} RISK
                  </Badge>
                </div>
                <Divider />
                <div style={{ textAlign: "center" }}>
                  <Text as="p" variant="bodySm" tone="subdued">Recommendation</Text>
                  <div style={{ marginTop: "4px" }}>
                    <Text as="p" variant="headingMd">
                      {score.recommendation}
                    </Text>
                  </div>
                </div>
                <Divider />
                <div style={{ textAlign: "center" }}>
                  <Text as="p" variant="bodySm" tone="subdued">Scored At</Text>
                  <Text as="p" variant="bodyMd">
                    {new Date(score.created_at).toLocaleString()}
                  </Text>
                </div>
              </BlockStack>
            </Card>
          </Layout.Section>

          {/* Score Composition & Actions */}
          <Layout.Section>
            <BlockStack gap="400">
              <Card>
                <BlockStack gap="400">
                  <Text as="h2" variant="headingMd">Score Composition</Text>
                  <ScoreCompositionBar
                    ruleScore={score.rule_score}
                    mlScore={score.ml_score}
                    finalScore={score.risk_score}
                  />
                </BlockStack>
              </Card>

              {override && (
                <Banner tone="info">
                  <p>
                    Override applied: {String((override as Record<string, unknown>).action)} - {String((override as Record<string, unknown>).reason)}
                  </p>
                </Banner>
              )}

              <Card>
                <BlockStack gap="300">
                  <Text as="h2" variant="headingMd">Actions</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Override the automated recommendation for this order
                  </Text>
                  <InlineStack gap="300">
                    <Button
                      variant="primary"
                      tone="success"
                      onClick={() => handleOverrideClick("approve")}
                      loading={isSubmitting}
                      size="large"
                    >
                      Approve Order
                    </Button>
                    <Button
                      onClick={() => handleOverrideClick("hold")}
                      loading={isSubmitting}
                      size="large"
                    >
                      Hold for Review
                    </Button>
                    <Button
                      variant="primary"
                      tone="critical"
                      onClick={() => handleOverrideClick("cancel")}
                      loading={isSubmitting}
                      size="large"
                    >
                      Cancel Order
                    </Button>
                  </InlineStack>
                </BlockStack>
              </Card>
            </BlockStack>
          </Layout.Section>
        </Layout>

        {/* Signal Breakdown */}
        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h2" variant="headingMd">Signal Breakdown</Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {signals.length} signals, {totalSignalPoints} total points
              </Text>
            </InlineStack>

            {sortedCategories.map(([category, categorySignals]) => {
              const categoryPoints = categorySignals.reduce((s, sig) => s + sig.signal_weight, 0);
              const maxCatWeight = categorySignals.reduce((s, sig) => s + Math.max(sig.signal_weight, sig.raw_data_json?.max_weight ?? sig.signal_weight, 5), 0);
              return (
                <div key={category}>
                  <div
                    style={{
                      backgroundColor: "#F8FAFC",
                      padding: "10px 16px",
                      borderRadius: "6px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Text as="p" variant="headingSm">{category}</Text>
                    <InlineStack gap="200" blockAlign="center">
                      {/* Mini progress bar for category */}
                      <div style={{
                        width: "60px", height: "6px", backgroundColor: "#E2E8F0",
                        borderRadius: "3px", overflow: "hidden"
                      }}>
                        <div style={{
                          width: `${maxCatWeight > 0 ? Math.min((categoryPoints / maxCatWeight) * 100, 100) : 0}%`,
                          height: "100%",
                          backgroundColor: categoryPoints > 0 ? "#EF4444" : "#22C55E",
                          borderRadius: "3px",
                        }} />
                      </div>
                      <Text as="p" variant="bodySm" fontWeight="semibold">
                        {categoryPoints > 0 ? `+${categoryPoints}` : "0"} pts
                      </Text>
                    </InlineStack>
                  </div>
                  {categorySignals
                    .sort((a, b) => b.signal_weight - a.signal_weight)
                    .map((signal, idx) => (
                      <SignalBar
                        key={`${category}-${idx}`}
                        signal={signal}
                        maxWeight={maxWeight}
                      />
                    ))}
                </div>
              );
            })}
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
