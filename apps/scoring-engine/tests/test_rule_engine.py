from app.scoring.rule_engine import RuleBasedScorer, ScoringResult
from app.scoring.signals import ExtractedSignals, Signal


def _make_signals(overrides: dict | None = None) -> ExtractedSignals:
    defaults = {
        "avs_mismatch": (True, 8.0, "payment"),
        "cvv_failure": (False, 6.0, "payment"),
        "first_time_customer": (True, 12.0, "behavioral"),
        "address_mismatch": (True, 15.0, "geographic"),
        "vpn_detected": (False, 18.0, "geographic"),
        "order_value_deviation": (3.2, 11.0, "order_pattern"),
        "disposable_email": (False, 20.0, "digital_footprint"),
        "free_email_provider": (True, 5.0, "digital_footprint"),
    }
    if overrides:
        defaults.update(overrides)
    signals = ExtractedSignals()
    for name, (value, weight, category) in defaults.items():
        signal = Signal(name=name, value=value, weight=weight, category=category)
        getattr(signals, category).append(signal)
    return signals


def test_scoring_returns_result():
    scorer = RuleBasedScorer()
    result = scorer.score(_make_signals())
    assert isinstance(result, ScoringResult)
    assert 0 <= result.score <= 100
    assert result.risk_level in ("low", "medium", "high", "critical")


def test_low_risk_order():
    signals = _make_signals({
        "avs_mismatch": (False, 8.0, "payment"),
        "first_time_customer": (False, 12.0, "behavioral"),
        "address_mismatch": (False, 15.0, "geographic"),
        "order_value_deviation": (1.0, 11.0, "order_pattern"),
    })
    result = RuleBasedScorer().score(signals)
    assert result.risk_level == "low"
    assert result.score <= 30


def test_high_risk_order():
    signals = _make_signals({
        "avs_mismatch": (True, 8.0, "payment"),
        "vpn_detected": (True, 18.0, "geographic"),
        "address_mismatch": (True, 15.0, "geographic"),
        "disposable_email": (True, 20.0, "digital_footprint"),
        "first_time_customer": (True, 12.0, "behavioral"),
        "order_value_deviation": (4.0, 11.0, "order_pattern"),
    })
    result = RuleBasedScorer().score(signals)
    assert result.risk_level in ("high", "critical")
    assert result.score >= 61


def test_scoring_includes_signal_contributions():
    result = RuleBasedScorer().score(_make_signals())
    assert len(result.signal_contributions) > 0
    for contrib in result.signal_contributions:
        assert "signal_name" in contrib
        assert "points_added" in contrib
