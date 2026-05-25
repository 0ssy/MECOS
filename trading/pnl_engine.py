# trading/pnl_engine.py

class PnLEngine:
    def __init__(self):
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0

    def update_realized(self, pnl):
        self.realized_pnl += float(pnl or 0.0)

    def update_unrealized(self, positions, prices):
        total = 0.0
        for sym, pos in (positions or {}).items():
            if sym not in (prices or {}):
                continue
            size = float(pos.get('size', 0.0) or 0.0)
            entry = float(pos.get('entry', pos.get('avg_price', 0.0)) or 0.0)
            mark = float(prices.get(sym, 0.0) or 0.0)
            if size == 0.0 or entry <= 0.0 or mark <= 0.0:
                continue
            total += size * (mark - entry)
        self.unrealized_pnl = float(total)

    def total_pnl(self):
        return float(self.realized_pnl + self.unrealized_pnl)
