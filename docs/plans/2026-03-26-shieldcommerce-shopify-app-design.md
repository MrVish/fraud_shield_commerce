# ShieldCommerce Shopify App — Design Document

**Date:** 2026-03-26
**Status:** Approved
**PRD Reference:** ShieldCommerce_PRD_v2.docx

---

## 1. Overview

ShieldCommerce is an AI-powered fraud intelligence platform for Shopify merchants. It provides real-time order risk scoring (0-100) with transparent signal breakdowns, an analytics dashboard, and a custom rules engine — all at $29-149/mo targeting SMB merchants doing $10K-$500K/mo GMV.

**Positioning:** "SEON for SMBs" — intelligence-first, not insurance. No chargeback guarantee at launch.

---

## 2. Architecture

### High-Level

```
Shopify (Webhooks + Order Risk API)
        │
        ▼
Remix App (DigitalOcean App Platform - Node)
  - OAuth / Session Management
  - Polaris Dashboard UI
  - App Bridge Integration
        │ Internal REST API
        ▼
FastAPI Scoring Engine (DigitalOcean App Platform - Docker)
  - Signal Extraction (30+ signals)
  - XGBoost ML Model + Rule-Based Scoring
  - Pluggable Enrichment Layer
  - Custom Rules Engine
        │
   ┌────┴────┐
   ▼         ▼
PostgreSQL  Redis
(DO Managed)(DO Managed)
```

### Key Decisions

- **All on DigitalOcean** — single provider, single billing, internal networking between services
- **Remix + Polaris** — Shopify's recommended framework, official tooling support
- **FastAPI backend** — separate scoring engine for ML workloads, independent scaling
- **Pluggable enrichment** — interface-based design so free tools can be swapped for paid APIs (IPQS) via config change

---

## 3. Order Scoring Pipeline

1. **Webhook received** — Shopify fires `orders/create` → Remix validates HMAC-SHA256
2. **Queue** — Validated payload pushed to Redis queue
3. **Signal extraction** — FastAPI worker extracts 30+ signals across 5 categories:
   - Payment (AVS, CVV, BIN country, card type)
   - Behavioral (velocity, time-to-checkout)
   - Geographic (IP vs shipping, VPN detection)
   - Order pattern (amount deviation, first-time buyer)
   - Digital footprint (disposable email, phone type)
4. **Enrichment (cache-first)** — Check Redis cache (target 60-70% hit rate), miss → local lookups
5. **Scoring** — Rule-based weighted score + XGBoost ML score → combined final score (0-100)
6. **Custom rules** — Merchant whitelist/blacklist/threshold overrides applied
7. **Write-back** — POST score to Shopify Order Risk API + persist to PostgreSQL
8. **Alert** — If above threshold, send email alert via SendGrid

**Target latency:** <200ms (all enrichment is local at MVP)

---

## 4. Enrichment Strategy

### MVP (Free-First, $0/mo)

| Category | Tool | Type |
|----------|------|------|
| IP Intelligence | MaxMind GeoLite2 | Local DB |
| Email Validation | Open-source disposable domain list (4K+ domains) | Local |
| Phone Parsing | Google libphonenumber | Local |
| BIN/Card Lookup | Shopify payment metadata | Already in payload |
| Device Fingerprint | ThumbMarkJS (MIT) | Client-side JS |

### Scale Path (When Revenue Supports It)

| Category | Upgrade To | Cost |
|----------|-----------|------|
| IP + Email + Phone | IPQualityScore (all-in-one) | ~$0.0003/query |
| Device Fingerprint | Fingerprint.com | $99/mo |
| BIN Lookup | BinSearchLookup | Paid tiers |

**Design principle:** Every enrichment provider implements a common interface. Swapping providers is a config change, not a code change.

---

## 5. ML Strategy

### Dual-Model from Day 1

- **Rule-based scoring** — Weighted scoring system with configurable weights per signal category (Payment 30%, Behavioral 25%, Geographic 20%, Order Pattern 15%, Digital Footprint 10%)
- **XGBoost ML model** — Trained on Kaggle IEEE-CIS Fraud Detection dataset + synthetic Shopify-like data
- **Combined score** — Weighted average of both models (configurable ratio, default 50/50)
- **Model versioning** — `model_versions` table tracks accuracy, precision, recall, F1 per version

### Risk Classification

| Score | Level | Default Action | Badge |
|-------|-------|---------------|-------|
| 0-30 | Low | Auto-approve | Green |
| 31-60 | Medium | Recommend review | Amber |
| 61-85 | High | Hold for review | Red |
| 86-100 | Critical | Recommend cancel | Dark red |

---

## 6. MVP Feature Set — 6 Pages

