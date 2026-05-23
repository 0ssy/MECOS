"""
Portfolio-Level Intelligence
Position sizing, correlation, risk aggregation
"""
import numpy as np
from typing import Dict, Any, List
from loguru import logger

class PortfolioEngine:
    """Manages portfolio-level intelligence"""
    
    def __init__(self, memory):
        self.memory = memory
        self.max_position_size = 0.20  # Max 20% per position
        self.max_sector_exposure = 0.40  # Max 40% per sector
        self.target_volatility = 0.15  # 15% annual vol target
        logger.info("Portfolio Engine initialized")
    
    async def optimize_position_size(self, 
                                    signal_strength: float,
                                    portfolio: Dict,
                                    volatility: float) -> float:
        """Kelly Criterion + volatility targeting"""
        
        # Kelly Criterion: f* = (bp - q) / b
        # Where: b = odds, p = win probability, q = loss probability
        
        # Estimate win probability from signal strength
        win_prob = 0.5 + (signal_strength * 0.3)  # 0.5 to 0.8 range
        win_prob = np.clip(win_prob, 0.4, 0.9)
        
        # Assume 1:1 risk/reward for simplicity
        odds = 1.0
        
        # Kelly fraction
        kelly_fraction = (odds * win_prob - (1 - win_prob)) / odds
        kelly_fraction = np.clip(kelly_fraction, 0, 0.25)  # Cap at 25%
        
        # Volatility adjustment (inverse volatility weighting)
        vol_scalar = self.target_volatility / max(volatility, 0.01)
        vol_scalar = np.clip(vol_scalar, 0.5, 2.0)
        
        # Final position size
        position_size = kelly_fraction * vol_scalar
        position_size = min(position_size, self.max_position_size)
        
        return float(position_size)
    
    async def calculate_portfolio_metrics(self, portfolio: Dict) -> Dict[str, Any]:
        """Calculate portfolio-level risk metrics"""
        
        total_value = portfolio.get('total_value', 10000)
        positions = portfolio.get('positions', {})
        
        if not positions:
            return {
                "total_exposure": 0,
                "num_positions": 0,
                "concentration_risk": 0,
                "largest_position": 0,
                "portfolio_beta": 1.0
            }
        
        # Calculate exposures
        exposures = [pos.get('value', 0) for pos in positions.values()]
        total_exposure = sum(exposures) / total_value if total_value > 0 else 0
        
        # Concentration (Herfindahl index)
        sum_exp = sum(exposures)
        weights = [exp / sum_exp for exp in exposures if sum_exp > 0]
        concentration = sum([w**2 for w in weights]) if weights else 0
        
        return {
            "total_exposure": float(total_exposure),
            "num_positions": len(positions),
            "concentration_risk": float(concentration),
            "largest_position": float(max(exposures) / total_value) if exposures and total_value > 0 else 0,
            "portfolio_beta": 1.0  # Placeholder
        }
