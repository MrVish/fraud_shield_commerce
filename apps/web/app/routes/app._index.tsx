import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  InlineGrid,
  Box,
  Banner,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { authenticate } from "../shopify.server";
import { getDashboardStats } from "../lib/scoring-api.server";
import type { DashboardStats } from "../lib/types";

interface LoaderData {
  stats: DashboardStats | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  try {
    const stats = await getDashboardStats(1, 30);
    return { stats, error: null } satisfies LoaderData;
  } catch (e) {
    console.error("[ShieldCommerce] Dashboard load error:", e);
    return {
      stats: null,
      error: "Unable to connect to scoring engine. Showing empty dashboard.",
    } satisfies LoaderData;
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
};

export default function Dashboard() {
  const { stats: rawStats, error } = useLoaderData<LoaderData>();
  const stats = rawStats ?? emptyStats;

  return (
    <Page>
      <TitleBar title="ShieldCommerce Dashboard" />
      <BlockStack gap="500">
        {error && (
          <Banner tone="warning">
            <p>{error}</p>
          </Banner>
        )}

        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" tone="subdued">
                Total Orders (30d)
              </Text>
              <Text as="p" variant="headingXl">
                {stats.total_orders.toLocaleString()}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" tone="subdued">
                Flagged Orders
              </Text>
              <Text as="p" variant="headingXl" tone="critical">
                {stats.flagged_orders.toLocaleString()}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" tone="subdued">
                Avg Risk Score
              </Text>
              <Text as="p" variant="headingXl">
                {stats.avg_score.toFixed(1)}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" tone="subdued">
                Chargebacks
              </Text>
              <Text as="p" variant="headingXl" tone="critical">
                {stats.chargeback_count} (${stats.chargeback_amount.toFixed(2)})
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Score Distribution
                </Text>
                <Box minHeight="300px">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={stats.score_distribution}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="label" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="count" fill="#5C6AC4" radius={[4, 4, 0, 0]} />
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
                <Box minHeight="300px">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={stats.trend_data}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(d: string) => d.slice(5)}
                      />
                      <YAxis />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="avg_score"
                        stroke="#BF0711"
                        strokeWidth={2}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="count"
                        stroke="#5C6AC4"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
