import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.merchant import Merchant, DEFAULT_SETTINGS, DEFAULT_THRESHOLDS
from app.models.order_score import OrderScore, ScoringSignal
from app.models.rules import WhitelistBlacklist
from app.scoring.signals import OrderPayload
from app.services.scoring_pipeline import ScoringPipeline

# ── SQLite in-memory test DB ─────────────────────────────────────────

TEST_ENGINE = create_engine("sqlite:///:memory:")
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(TEST_ENGINE)
    yield
    Base.metadata.drop_all(TEST_ENGINE)


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def merchant(db_session):
    m = Merchant(
        shop_domain="pipeline-test.myshopify.com",
        access_token_encrypted="enc_token",
        plan_tier="starter",
        settings_json={
            **DEFAULT_SETTINGS,
            "digest_email": "alerts@test.com",
        },
        thresholds_json=DEFAULT_THRESHOLDS.copy(),
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


SAMPLE_ORDER = OrderPayload(
    order_id="ORD-5001",
    email="customer@gmail.com",
    ip_address="8.8.8.8",
    shipping_country="US",
    shipping_state="CA",
    billing_country="US",
    billing_state="CA",
    order_total=150.00,
    currency="USD",
    line_items=[{"title": "Widget", "quantity": 1, "price": "150.00"}],
    customer_id="cust_123",
    is_first_order=False,
    phone="+14155552671",
    card_brand="visa",
    card_country="US",
    avs_result="Y",
    cvv_result="M",
)


def _make_pipeline():
    """Create a ScoringPipeline with a mocked email service."""
    mock_email = MagicMock()
    mock_email.send_alert = MagicMock(return_value=True)
    pipeline = ScoringPipeline(email_service=mock_email)
    return pipeline, mock_email


# ── Tests ────────────────────────────────────────────────────────────

def test_pipeline_returns_expected_fields(db_session, merchant):
    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    assert "order_score_id" in result
    assert "order_id" in result
    assert result["order_id"] == "ORD-5001"
    assert "risk_score" in result
    assert "risk_level" in result
    assert "recommendation" in result
    assert "rule_score" in result
    assert "ml_score" in result
    assert "signal_contributions" in result
    assert 0 <= result["risk_score"] <= 100


def test_pipeline_persists_order_score(db_session, merchant):
    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    order_score = db_session.query(OrderScore).filter(
        OrderScore.id == result["order_score_id"]
    ).first()
    assert order_score is not None
    assert order_score.shopify_order_id == "ORD-5001"
    assert order_score.merchant_id == merchant.id
    assert order_score.risk_score == result["risk_score"]


def test_pipeline_persists_signals(db_session, merchant):
    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    signals = db_session.query(ScoringSignal).filter(
        ScoringSignal.order_score_id == result["order_score_id"]
    ).all()
    assert len(signals) > 0
    signal_names = [s.signal_name for s in signals]
    assert "avs_mismatch" in signal_names
    assert "first_time_customer" in signal_names


def test_pipeline_merchant_not_found(db_session):
    pipeline, _ = _make_pipeline()
    with pytest.raises(ValueError, match="Merchant 9999 not found"):
        pipeline.score_order(db_session, 9999, SAMPLE_ORDER)


def test_pipeline_whitelist_overrides(db_session, merchant):
    # Add customer email to whitelist
    wbl = WhitelistBlacklist(
        merchant_id=merchant.id,
        entry_type="email",
        value="customer@gmail.com",
        list_type="allow",
    )
    db_session.add(wbl)
    db_session.commit()

    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    assert result["risk_score"] == 0
    assert result["risk_level"] == "low"
    assert result["recommendation"] == "approve"
    assert result["custom_rule_action"] == "approve"


def test_pipeline_blacklist_overrides(db_session, merchant):
    # Add customer email to blacklist
    wbl = WhitelistBlacklist(
        merchant_id=merchant.id,
        entry_type="email",
        value="customer@gmail.com",
        list_type="block",
    )
    db_session.add(wbl)
    db_session.commit()

    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    assert result["risk_score"] == 100
    assert result["risk_level"] == "critical"
    assert result["recommendation"] == "cancel"
    assert result["custom_rule_action"] == "block"


def test_pipeline_sends_email_on_high_risk(db_session, merchant):
    # Ensure merchant settings enable email alerts for high/critical
    merchant.settings_json = {
        "email_alerts_enabled": True,
        "alert_on_risk_levels": ["high", "critical"],
        "digest_email": "alerts@test.com",
    }
    db_session.commit()

    # Blacklist the email to force critical risk
    wbl = WhitelistBlacklist(
        merchant_id=merchant.id,
        entry_type="email",
        value="customer@gmail.com",
        list_type="block",
    )
    db_session.add(wbl)
    db_session.commit()

    pipeline, mock_email = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    assert result["risk_level"] == "critical"
    mock_email.send_alert.assert_called_once()
    alert = mock_email.send_alert.call_args[0][0]
    assert alert.to == "alerts@test.com"
    assert alert.order_id == "ORD-5001"


def test_pipeline_no_email_when_disabled(db_session, merchant):
    merchant.settings_json = {
        "email_alerts_enabled": False,
        "alert_on_risk_levels": ["high", "critical"],
        "digest_email": "alerts@test.com",
    }
    db_session.commit()

    # Blacklist to force critical
    wbl = WhitelistBlacklist(
        merchant_id=merchant.id,
        entry_type="email",
        value="customer@gmail.com",
        list_type="block",
    )
    db_session.add(wbl)
    db_session.commit()

    pipeline, mock_email = _make_pipeline()
    pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    mock_email.send_alert.assert_not_called()


def test_pipeline_uses_store_average(db_session, merchant):
    """When prior orders exist, pipeline should use their average as store_avg."""
    # Add a prior order
    prior = OrderScore(
        merchant_id=merchant.id, shopify_order_id="prior_1",
        risk_score=40, risk_level="medium",
        signals_json={}, recommendation="review",
        rule_score=40.0, ml_score=40.0,
    )
    db_session.add(prior)
    db_session.commit()

    pipeline, _ = _make_pipeline()
    result = pipeline.score_order(db_session, merchant.id, SAMPLE_ORDER)

    # Pipeline should still work; we just verify it doesn't crash
    assert result["risk_score"] >= 0
    # Now there are 2 orders total
    count = db_session.query(OrderScore).filter(
        OrderScore.merchant_id == merchant.id
    ).count()
    assert count == 2
