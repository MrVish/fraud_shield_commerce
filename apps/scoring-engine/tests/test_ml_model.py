import numpy as np
from app.scoring.feature_engineering import FeatureEngineer
from app.scoring.ml_model import FraudMLModel
from app.scoring.signals import ExtractedSignals, Signal


def _make_feature_signals() -> ExtractedSignals:
    signals = ExtractedSignals()
    signals.payment = [
        Signal(name="avs_mismatch", value=True, weight=8.0, category="payment"),
        Signal(name="cvv_failure", value=False, weight=6.0, category="payment"),
        Signal(name="card_country_mismatch", value=False, weight=12.0, category="payment"),
    ]
    signals.behavioral = [
        Signal(name="first_time_customer", value=True, weight=12.0, category="behavioral"),
        Signal(name="item_count", value=3, weight=0.0, category="behavioral"),
    ]
    signals.geographic = [
        Signal(name="address_mismatch", value=True, weight=15.0, category="geographic"),
        Signal(name="vpn_detected", value=False, weight=18.0, category="geographic"),
        Signal(name="ip_country_mismatch", value=False, weight=10.0, category="geographic"),
        Signal(name="tor_detected", value=False, weight=25.0, category="geographic"),
    ]
    signals.order_pattern = [
        Signal(name="order_value_deviation", value=2.5, weight=11.0, category="order_pattern"),
        Signal(name="high_value_order", value=False, weight=5.0, category="order_pattern"),
    ]
    signals.digital_footprint = [
        Signal(name="disposable_email", value=False, weight=20.0, category="digital_footprint"),
        Signal(name="free_email_provider", value=True, weight=5.0, category="digital_footprint"),
        Signal(name="invalid_email_format", value=False, weight=15.0, category="digital_footprint"),
    ]
    return signals


def test_feature_engineer_produces_vector():
    engineer = FeatureEngineer()
    vector = engineer.transform(_make_feature_signals())
    assert isinstance(vector, np.ndarray)
    assert len(vector) == engineer.feature_count()
    assert not np.isnan(vector).any()


def test_ml_model_predict_returns_score():
    model = FraudMLModel()
    engineer = FeatureEngineer()
    vector = engineer.transform(_make_feature_signals())
    score = model.predict(vector)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_feature_names_match_vector_length():
    engineer = FeatureEngineer()
    names = engineer.feature_names()
    assert len(names) == engineer.feature_count()
