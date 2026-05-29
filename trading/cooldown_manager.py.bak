import time

class CooldownManager:
    def __init__(self):
        self.cooldowns = {}

    def can_trade(self, symbol, cooldown_seconds=300):
        now = time.time()
        last_trade = self.cooldowns.get(symbol)
        if last_trade is None:
            return True
        return (now - last_trade) > cooldown_seconds

    def record_trade(self, symbol):
        self.cooldowns[symbol] = time.time()
