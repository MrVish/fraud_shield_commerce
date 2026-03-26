import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from app.main import app
from app.models.merchant import Merchant, DEFAULT_SETTINGS, DEFAULT_THRESHOLDS
from app.models.order_score import OrderScore, ScoringSignal
from app.models.chargeback import Chargeback
from app.models.rules import MerchantOverride
from tests.conftest import TestSessionLocal

HEADERS = {"X-API-Key": "dev-key"}

client = TestClient(app)


@pytest.fixture
def merchant(db_session):
    m = Merchant(
        shop_domain="test-store.myshopify.com",
        access_token_encrypted="enc_token",
        plan_tier="starter",
        settings_json=DEFAULT_SETTINGS.copy(),
        thresholds_json=DEFAULT_THRESHOLDS.copy(),
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def merchant_with_orders(db_session, merchant):
    now = datetime.now(timezone.utc)
    orders = [
        OrderScore(
            merchant_id=merchant.id, shopify_order_id=f"order_{i}",
            risk_score=score, risk_level=level,
            signals_json={"test": True}, recommendation=rec,
            rule_score=float(score), ml_score=float(score),
            order_total=total,
            created_at=now - timedelta(days=i),
        )
        for i, (score, level, rec, total) in enumerate([
            (15, "low", "approve", 50.0),
            (45, "medium", "review", 120.0),
            (75, "high", "review", 350.0),
            (92, "critical", "cancel", 487.0),
            (30, "low", "approve", 89.99),
        ])
    ]
    db_session.add_all(orders)
    db_session.commit()
    for o in orders:
        db_session.refresh(o)
    return orders


@pytest.fixture
def order_with_signals(db_session, merchant):
    order = OrderScore(
        merchant_id=merchant.id, shopify_order_id="detailed_order",
        risk_score=65, risk_level="high",
        signals_json={"vpn_detected": True}, recommendation="review",
        rule_score=60.0, ml_score=70.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    signals = [
        ScoringSignal(
            order_score_id=order.id, signal_name="vpn_detected",
            signal_value="True", signal_weight=18.0,
            raw_data_json={"explanation": "VPN detected", "category": "geographic"},
        ),
        ScoringSignal(
            order_score_id=order.id, signal_name="first_time_customer",
            signal_value="True", signal_weight=12.0,
            raw_data_json={"explanation": "First order", "category": "behavioral"},
        ),
    ]
    db_session.add_all(signals)
    db_session.commit()
    return order


# ── Dashboard Stats Tests ────────────────────────────────────────────

def test_dashboard_stats_structure(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/dashboard?days=30", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_orders" in data
    assert "flagged_orders" in data
    assert "avg_score" in data
    assert "chargeback_count" in data
    assert "chargeback_amount" in data
    assert "score_distribution" in data
    assert "trend_data" in data
    assert "revenue_protected" in data
    assert "chargeback_rate" in data
    assert "chargeback_health" in data
    assert data["total_orders"] == 5
    assert data["flagged_orders"] == 2  # high + critical
    assert data["chargeback_health"] == "good"


def test_dashboard_stats_score_distribution(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/dashboard?days=30", headers=HEADERS)
    data = resp.json()
    dist = data["score_distribution"]
    assert len(dist) == 5
    labels = [d["label"] for d in dist]
    assert "0-20" in labels
    assert "81-100" in labels


def test_dashboard_stats_empty_merchant(merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/dashboard", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_orders"] == 0
    assert data["avg_score"] == 0.0


def test_dashboard_merchant_not_found():
    resp = client.get("/api/v1/merchants/9999/dashboard", headers=HEADERS)
    assert resp.status_code == 404


# ── Orders List Tests ────────────────────────────────────────────────

def test_orders_list_pagination(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/orders?page=1&limit=2", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["limit"] == 2
    assert data["total"] == 5
    assert len(data["orders"]) == 2


def test_orders_list_risk_filter(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/orders?risk_level=high", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["orders"][0]["risk_level"] == "high"


def test_orders_list_all(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/orders", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5


# ── Order Detail Tests ───────────────────────────────────────────────

def test_order_detail(order_with_signals, merchant):
    resp = client.get(
        f"/api/v1/merchants/{merchant.id}/orders/{order_with_signals.id}",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["shopify_order_id"] == "detailed_order"
    assert data["risk_score"] == 65
    assert len(data["signals"]) == 2
    signal_names = [s["name"] for s in data["signals"]]
    assert "vpn_detected" in signal_names
    assert "risk_summary" in data
    assert len(data["risk_summary"]) > 0


def test_order_detail_not_found(merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/orders/9999", headers=HEADERS)
    assert resp.status_code == 404


# ── Override Tests ───────────────────────────────────────────────────

def test_override_order(order_with_signals, merchant):
    resp = client.post(
        f"/api/v1/merchants/{merchant.id}/orders/{order_with_signals.id}/override",
        json={"action": "approve", "reason": "Known customer"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["override_action"] == "approve"
    assert data["original_recommendation"] == "review"
    assert data["reason"] == "Known customer"


def test_override_duplicate(order_with_signals, merchant):
    # First override
    client.post(
        f"/api/v1/merchants/{merchant.id}/orders/{order_with_signals.id}/override",
        json={"action": "approve", "reason": "First"},
        headers=HEADERS,
    )
    # Second override should fail
    resp = client.post(
        f"/api/v1/merchants/{merchant.id}/orders/{order_with_signals.id}/override",
        json={"action": "cancel", "reason": "Second"},
        headers=HEADERS,
    )
    assert resp.status_code == 409


# ── Settings Tests ───────────────────────────────────────────────────

def test_get_settings(merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/settings", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "settings" in data
    assert "thresholds" in data
    assert data["settings"]["email_alerts_enabled"] is True
    assert data["thresholds"]["low_max"] == 30


def test_patch_settings(merchant):
    resp = client.patch(
        f"/api/v1/merchants/{merchant.id}/settings",
        json={"settings": {"digest_email": "admin@test.com"}, "thresholds": {"low_max": 25}},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["settings"]["digest_email"] == "admin@test.com"
    assert data["settings"]["email_alerts_enabled"] is True  # unchanged
    assert data["thresholds"]["low_max"] == 25


# ── Chargeback Tests ────────────────────────────────────────────────

def test_record_chargeback(merchant):
    resp = client.post(
        "/api/v1/chargebacks",
        json={
            "merchant_id": merchant.id,
            "shopify_order_id": "order_999",
            "dispute_type": "fraudulent",
            "amount": 149.99,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["merchant_id"] == merchant.id
    assert data["dispute_type"] == "fraudulent"
    assert data["amount"] == 149.99
    assert data["predicted_correctly"] is None  # no matching order score


def test_record_chargeback_links_order_score(order_with_signals, merchant):
    resp = client.post(
        "/api/v1/chargebacks",
        json={
            "merchant_id": merchant.id,
            "shopify_order_id": "detailed_order",
            "dispute_type": "fraudulent",
            "amount": 250.00,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["order_score_id"] == order_with_signals.id
    assert data["predicted_correctly"] is True  # order was "high" risk


def test_record_chargeback_merchant_not_found():
    resp = client.post(
        "/api/v1/chargebacks",
        json={
            "merchant_id": 9999,
            "shopify_order_id": "order_1",
            "dispute_type": "fraudulent",
            "amount": 100.0,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 404


# ── Merchant Registration Tests ──────────────────────────────────────

def test_register_merchant():
    resp = client.post(
        "/api/v1/merchants",
        json={
            "shop_domain": "new-store.myshopify.com",
            "access_token_encrypted": "new_token",
            "plan_tier": "pro",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["shop_domain"] == "new-store.myshopify.com"
    assert data["plan_tier"] == "pro"
    assert "settings" in data
    assert "thresholds" in data


def test_register_merchant_upsert(merchant):
    resp = client.post(
        "/api/v1/merchants",
        json={
            "shop_domain": "test-store.myshopify.com",
            "access_token_encrypted": "updated_token",
            "plan_tier": "enterprise",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == merchant.id  # same merchant
    assert data["plan_tier"] == "enterprise"


# ── Dashboard with Chargebacks ───────────────────────────────────────

def test_dashboard_revenue_protected(merchant_with_orders, merchant):
    resp = client.get(f"/api/v1/merchants/{merchant.id}/dashboard?days=30", headers=HEADERS)
    data = resp.json()
    # high (350.0) + critical (487.0) = 837.0
    assert data["revenue_protected"] == 837.0


def test_dashboard_with_chargebacks(db_session, merchant_with_orders, merchant):
    now = datetime.now(timezone.utc)
    cb = Chargeback(
        merchant_id=merchant.id,
        shopify_order_id="order_3",
        dispute_type="fraudulent",
        amount=199.99,
        filed_at=now - timedelta(days=2),
    )
    db_session.add(cb)
    db_session.commit()

    resp = client.get(f"/api/v1/merchants/{merchant.id}/dashboard?days=30", headers=HEADERS)
    data = resp.json()
    assert data["chargeback_count"] == 1
    assert data["chargeback_amount"] == 199.99
    # 1 chargeback / 5 orders = 20% - elevated
    assert data["chargeback_rate"] == 20.0
    assert data["chargeback_health"] == "elevated"
