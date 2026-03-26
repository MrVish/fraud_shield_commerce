from app.scoring.combined_scorer import CombinedScorer, FinalScore
from app.scoring.signals import ExtractedSignals, Signal
from app.scoring.custom_rules import CustomRuleEngine, RuleDefinition


def _make_signals(vpn=False, disposable=False, deviation=1.0):
    signals = ExtractedSignals()
    signals.payment = [Signal("avs_mismatch", False, 8.0, "payment")]
    signals.behavioral = [Signal("first_time_customer", True, 12.0, "behavioral")]
    signals.geographic = [
        Signal("address_mismatch", False, 15.0, "geographic"),
        Signal("vpn_detected", vpn, 18.0, "geographic"),
    ]
    signals.order_pattern = [Signal("order_value_deviation", deviation, 11.0, "order_pattern")]
    signals.digital_footprint = [
        Signal("disposable_email", disposable, 20.0, "digital_footprint"),
        Signal("free_email_provider", True, 5.0, "digital_footprint"),
    ]
    return signals


def test_combined_scorer_returns_final_score():
    scorer = CombinedScorer(rule_weight=0.5, ml_weight=0.5)
    result = scorer.score(_make_signals())
    assert isinstance(result, FinalScore)
    assert 0 <= result.final_score <= 100


def test_combined_scorer_includes_both_scores():
    scorer = CombinedScorer(rule_weight=0.5, ml_weight=0.5)
    result = scorer.score(_make_signals())
    assert result.rule_score is not None
    assert result.ml_score is not None


def test_custom_rule_whitelist_overrides():
    rules = CustomRuleEngine()
    rules.add_whitelist("email", "trusted@company.com")
    action = rules.evaluate(email="trusted@company.com", ip="1.2.3.4")
    assert action == "approve"


def test_custom_rule_blacklist_overrides():
    rules = CustomRuleEngine()
    rules.add_blacklist("email", "fraud@bad.com")
    action = rules.evaluate(email="fraud@bad.com", ip="1.2.3.4")
    assert action == "block"


def test_custom_rule_conditions():
    rules = CustomRuleEngine()
    rule = RuleDefinition(
        name="High value VPN", action="hold", priority=10,
        conditions={"order_total_gt": 500, "vpn_detected": True, "first_time_customer": True},
    )
    rules.add_rule(rule)
    action = rules.evaluate_signals(
        signals_dict={"vpn_detected": True, "first_time_customer": True},
        order_total=600.0, email="test@test.com", ip="1.2.3.4",
    )
    assert action == "hold"
