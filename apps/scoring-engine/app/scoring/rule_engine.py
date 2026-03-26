from dataclasses import dataclass, field
from app.scoring.signals import ExtractedSignals, Signal


@dataclass
class ScoringResult:
    score: int
    risk_level: str
    recommendation: str
    signal_contributions: list[dict] = field(default_factory=list)


class RuleBasedScorer:
    def __init__(self, thresholds: dict | None = None):
        self.thresholds = thresholds or {"low_max": 30, "medium_max": 60, "high_max": 85}

    def score(self, signals: ExtractedSignals) -> ScoringResult:
        contributions = []
        raw_score = 0.0
        for signal in signals.all_signals():
            points = self._signal_to_points(signal)
            if points > 0:
                contributions.append({
                    "signal_name": signal.name, "finding": str(signal.value),
                    "points_added": round(points, 1), "explanation": signal.explanation,
                    "category": signal.category,
                })
            raw_score += points
        final_score = max(0, min(100, int(round(raw_score))))
        risk_level = self._classify(final_score)
        recommendation = self._recommend(risk_level)
        contributions.sort(key=lambda c: c["points_added"], reverse=True)
        return ScoringResult(score=final_score, risk_level=risk_level,
            recommendation=recommendation, signal_contributions=contributions)

    def _signal_to_points(self, signal: Signal) -> float:
        if isinstance(signal.value, bool):
            return signal.weight if signal.value else 0.0
        elif isinstance(signal.value, (int, float)):
            if signal.name == "order_value_deviation":
                if signal.value > 3.0: return signal.weight
                elif signal.value > 2.0: return signal.weight * 0.6
                elif signal.value > 1.5: return signal.weight * 0.3
                return 0.0
        return 0.0

    def _classify(self, score: int) -> str:
        if score <= self.thresholds["low_max"]: return "low"
        elif score <= self.thresholds["medium_max"]: return "medium"
        elif score <= self.thresholds["high_max"]: return "high"
        return "critical"

    def _recommend(self, risk_level: str) -> str:
        return {"low": "approve", "medium": "review", "high": "hold", "critical": "cancel"}.get(risk_level, "review")
