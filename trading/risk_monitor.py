
from loguru import logger

class RiskManager:
    def __init__(self):
        # relaxed for simulation warmup
        self.max_drawdown = 0.15
        # per-trade risk
        self.max_position_size = 0.20
        # state
        self.starting_equity = 10000
        self.peak_equity = 10000
        self.kill_switch = False
        self.daily_pnl = 0.0
        self.max_daily_loss = 500.0

    def validate_order(self, portfolio_value, proposed_size):
        if self.kill_switch:
            logger.warning("KILL SWITCH ACTIVE")
            return False

        # update peak
        if portfolio_value > self.peak_equity:
            self.peak_equity = portfolio_value

        # drawdown calculation
        drawdown = (
            self.peak_equity - portfolio_value
        ) / self.peak_equity

        # equity/drawdown logging
        logger.info(
            f"Equity=${portfolio_value:.2f} | "
            f"Peak=${self.peak_equity:.2f} | "
            f"DD={drawdown:.2%}"
        )

        # trigger protection
        if drawdown >= self.max_drawdown:
            logger.error(
                f"RISK BREACH: "
                f"Drawdown {drawdown:.2%}"
            )
            self.kill_switch = True
            return False

        # position size protection
        if proposed_size > self.max_position_size:
            logger.warning(
                f"Position too large: "
                f"{proposed_size:.2%}"
            )
            return False

        return True

    async def check_risk_limits(self, portfolio):
        portfolio_value = float(portfolio.get('total_value', self.starting_equity))
        if not self.validate_order(portfolio_value, 0.0):
            return {'breach': True, 'reason': 'drawdown_limit', 'action': 'HALT_TRADING'}

        if self.daily_pnl <= -abs(self.max_daily_loss):
            self.kill_switch = True
            return {'breach': True, 'reason': 'daily_loss_limit', 'action': 'HALT_TRADING'}

        return {'breach': False}

    async def check_order_risk(self, portfolio, symbol, proposed_notional, current_prices, positions):
        total_value = float(portfolio.get('total_value', self.starting_equity))
        proposed_size = proposed_notional / max(total_value, 1.0)
        if not self.validate_order(total_value, proposed_size):
            return {'breach': True, 'reason': 'order_risk_limit'}

        # Basic concentration cap at 30% notional per asset.
        price = float(current_prices.get(symbol, 0.0))
        current_position = positions.get(symbol, {}) if isinstance(positions, dict) else {}
        current_notional = float(current_position.get('size', 0.0)) * price
        concentration = (current_notional + proposed_notional) / max(total_value, 1.0)
        if concentration > 0.30:
            return {'breach': True, 'reason': 'asset_concentration_limit'}

        return {'breach': False}

    async def update_daily_pnl(self, pnl):
        self.daily_pnl += float(pnl)


# Export for backward compatibility
RiskMonitor = RiskManager
