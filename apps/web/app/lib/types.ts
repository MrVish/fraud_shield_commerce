export interface OrderScore {
  id: number;
  shopify_order_id: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  signals_json: Record<string, any>;
  recommendation: string;
  rule_score: number | null;
  ml_score: number | null;
  created_at: string;
}

export interface ScoringSignal {
  signal_name: string;
  signal_value: string;
  signal_weight: number;
  raw_data_json: Record<string, any> | null;
}

export interface DashboardStats {
  total_orders: number;
  flagged_orders: number;
  avg_score: number;
  chargeback_count: number;
  chargeback_amount: number;
  score_distribution: { range: string; count: number }[];
  trend_data: { date: string; avg_score: number; order_count: number }[];
}

export interface MerchantSettings {
  thresholds: {
    low_max: number;
    medium_max: number;
    high_max: number;
    auto_approve_below: number;
    auto_cancel_above: number;
  };
  settings: {
    email_alerts_enabled: boolean;
    alert_on_risk_levels: string[];
    digest_frequency: string;
    digest_email: string;
  };
}

export type PlanTier = "starter" | "growth" | "pro" | "scale";

export const PLAN_FEATURES: Record<PlanTier, string[]> = {
  starter: ["scoring", "signals", "basic_dashboard", "email_alerts"],
  growth: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking"],
  pro: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking", "advanced_analytics", "api_access"],
  scale: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking", "advanced_analytics", "api_access", "bulk_actions", "exports", "custom_model"],
};
