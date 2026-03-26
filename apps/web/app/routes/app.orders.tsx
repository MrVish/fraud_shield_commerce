import { useState, useCallback } from "react";
import type { LoaderFunctionArgs } from "@remix-run/node";
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
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const url = new URL(request.url);
  const page = parseInt(url.searchParams.get("page") || "1", 10);
  const limit = 20;
  const riskLevel = url.searchParams.get("risk_level") || "";

  try {
    const result = await getOrderScores(1, page, limit, riskLevel || undefined);
    return {
      orders: result.items,
      total: result.total,
      page,
      limit,
      riskLevel,
      error: null,
    } satisfies LoaderData;
  } catch (e) {
    console.error("[ShieldCommerce] Orders load error:", e);
    return {
      orders: [],
      total: 0,
      page,
      limit,
      riskLevel,
      error: "Unable to load orders from scoring engine.",
    } satisfies LoaderData;
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

export default function Orders() {
  const { orders, total, page, limit, riskLevel, error } = useLoaderData<LoaderData>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedRisk, setSelectedRisk] = useState(riskLevel);

  const handleRiskChange = useCallback((value: string) => {
    setSelectedRisk(value);
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set("risk_level", value);
    } else {
      params.delete("risk_level");
    }
    params.set("page", "1");
    setSearchParams(params);
  }, [searchParams, setSearchParams]);

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
        <Text as="span" variant="bodyMd">
          {order.risk_score}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Badge tone={riskBadgeTone(order.risk_level)}>
          {order.risk_level.toUpperCase()}
        </Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>{order.recommendation}</IndexTable.Cell>
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

        <Card>
          <BlockStack gap="400">
            <InlineStack align="start" gap="400">
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
