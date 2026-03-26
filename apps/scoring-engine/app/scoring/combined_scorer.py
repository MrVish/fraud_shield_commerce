from dataclasses import dataclass, field
from app.scoring.signals import ExtractedSignals
from app.scoring.rule_engine import RuleBasedScorer
from app.scoring.ml_model import FraudMLModel
from app.scoring.feature_engineering import FeatureEngineer


@dataclass
class FinalScore:
    final_score: int
    risk_level: str
    recommendation: str
    rule_score: float
    ml_score: float
    signal_contributions: list[dict] = field(default_factory=list)
    custom_rule_action: str | None = None


class CombinedScorer:
    def __init__(self, rule_weight: float = 0.5, ml_weight: float = 0.5,
                 model_path: str | None = None, thresholds: dict | None = None):
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight
        self.rule_scorer = RuleBasedScorer(thresholds=thresholds)
        self.ml_model = FraudMLModel(model_path=model_path)
        self.feature_engineer = FeatureEngineer()

    def score(self, signals: ExtractedSignals) -> FinalScore:
        rule_result = self.rule_scorer.score(signals)
        feature_vector = self.feature_engineer.transform(signals)
        ml_score = self.ml_model.predict(feature_vector)

        if self.ml_model.is_loaded():
            combined = (rule_result.score * self.rule_weight) + (ml_score * self.ml_weight)
        else:
            combined = float(rule_result.score)

        final_score = max(0, min(100, int(round(combined))))
        risk_level = self.rule_scorer._classify(final_score)
        recommendation = self.rule_scorer._recommend(risk_level)

        return FinalScore(
            final_score=final_score, risk_level=risk_level, recommendation=recommendation,
            rule_score=float(rule_result.score), ml_score=ml_score,
            signal_contributions=rule_result.signal_contributions,
        )
