# trading/confidence_calibrator.py

class ConfidenceCalibrator:
    def __init__(self):
        self.decay = 0.98  # placeholder for adaptive decay

    def calibrate(self, raw_confidence):
        # Placeholder: apply decay, later replace with Bayesian/ML
        return max(0.0, min(1.0, raw_confidence * self.decay))
