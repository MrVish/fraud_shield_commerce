import type { OrderScore, DashboardStats, MerchantSettings, ScoringSignal } from "./types";

const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${SCORING_ENGINE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCORING_API_KEY,
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`Scoring API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getDashboardStats(merchantId: number, days: number = 30): Promise<DashboardStats> {
  return apiRequest(`/api/v1/merchants/${merchantId}/dashboard?days=${days}`);
}

export async function getOrderScores(merchantId: number, page: number = 1, limit: number = 20, riskLevel?: string): Promise<{ orders: OrderScore[]; total: number; page: number; limit: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (riskLevel) params.set("risk_level", riskLevel);
  return apiRequest(`/api/v1/merchants/${merchantId}/orders?${params}`);
}

export async function getOrderDetail(merchantId: number, orderId: string): Promise<OrderScore & { signals: { name: string; value: string; weight: number; raw_data: any }[]; override: any }> {
  return apiRequest(`/api/v1/merchants/${merchantId}/orders/${orderId}`);
}

export async function overrideOrder(merchantId: number, orderScoreId: number, action: string, reason: string): Promise<void> {
  await apiRequest(`/api/v1/merchants/${merchantId}/orders/${orderScoreId}/override`, {
    method: "POST",
    body: JSON.stringify({ action, reason }),
  });
}

export async function getMerchantSettings(merchantId: number): Promise<MerchantSettings> {
  return apiRequest(`/api/v1/merchants/${merchantId}/settings`);
}

export async function updateMerchantSettings(merchantId: number, settings: Partial<MerchantSettings>): Promise<MerchantSettings> {
  return apiRequest(`/api/v1/merchants/${merchantId}/settings`, {
    method: "PATCH",
    body: JSON.stringify(settings),
  });
}
