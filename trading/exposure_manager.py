# trading/exposure_manager.py

SECTOR_LIMITS = {
    'tech': 0.40,
    'crypto': 0.25,
}

class ExposureManager:
    def __init__(self):
        self.sector_exposure = {}

    def update_exposure(self, symbol, sector, notional):
        self.sector_exposure.setdefault(sector, 0.0)
        self.sector_exposure[sector] += notional

    def can_add(self, sector, notional, portfolio_value):
        max_exposure = SECTOR_LIMITS.get(sector, 1.0)
        current = self.sector_exposure.get(sector, 0.0)
        return (current + notional) / portfolio_value <= max_exposure

    def reset(self):
        self.sector_exposure = {}
