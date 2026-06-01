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

    def get_active_personas(self, asset_type: str):
        token = str(asset_type or "").strip().lower()
        if token == "equity":
            return ["Buffett", "Simons", "Dalio"]
        if token == "crypto":
            return ["Simons", "Dalio", "Buffett"]
        if token in {"forex", "commodity_fx"}:
            return ["Dalio", "Soros", "Simons"]
        if token == "macro":
            return ["Dalio", "Buffett", "Simons"]
        return ["Dalio", "Buffett", "Simons"]

    def get_primary_persona(self, asset_type: str) -> str:
        active = self.get_active_personas(asset_type)
        return active[0] if active else "Dalio"

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
