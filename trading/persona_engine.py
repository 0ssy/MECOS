from __future__ import annotations


class PersonaEngine:
    PERSONAS = {
        "Buffett": "Focus on intrinsic value, long-term fundamentals, and margin of safety.",
        "Simons": "Focus on high-frequency patterns, statistical arbitrage, and quantitative signals.",
        "Dalio": "Focus on macro cycles, debt levels, and diversification across asset classes.",
        "Soros": "Focus on currency reflexivity, central bank policy, and macro-economic imbalances.",
    }

    def register_persona(self, name: str, prompt: str) -> None:
        token = str(name or "").strip()
        instruction = str(prompt or "").strip()
        if token and instruction:
            self.PERSONAS[token] = instruction

    def get_personas(self):
        return dict(self.PERSONAS)

    def get_prompt_injection(self, asset_type: str) -> str:
        token = str(asset_type or "").strip().lower()
        if token == "equity":
            return self.PERSONAS["Buffett"]
        if token == "crypto":
            return self.PERSONAS["Simons"]
        if token in {"forex", "commodity_fx"}:
            return self.PERSONAS["Soros"]
        if token == "macro":
            return self.PERSONAS["Dalio"]
        return self.PERSONAS["Dalio"]