| Page | Description |
|------|-------------|
| **Dashboard** | KPI cards (total orders, flagged %, avg score, chargebacks) + score distribution bar chart + risk trend line (7/30/90 day) |
| **Orders** | Sortable table with risk badges, score, date. Click to expand signal breakdown |
| **Order Detail** | Signal-by-signal table + one-click approve/hold/cancel + override reason logging |
| **Rules** | Threshold sliders, whitelist/blacklist management, custom rule builder |
| **Settings** | Email alert preferences, digest frequency, enrichment config |
| **Billing** | Current plan, usage, upgrade/downgrade via Shopify Billing API |

### Charts: Recharts (lightweight, React-native)

### Phase 2 additions (not MVP):
- Geography heatmap
- False decline monitor
- Model performance metrics (precision/recall/F1)
- Slack integration
- Bulk actions, CSV/PDF export
- In-app notifications

---

## 7. Database Schema

### Core Tables

- **merchants** — shop_domain, access_token (AES-256 encrypted), plan_tier, settings_json, thresholds_json
- **order_scores** — merchant_id, shopify_order_id, risk_score, risk_level, signals_json (denormalized), recommendation
- **scoring_signals** — order_score_id, signal_name, signal_value, signal_weight (normalized for analytics)
- **chargebacks** — shopify_order_id, order_score_id, dispute_type, amount, outcome, predicted_correctly
- **custom_rules** — merchant_id, rule_name, conditions_json, action, priority, is_active
- **whitelist_blacklist** — merchant_id, entry_type (email/ip/bin), value, list_type (allow/block)
- **merchant_overrides** — order_score_id, original_recommendation, override_action, reason
- **enrichment_cache** — lookup_type, lookup_key, result_json, expires_at
- **model_versions** — version, algorithm, accuracy, precision, recall, f1_score, is_active
- **daily_digests** — merchant_id, date, total_orders, flagged_orders, avg_score, sent_at

---

## 8. Tech Stack

| Layer | Technology | Hosting | Cost |
|-------|-----------|---------|------|
| Frontend | Remix + Polaris + App Bridge | DO App Platform (Node) | ~$12/mo |
| Scoring Engine | Python 3.11+ FastAPI | DO App Platform (Docker) | ~$12/mo |
| Database | PostgreSQL 16 | DO Managed Database | ~$15/mo |
| Cache/Queue | Redis 7 | DO Managed Redis | ~$15/mo |
| Charts | Recharts | Bundled | $0 |
| Email | SendGrid (free: 100/day) | External | $0 |
| ML | XGBoost + scikit-learn | Bundled | $0 |
| Errors | Sentry (free tier) | External | $0 |
| CI/CD | GitHub Actions | GitHub | $0 |

**Total MVP infra: ~$54/mo**
**Break-even: 2 merchants on Starter plan**

---

## 9. Pricing

| Plan | Price | Orders/Mo | Unlocks |
|------|-------|-----------|---------|
| Starter | $29/mo | 500 | Scoring, signals, basic dashboard, email alerts, 30-day history |
| Growth | $69/mo | 2,000 | + Custom rules, chargeback tracking, 90-day history |
| Pro | $149/mo | 10,000 | + Advanced analytics, heatmap, model metrics, API access, 1-year history |
| Scale | $249/mo | 25,000 | + Onboarding, exports, bulk actions, custom model training |

- 14-day free trial, no credit card (Shopify Billing API)
- Feature gating in Remix frontend, not FastAPI (scoring engine stays plan-agnostic)
- Soft overage: upgrade prompt, no hard cutoff mid-month

---

## 10. Shopify Integration Points

**OAuth scopes:** `read_orders`, `write_orders`, `read_customers`

**Webhooks consumed:**
- `orders/create` — trigger scoring
- `disputes/create` — chargeback tracking

**APIs called:**
- Order Risk API — write-back scores
- AppSubscription GraphQL — billing management

**GDPR webhooks (mandatory):**
- `customers/data_request`
- `customers/redact`
- `shop/redact`

---

## 11. Notifications (MVP)

- **Email alerts** — High-risk order notifications via SendGrid
- **Email digest** — Daily/weekly summary (configurable)
- Shopify admin risk badge on orders (via Order Risk API, automatic)

**Phase 2:** Slack webhooks, in-app toast notifications

---

## 12. Scale Path Summary

| Area | MVP | Phase 2 |
|------|-----|---------|
| Enrichment | Free local tools | IPQS + Fingerprint.com |
| Analytics | Essential charts (Recharts) | Heatmap, model metrics (ECharts) |
| Notifications | Email only | + Slack, in-app |
| Actions | Manual approve/hold/cancel | Auto-hold, auto-cancel, bulk actions |
| Export | None | CSV/PDF reports |
| Guarantee | None | Chargeback guarantee (Phase 3) |
| Network | Single-merchant | Cross-merchant fraud signals (Phase 4) |
