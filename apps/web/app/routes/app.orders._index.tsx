import { useState, useCallback } from "react";
import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useNavigate, useSearchParams } from "@remix-run/react";
import {
  Page,
  Card,
  IndexTable,
  Text,
  Badge,
  Select,
  BlockStack,
  InlineStack,
  Pagination,
  Banner,
  Box,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { getOrderScores } from "../lib/scoring-api.server";
import type { OrderScore } from "../lib/types";

interface LoaderData {
  orders: OrderScore[];
  total: number;
  page: number;
  limit: number;
  riskLevel: string;
  needsReviewCount: number;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const url = new URL(request.url);
  const page = parseInt(url.searchParams.get("page") || "1", 10);
  const limit = 20;
  const riskLevel = url.searchParams.get("risk_level") || "";

  try {
    const [result, highResult, criticalResult] = await Promise.all([
      getOrderScores(1, page, limit, riskLevel || undefined),
      getOrderScores(1, 1, 1, "high"),
      getOrderScores(1, 1, 1, "critical"),
    ]);

    const needsReviewCount = (highResult.total ?? 0) + (criticalResult.total ?? 0);

    return json({
      orders: result.orders ?? [],
      total: result.total ?? 0,
      page,
      limit,
      riskLevel,
      needsReviewCount,
      error: null,
    });
  } catch (e) {
    console.error("[ShieldCommerce] Orders load error:", e);
    return json({
      orders: [],
      total: 0,
      page,
      limit,
      riskLevel,
      needsReviewCount: 0,
      error: "Unable to load orders from scoring engine.",
    });
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

function getScoreDotColor(score: number): string {
  if (score <= 30) return "#22C55E";
  if (score <= 60) return "#F59E0B";
  if (score <= 80) return "#EF4444";
  return "#991B1B";
}

function ScoreDot({ score }: { score: number }) {
  return (
    <InlineStack gap="200" blockAlign="center">
      <span
        style={{
          display: "inline-block",
          width: "10px",
          height: "10px",
          borderRadius: "50%",
          backgroundColor: getScoreDotColor(score),
          flexShrink: 0,
        }}
      />
      <Text as="span" variant="bodyMd" fontWeight="semibold">
        {score}
      </Text>
    </InlineStack>
  );
}

export default function Orders() {
  const { orders, total, page, limit, riskLevel, needsReviewCount, error } =
    useLoaderData<typeof loader>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedRisk, setSelectedRisk] = useState(riskLevel);

  const handleRiskChange = useCallback(
    (value: string) => {
      setSelectedRisk(value);
      const params = new URLSearchParams(searchParams);
      if (value) {
        params.set("risk_level", value);
      } else {
        params.delete("risk_level");
      }
      params.set("page", "1");
      setSearchParams(params);
    },
    [searchParams, setSearchParams],
  );

  const totalPages = Math.ceil(total / limit);
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  const handlePrev = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.set("page", String(page - 1));
    setSearchParams(params);
  }, [page, searchParams, setSearchParams]);

  const handleNext = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.set("page", String(page + 1));
    setSearchParams(params);
  }, [page, searchParams, setSearchParams]);

  const rowMarkup = orders.map((order, index) => (
    <IndexTable.Row
      id={String(order.id)}
      key={order.id}
      position={index}
      onClick={() => navigate(`/app/orders/${order.id}`)}
    >
      <IndexTable.Cell>
        <Text variant="bodyMd" fontWeight="bold" as="span">
          {order.shopify_order_id}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <ScoreDot score={order.risk_score} />
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Badge tone={riskBadgeTone(order.risk_level)}>
          {order.risk_level.toUpperCase()}
        </Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {order.recommendation}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        {new Date(order.created_at).toLocaleDateString()}
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page>
      <TitleBar title="Order Risk Scores" />
      <BlockStack gap="400">
        {error && (
          <Banner tone="warning">
            <p>{error}</p>
          </Banner>
        )}

        {needsReviewCount > 0 && (
          <Banner
            tone="warning"
            title={`${needsReviewCount} orders need review`}
            action={{
              content: "Show flagged orders",
              onAction: () => handleRiskChange("high"),
            }}
          >
            <p>
              There are {needsReviewCount} orders flagged as high or critical risk that require manual review.
            </p>
          </Banner>
        )}

        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between" blockAlign="center">
              <Select
                label="Filter by Risk Level"
                labelInline
                options={[
                  { label: "All", value: "" },
                  { label: "Low", value: "low" },
                  { label: "Medium", value: "medium" },
                  { label: "High", value: "high" },
                  { label: "Critical", value: "critical" },
                ]}
                value={selectedRisk}
                onChange={handleRiskChange}
              />
              <Text as="p" variant="bodySm" tone="subdued">
                {total} order{total !== 1 ? "s" : ""} total
              </Text>
            </InlineStack>

            <IndexTable
              resourceName={{ singular: "order", plural: "orders" }}
              itemCount={orders.length}
              headings={[
                { title: "Order ID" },
                { title: "Risk Score" },
                { title: "Risk Level" },
                { title: "Recommendation" },
                { title: "Date" },
              ]}
              selectable={false}
            >
              {rowMarkup}
            </IndexTable>

            <InlineStack align="center">
              <Pagination
                hasPrevious={hasPrev}
                hasNext={hasNext}
                onPrevious={handlePrev}
                onNext={handleNext}
              />
            </InlineStack>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
