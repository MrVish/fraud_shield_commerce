import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useNavigate } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  InlineGrid,
  InlineStack,
  Box,
  Banner,
  Badge,
  Divider,
  Link,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ComposedChart,
  Line,
  Legend,
} from "recharts";
import { authenticate } from "../shopify.server";
import { getDashboardStats, getOrderScores } from "../lib/scoring-api.server";
import type { DashboardStats, OrderScore } from "../lib/types";

interface LoaderData {
  stats: DashboardStats | null;
  recentFlagged: OrderScore[];
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  try {
    const [stats, highOrders, criticalOrders] = await Promise.all([
      getDashboardStats(1, 30),
      getOrderScores(1, 1, 5, "high"),
      getOrderScores(1, 1, 5, "critical"),
    ]);

    const recentFlagged = [
      ...(criticalOrders.orders ?? []),
      ...(highOrders.orders ?? []),
    ]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);

    return json({ stats, recentFlagged, error: null } satisfies LoaderData);
  } catch (e) {
    console.error("[ShieldCommerce] Dashboard load error:", e);
    return json({
      stats: null,
      recentFlagged: [],
      error: "Unable to connect to scoring engine. Showing empty dashboard.",
    } satisfies LoaderData);
  }
};

const emptyStats: DashboardStats = {
  total_orders: 0,
  flagged_orders: 0,
  avg_score: 0,
  chargeback_count: 0,
  chargeback_amount: 0,
  score_distribution: [],
  trend_data: [],
  revenue_protected: 0,
  chargeback_rate: 0,
  chargeback_health: "good",
};

function getScoreBarColor(label: string): string {
  if (label.startsWith("0") || label.startsWith("1") || label.startsWith("2")) return "#22C55E";
  if (label.startsWith("3") || label.startsWith("4") || label.startsWith("5")) return "#F59E0B";
  if (label.startsWith("6") || label.startsWith("7")) return "#EF4444";
  return "#991B1B";
}

function riskBadgeTone(level: string): "critical" | "warning" | "success" | "attention" {
  switch (level) {
    case "critical": return "critical";
    case "high": return "warning";
    case "medium": return "attention";
    default: return "success";
  }
}

function getRiskDotColor(level: string): string {
  switch (level) {
    case "critical": return "#991B1B";
    case "high": return "#EF4444";
    case "medium": return "#F59E0B";
    default: return "#22C55E";
  }
}

function KpiCard({
  title,
  value,
  subtitle,
  borderColor,
  bgTint,
  trend,
}: {
  title: string;
  value: string;
  subtitle?: string;
  borderColor: string;
  bgTint?: string;
  trend?: string;
}) {
  return (
    <div
      style={{
        borderLeft: `4px solid ${borderColor}`,
        backgroundColor: bgTint || "#FFFFFF",
        borderRadius: "12px",
        padding: "16px 20px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        minHeight: "100px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
      }}
    >
      <Text as="p" variant="bodySm" tone="subdued">
        {title}
      </Text>
      <div style={{ marginTop: "4px" }}>
        <Text as="p" variant="heading2xl">
          {value}
        </Text>
      </div>
      {subtitle && (
        <div style={{ marginTop: "2px" }}>
          <Text as="p" variant="bodySm" tone="subdued">
            {subtitle}
          </Text>
        </div>
      )}
      {trend && (
        <div style={{ marginTop: "4px" }}>
          <Text as="p" variant="bodySm" tone="subdued">
            {trend}
          </Text>
        </div>
      )}
    </div>
  );
}

// Custom tooltip for the score distribution chart
function ScoreDistTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E4E5E7",
        borderRadius: "8px",
        padding: "8px 12px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      }}
    >
      <Text as="p" variant="bodySm" fontWeight="semibold">
        Score Range: {label}
      </Text>
      <Text as="p" variant="bodySm">
        {payload[0].value} orders
      </Text>
    </div>
  );
}

// Custom label on bars
function BarLabel({ x, y, width, value }: any) {
  if (!value) return null;
  return (
    <text
      x={x + width / 2}
      y={y - 6}
      fill="#64748B"
      textAnchor="middle"
      fontSize={12}
      fontWeight={600}
    >
      {value}
    </text>
  );
}

