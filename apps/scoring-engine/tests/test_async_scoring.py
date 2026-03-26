"""Tests for the async scoring endpoint and worker."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.merchant import Merchant
from tests.conftest import TestSessionLocal

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-key"}

SAMPLE_ORDER = {
    "order_id": "2001", "merchant_id": 1, "email": "test@gmail.com",
    "ip_address": "8.8.8.8", "shipping_country": "US", "shipping_state": "CA",
    "billing_country": "US", "billing_state": "CA", "order_total": 150.00,
    "currency": "USD", "line_items": [{"title": "Widget", "quantity": 1, "price": "150.00"}],
    "customer_id": "cust_123", "is_first_order": False, "phone": "+14155552671",
}


@pytest.fixture(autouse=True)
def seed_merchant(setup_db):
    db = TestSessionLocal()
    merchant = Merchant(
        id=1, shop_domain="test-store.myshopify.com",
        access_token_encrypted="enc", plan_tier="starter",
    )
    db.add(merchant)
    db.commit()
    db.close()


@patch("app.api.v1.scoring.RedisClient")
def test_async_score_returns_202(mock_redis_cls):
    """Async endpoint enqueues and returns 202."""
    mock_redis = MagicMock()
    mock_redis_cls.return_value = mock_redis

    response = client.post("/api/v1/score/async", json=SAMPLE_ORDER, headers=HEADERS)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["order_id"] == "2001"
    mock_redis.enqueue.assert_called_once()


@patch("app.api.v1.scoring.RedisClient")
def test_async_score_returns_503_on_redis_failure(mock_redis_cls):
    """If Redis is unavailable, return 503."""
    mock_redis_cls.side_effect = Exception("Connection refused")

    response = client.post("/api/v1/score/async", json=SAMPLE_ORDER, headers=HEADERS)
    assert response.status_code == 503


def test_async_score_requires_api_key():
    response = client.post("/api/v1/score/async", json=SAMPLE_ORDER)
    assert response.status_code == 401
