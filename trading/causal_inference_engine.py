import numpy as np
from typing import Dict, List, Any
from loguru import logger

class CausalInferenceEngine:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Causal Inference Engine initialized")

    async def analyze(self,
                      features: Dict,
                      outcomes: List[float]) -> Dict[str, Any]:

        causal_scores = {}

        for key, value in features.items():

            try:
                arr = np.array(outcomes)

                feat = np.full(len(arr), float(value))

                corr = np.corrcoef(feat, arr)[0, 1]

                if np.isnan(corr):
                    corr = 0

                causal_scores[key] = float(corr)

            except:
                pass

        strongest = max(
            causal_scores,
            key=causal_scores.get
        ) if causal_scores else None

        return {
            "causal_scores": causal_scores,
            "strongest_factor": strongest
        }