export default function Dashboard() {
  const { stats: rawStats, recentFlagged, error } = useLoaderData<typeof loader>();
  const stats = { ...emptyStats, ...(rawStats ?? {}) };
  const navigate = useNavigate();

  const flaggedPct =
    stats.total_orders > 0
      ? ((stats.flagged_orders / stats.total_orders) * 100).toFixed(1)
      : "0";

  // Count flagged by level from recent data
  const criticalCount = recentFlagged.filter((o) => o.risk_level === "critical").length;
  const highCount = recentFlagged.filter((o) => o.risk_level === "high").length;

  return (
    <Page>
      <TitleBar title="ShieldCommerce Dashboard" />
      <BlockStack gap="500">
        {error && (
          <Banner tone="warning">
            <p>{error}</p>
          </Banner>
        )}

        {/* KPI Cards */}
        <InlineGrid columns={{ xs: 1, sm: 2, md: 3 }} gap="400">
          <KpiCard
            title="Total Orders (30d)"
            value={stats.total_orders.toLocaleString()}
            borderColor="#3B82F6"
            trend="vs last period"
          />
          <KpiCard
            title="Flagged Orders"
            value={stats.flagged_orders.toLocaleString()}
            subtitle={`${flaggedPct}% of total`}
            borderColor="#EF4444"
            bgTint="#FEF2F2"
          />
          <KpiCard
            title="Avg Risk Score"
            value={stats.avg_score.toFixed(1)}
            subtitle={stats.avg_score > 50 ? "Above threshold" : "Within safe range"}
            borderColor={stats.avg_score > 50 ? "#F59E0B" : "#22C55E"}
          />
        </InlineGrid>

        <InlineGrid columns={{ xs: 1, sm: 2, md: 3 }} gap="400">
          <KpiCard
            title="Revenue Protected"
            value={`$${(stats.revenue_protected || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle="High/critical risk orders caught"
            borderColor="#22C55E"
            bgTint="#F0FDF4"
          />
          <div
            style={{
              borderLeft: `4px solid ${stats.chargeback_health === "good" ? "#22C55E" : stats.chargeback_health === "at_risk" ? "#F59E0B" : "#EF4444"}`,
              backgroundColor: stats.chargeback_count > 0 ? "#FFFBEB" : "#FFFFFF",
              borderRadius: "12px",
              padding: "16px 20px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
              minHeight: "100px",
              display: "flex",
              flexDirection: "column" as const,
              justifyContent: "center",
            }}
          >
            <Text as="p" variant="bodySm" tone="subdued">
              Chargebacks
            </Text>
            <div style={{ marginTop: "4px", display: "flex", alignItems: "center", gap: "8px" }}>
              <Text as="p" variant="heading2xl">
                {String(stats.chargeback_count)}
              </Text>
              <span style={{
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: "12px",
                fontSize: "11px",
                fontWeight: 600,
                backgroundColor: stats.chargeback_health === "good" ? "#DCFCE7" : stats.chargeback_health === "at_risk" ? "#FEF9C3" : "#FEE2E2",
                color: stats.chargeback_health === "good" ? "#166534" : stats.chargeback_health === "at_risk" ? "#854D0E" : "#991B1B",
              }}>
                {stats.chargeback_health === "good" ? "Good Standing" : stats.chargeback_health === "at_risk" ? "At Risk" : "Elevated Risk"}
              </span>
            </div>
            <div style={{ marginTop: "2px" }}>
              <Text as="p" variant="bodySm" tone="subdued">
                {stats.chargeback_rate.toFixed(2)}% rate | ${stats.chargeback_amount.toFixed(2)} total
              </Text>
            </div>
          </div>
          <KpiCard
            title="Chargeback Amount"
            value={`$${stats.chargeback_amount.toFixed(2)}`}
            subtitle={stats.chargeback_count > 0 ? `${stats.chargeback_count} disputes filed` : "No disputes"}
            borderColor="#F59E0B"
            bgTint={stats.chargeback_count > 0 ? "#FFFBEB" : undefined}
          />
        </InlineGrid>

        {/* Risk Summary Banner */}
        {stats.flagged_orders > 0 && (
          <Banner tone="warning" title={`${stats.flagged_orders} orders need review`}>
            <p>
              {criticalCount > 0 && `${criticalCount} Critical`}
              {criticalCount > 0 && highCount > 0 && ", "}
              {highCount > 0 && `${highCount} High`}
              {criticalCount === 0 && highCount === 0 && "Orders flagged in the last 30 days"}
              {" "}
              -- <Link url="/app/orders?risk_level=high">View all flagged orders</Link>
            </p>
          </Banner>
        )}

        {/* Charts */}
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Score Distribution
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Distribution of risk scores across all orders in the last 30 days
                </Text>
                <Box minHeight="320px" padding="200">
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart
                      data={stats.score_distribution}
                      margin={{ top: 20, right: 20, bottom: 5, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 12, fill: "#64748B" }}
                        axisLine={{ stroke: "#CBD5E1" }}
                      />
                      <YAxis
                        tick={{ fontSize: 12, fill: "#64748B" }}
                        axisLine={{ stroke: "#CBD5E1" }}
                      />
                      <Tooltip content={<ScoreDistTooltip />} />
                      <Bar
                        dataKey="count"
                        radius={[6, 6, 0, 0]}
                        label={<BarLabel />}
                      >
                        {stats.score_distribution.map((entry, index) => (
                          <Cell key={index} fill={getScoreBarColor(entry.label)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </BlockStack>
            </Card>
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Risk Trend (30d)
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Average score (line) and order volume (bars)
                </Text>
                <Box minHeight="320px" padding="200">
                  <ResponsiveContainer width="100%" height={320}>
                    <ComposedChart
                      data={stats.trend_data}
                      margin={{ top: 10, right: 10, bottom: 5, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(d: string) => d.slice(5)}
                        tick={{ fontSize: 11, fill: "#64748B" }}
                        axisLine={{ stroke: "#CBD5E1" }}
                      />
                      <YAxis
                        yAxisId="left"
                        tick={{ fontSize: 11, fill: "#64748B" }}
                        axisLine={{ stroke: "#CBD5E1" }}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        tick={{ fontSize: 11, fill: "#64748B" }}
                        axisLine={{ stroke: "#CBD5E1" }}
                      />
                      <Tooltip />
                      <Legend
                        wrapperStyle={{ fontSize: 12 }}
                      />
                      <Bar
                        yAxisId="right"
                        dataKey="count"
                        fill="#BFDBFE"
                        radius={[4, 4, 0, 0]}
                        name="Orders"
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="avg_score"
                        stroke="#DC2626"
                        strokeWidth={2}
                        dot={false}
                        name="Avg Score"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </Box>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        {/* Recent High-Risk Orders */}
        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h2" variant="headingMd">
                Recent High-Risk Orders
              </Text>
              <Link url="/app/orders?risk_level=high">View all</Link>
            </InlineStack>
            {recentFlagged.length === 0 ? (
              <Box padding="400">
                <Text as="p" variant="bodyMd" tone="subdued" alignment="center">
                  No high-risk orders found. Everything looks good!
                </Text>
              </Box>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: "14px",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        borderBottom: "1px solid #E4E5E7",
                        textAlign: "left",
                      }}
                    >
                      <th style={{ padding: "10px 12px", color: "#6B7280", fontWeight: 500, fontSize: "13px" }}>
                        Order ID
                      </th>
                      <th style={{ padding: "10px 12px", color: "#6B7280", fontWeight: 500, fontSize: "13px" }}>
                        Score
                      </th>
                      <th style={{ padding: "10px 12px", color: "#6B7280", fontWeight: 500, fontSize: "13px" }}>
                        Risk Level
                      </th>
                      <th style={{ padding: "10px 12px", color: "#6B7280", fontWeight: 500, fontSize: "13px" }}>
                        Date
                      </th>
                      <th style={{ padding: "10px 12px", color: "#6B7280", fontWeight: 500, fontSize: "13px" }}>
                        Action
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentFlagged.map((order) => (
                      <tr
                        key={order.id}
                        style={{
                          borderBottom: "1px solid #F1F5F9",
                          cursor: "pointer",
                        }}
                        onClick={() => navigate(`/app/orders/${order.id}`)}
                      >
                        <td style={{ padding: "10px 12px", fontWeight: 600 }}>
                          {order.shopify_order_id}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <InlineStack gap="200" blockAlign="center">
                            <span
                              style={{
                                display: "inline-block",
                                width: "10px",
                                height: "10px",
                                borderRadius: "50%",
                                backgroundColor: getRiskDotColor(order.risk_level),
                              }}
                            />
                            <span style={{ fontWeight: 600 }}>{order.risk_score}</span>
                          </InlineStack>
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <Badge tone={riskBadgeTone(order.risk_level)}>
                            {order.risk_level.toUpperCase()}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 12px", color: "#6B7280" }}>
                          {new Date(order.created_at).toLocaleDateString()}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          <Link url={`/app/orders/${order.id}`}>Review</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
