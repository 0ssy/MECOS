from __future__ import annotations


class PersonaEngine:
    PERSONAS = {
        "Buffett": "Focus on intrinsic value, long-term fundamentals, and margin of safety.",
        "Simons": "Focus on high-frequency patterns, statistical arbitrage, and quantitative signals.",
        "Dalio": "Focus on macro cycles, debt levels, and diversification across asset classes.",
    }

    def get_prompt_injection(self, asset_type: str) -> str:
        token = str(asset_type or "").strip().lower()
        if token == "equity":
            return self.PERSONAS["Buffett"]
        if token == "crypto":
            return self.PERSONAS["Simons"]
        return self.PERSONAS["Dalio"]
