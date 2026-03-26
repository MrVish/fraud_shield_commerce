import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.merchant import Merchant
from tests.conftest import TestSessionLocal

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-key"}


@pytest.fixture(autouse=True)
def seed_merchant(setup_db):
    """Seed a test merchant for scoring tests."""
    db = TestSessionLocal()
    merchant = Merchant(
        id=1,
        shop_domain="test-store.myshopify.com",
        access_token_encrypted="enc",
        plan_tier="starter",
    )
    db.add(merchant)
    db.commit()
    db.close()


SAMPLE_ORDER = {
    "order_id": "1001", "merchant_id": 1, "email": "test@gmail.com",
    "ip_address": "8.8.8.8", "shipping_country": "US", "shipping_state": "CA",
    "billing_country": "US", "billing_state": "CA", "order_total": 150.00,
    "currency": "USD", "line_items": [{"title": "Widget", "quantity": 1, "price": "150.00"}],
    "customer_id": "cust_123", "is_first_order": False, "phone": "+14155552671",
    "card_brand": "visa", "card_country": "US", "avs_result": "Y", "cvv_result": "M",
}


def test_score_order_endpoint():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "risk_level" in data
    assert "signal_contributions" in data
    assert 0 <= data["risk_score"] <= 100


def test_score_order_returns_all_fields():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER, headers=HEADERS)
    data = response.json()
    assert "rule_score" in data
    assert "ml_score" in data
    assert "recommendation" in data


def test_score_order_persists_to_db():
    """Verify the pipeline persists the score to the database."""
    client.post("/api/v1/score", json=SAMPLE_ORDER, headers=HEADERS)
    response = client.get("/api/v1/merchants/1/orders", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_score_order_requires_api_key():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER)
    assert response.status_code == 401
