# trading/confidence_calibrator.py
import math


class ConfidenceCalibrator:
    def __init__(self, half_life_seconds: float = 20.0, baseline_decay: float = 0.995):
        self.half_life_seconds = max(float(half_life_seconds), 1.0)
        self.baseline_decay = float(min(max(baseline_decay, 0.90), 1.0))

    def calibrate(self, raw_confidence: float, age_seconds: float = 0.0):
        confidence = float(min(max(raw_confidence, 0.0), 1.0)) * self.baseline_decay
        if age_seconds <= 0.0:
            return confidence
        decay_rate = math.log(2.0) / self.half_life_seconds
        return float(min(max(confidence * math.exp(-decay_rate * float(age_seconds)), 0.0), 1.0))
