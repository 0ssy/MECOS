import time

# Asset-class-aware cooldown periods (reduced for paper trading/testing)
COOLDOWN_BY_CLASS = {
    "crypto":      15,    # Crypto: 15 seconds
    "index":       30,    # ETFs: 30 seconds
    "technology":  30,    # Tech stocks: 30 seconds
    "equity":      30,    # Default equity: 30 seconds
    "small_cap":   30,    # Small caps: 30 seconds
    "default":     30,
}

# Symbol-level overrides (reduced for testing)
SYMBOL_COOLDOWNS = {
    "BTC/USD":  15,
    "ETH/USD":  15,
    "SOL/USD":  15,
    "SPY":      30,
    "QQQ":      30,
    "IWM":      30,
}


class CooldownManager:
    def __init__(self):
        self.cooldowns = {}

    def _get_cooldown(self, symbol: str, sector: str = "default") -> int:
        if symbol in SYMBOL_COOLDOWNS:
            return SYMBOL_COOLDOWNS[symbol]
        return COOLDOWN_BY_CLASS.get(sector, COOLDOWN_BY_CLASS["default"])

    def can_trade(self, symbol: str, cooldown_seconds: int = None, sector: str = "default") -> bool:
        now = time.time()
        last_trade = self.cooldowns.get(symbol)
        if last_trade is None:
            return True
        effective_cooldown = cooldown_seconds if cooldown_seconds is not None else self._get_cooldown(symbol, sector)
        return (now - last_trade) > effective_cooldown

    def record_trade(self, symbol: str):
        self.cooldowns[symbol] = time.time()

    def time_since_trade(self, symbol: str) -> float:
        last = self.cooldowns.get(symbol)
        return (time.time() - last) if last else float("inf")
