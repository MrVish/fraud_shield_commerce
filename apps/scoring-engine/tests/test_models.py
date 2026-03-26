from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from app.models.base import Base
from app.models.merchant import Merchant
from app.models.order_score import OrderScore, ScoringSignal
from app.models.chargeback import Chargeback
from app.models.rules import CustomRule, WhitelistBlacklist, MerchantOverride
from app.models.enrichment import EnrichmentCache
from app.models.model_version import ModelVersion
from app.models.daily_digest import DailyDigest


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "merchants", "order_scores", "scoring_signals", "chargebacks",
        "custom_rules", "whitelist_blacklist", "merchant_overrides",
        "enrichment_cache", "model_versions", "daily_digests",
    ]
    for table in expected_tables:
        assert table in tables, f"Missing table: {table}"


def test_merchant_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = Merchant(
            shop_domain="test-store.myshopify.com",
            access_token_encrypted="encrypted_token_here",
            plan_tier="starter",
        )
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        assert merchant.id is not None
        assert merchant.shop_domain == "test-store.myshopify.com"
        assert merchant.plan_tier == "starter"
        assert merchant.thresholds_json is not None


def test_order_score_with_signals():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = Merchant(
            shop_domain="test.myshopify.com",
            access_token_encrypted="enc",
            plan_tier="starter",
        )
        session.add(merchant)
        session.commit()

        score = OrderScore(
            merchant_id=merchant.id,
            shopify_order_id="12345",
            risk_score=73,
            risk_level="high",
            signals_json={"vpn_detected": True},
            recommendation="review",
        )
        session.add(score)
        session.commit()

        signal = ScoringSignal(
            order_score_id=score.id,
            signal_name="vpn_detected",
            signal_value="true",
            signal_weight=18.0,
            raw_data_json={"provider": "NordVPN"},
        )
        session.add(signal)
        session.commit()

        assert score.risk_score == 73
        assert signal.signal_weight == 18.0
