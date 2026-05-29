import time

# Asset-class-aware cooldown periods
COOLDOWN_BY_CLASS = {
    "crypto":      60,    # Crypto: 1 minute (24/7, fast-moving)
    "index":       120,   # ETFs: 2 minutes
    "technology":  180,   # Tech stocks: 3 minutes
    "equity":      180,   # Default equity: 3 minutes
    "small_cap":   240,   # Small caps: 4 minutes (less liquid)
    "default":     180,
}

# Symbol-level overrides
SYMBOL_COOLDOWNS = {
    "BTC/USD":  60,
    "ETH/USD":  60,
    "SOL/USD":  60,
    "SPY":      90,
    "QQQ":      90,
    "IWM":      120,
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
