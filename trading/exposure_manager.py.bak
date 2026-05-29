# trading/exposure_manager.py

SECTOR_LIMITS = {
    'tech': 0.40,
    'crypto': 0.25,
}

CORRELATION_CLUSTERS = [
    {'SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'META', 'GOOGL', 'AMZN'},
]


class ExposureManager:
    def __init__(self):
        self.sector_exposure = {}
        self.symbol_exposure = {}

    def update_exposure(self, symbol, sector, notional):
        self.sector_exposure.setdefault(sector, 0.0)
        self.sector_exposure[sector] += notional
        self.symbol_exposure[symbol] = self.symbol_exposure.get(symbol, 0.0) + notional

    def _cluster_for_symbol(self, symbol):
        token = str(symbol or '').upper()
        for cluster in CORRELATION_CLUSTERS:
            if token in cluster:
                return cluster
        return set()

    def can_add(
        self,
        sector,
        notional,
        portfolio_value,
        symbol=None,
        max_correlated_positions=3,
        max_sector_exposure=None,
    ):
        max_exposure = float(max_sector_exposure) if max_sector_exposure is not None else SECTOR_LIMITS.get(sector, 1.0)
        current = self.sector_exposure.get(sector, 0.0)
        if (current + notional) / max(portfolio_value, 1.0) > max_exposure:
            return False

        cluster = self._cluster_for_symbol(symbol)
        if not cluster:
            return True

        correlated_open = 0
        for corr_symbol in cluster:
            exposure = self.symbol_exposure.get(corr_symbol, 0.0)
            if exposure > 0.0:
                correlated_open += 1

        symbol_token = str(symbol or '').upper()
        if symbol_token not in self.symbol_exposure:
            correlated_open += 1
        return correlated_open <= int(max_correlated_positions)

    def reset(self):
        self.sector_exposure = {}
        self.symbol_exposure = {}
