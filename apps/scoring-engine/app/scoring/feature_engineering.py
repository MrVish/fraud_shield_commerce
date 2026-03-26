import numpy as np
from app.scoring.signals import ExtractedSignals

FEATURE_NAMES = [
    "avs_mismatch", "cvv_failure", "card_country_mismatch",
    "first_time_customer", "item_count",
    "address_mismatch", "vpn_detected", "ip_country_mismatch", "tor_detected",
    "order_value_deviation", "high_value_order",
    "disposable_email", "free_email_provider", "invalid_email_format",
    "phone_invalid", "voip_phone",
]


class FeatureEngineer:
    def __init__(self):
        self._feature_names = FEATURE_NAMES

    def feature_names(self) -> list[str]:
        return self._feature_names.copy()

    def feature_count(self) -> int:
        return len(self._feature_names)

    def transform(self, signals: ExtractedSignals) -> np.ndarray:
        signal_map = {s.name: s.value for s in signals.all_signals()}
        vector = []
        for name in self._feature_names:
            raw = signal_map.get(name, 0)
            vector.append(self._encode(raw))
        return np.array(vector, dtype=np.float32)

    def _encode(self, value: object) -> float:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            return float(value)
        return 0.0
