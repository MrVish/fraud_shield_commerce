import os
import numpy as np
import joblib


class FraudMLModel:
    def __init__(self, model_path: str | None = None):
        self.model = None
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)

    def predict(self, feature_vector: np.ndarray) -> float:
        if self.model is None:
            return float(min(100.0, max(0.0, feature_vector.sum() * 12.0)))
        vector_2d = feature_vector.reshape(1, -1)
        probability = self.model.predict_proba(vector_2d)[0][1]
        return float(round(probability * 100, 1))

    def is_loaded(self) -> bool:
        return self.model is not None
