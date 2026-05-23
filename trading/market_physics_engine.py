"""
Stochastic Market Physics Models
Black-Scholes, Heston, Monte Carlo, Jump Diffusion
"""
import numpy as np
from scipy.stats import norm
from typing import Dict, Any, List
from loguru import logger

class MarketPhysicsEngine:
    """Mathematical models of market dynamics"""
    
    def __init__(self, memory):
        self.memory = memory
        self.risk_free_rate = 0.05  # 5% annual risk-free rate
        logger.info("Market Physics Engine initialized")
    
    async def analyze(self, symbol: str, data: List[Dict], features: Dict) -> Dict[str, Any]:
        """Comprehensive physics analysis"""
        
        df_data = data[-100:] if len(data) > 100 else data
        current_price = df_data[-1]['close']
        volatility = features.get('realized_volatility', 0.3)
        
        analysis = {}
        
        # 1. BLACK-SCHOLES IMPLIED DYNAMICS
        analysis['black_scholes'] = self._black_scholes_dynamics(
            current_price, volatility
        )
        
        # 2. MONTE CARLO PATH SIMULATION
        analysis['monte_carlo'] = self._monte_carlo_simulation(
            current_price, volatility, days=5, paths=1000
        )
        
        # 3. JUMP DIFFUSION (Merton Model)
        analysis['jump_risk'] = self._jump_diffusion_analysis(
            df_data, volatility
        )
        
        # 4. TAIL RISK ESTIMATION
        analysis['tail_risk'] = self._estimate_tail_risk(
            analysis['monte_carlo']['paths']
        )
        
        return analysis
    
    def _black_scholes_dynamics(self, S: float, sigma: float) -> Dict:
        """Black-Scholes drift-diffusion dynamics"""
        dt = 1/252  # Daily time step
        
        # Expected drift
        drift = self.risk_free_rate * S * dt
        
        # Expected diffusion (volatility component)
        diffusion = sigma * S * np.sqrt(dt)
        
        # Probability distribution parameters
        mean_return = drift
        std_return = diffusion
        
        return {
            "expected_drift": float(drift),
            "diffusion_magnitude": float(diffusion),
            "1d_range_68%": (float(S + mean_return - std_return), float(S + mean_return + std_return)),
            "1d_range_95%": (float(S + mean_return - 2*std_return), float(S + mean_return + 2*std_return))
        }
    
    def _monte_carlo_simulation(self, S0: float, sigma: float, 
                                days: int = 5, paths: int = 1000) -> Dict:
        """Monte Carlo path simulation (Geometric Brownian Motion)"""
        dt = 1/252
        mu = self.risk_free_rate
        
        # Generate random walks
        np.random.seed(42)  # Reproducibility
        Z = np.random.standard_normal((paths, days))
        
        # GBM formula: S_t = S_0 * exp((mu - 0.5*sigma^2)*t + sigma*sqrt(t)*Z)
        cumulative_returns = (mu - 0.5 * sigma**2) * dt * np.arange(1, days+1)
        diffusion = sigma * np.sqrt(dt) * np.cumsum(Z, axis=1)
        
        paths_array = S0 * np.exp(cumulative_returns + diffusion)
        
        # Statistics
        final_prices = paths_array[:, -1]
        
        return {
            "paths": paths_array,
            "mean_final_price": float(np.mean(final_prices)),
            "median_final_price": float(np.median(final_prices)),
            "std_final_price": float(np.std(final_prices)),
            "percentile_5": float(np.percentile(final_prices, 5)),
            "percentile_95": float(np.percentile(final_prices, 95)),
            "prob_profit": float(np.sum(final_prices > S0) / paths),
            "expected_return": float((np.mean(final_prices) - S0) / S0)
        }
    
    def _jump_diffusion_analysis(self, data: List[Dict], sigma: float) -> Dict:
        """Merton Jump-Diffusion Model analysis"""
        closes = np.array([d['close'] for d in data])
        returns = np.diff(np.log(closes + 1e-10))
        
        if len(returns) < 20:
            return {"jump_probability": 0, "jump_magnitude": 0, "expected_jump_impact": 0, "jump_risk_premium": 0}
        
        # Detect jumps (returns > 2.5 standard deviations)
        threshold = 2.5 * np.std(returns)
        jumps = returns[np.abs(returns) > threshold]
        
        jump_prob = len(jumps) / len(returns)
        jump_magnitude = np.mean(np.abs(jumps)) if len(jumps) > 0 else 0
        
        # Expected jump impact over next period
        expected_jump_impact = jump_prob * jump_magnitude
        
        return {
            "jump_probability": float(jump_prob),
            "jump_magnitude": float(jump_magnitude),
            "expected_jump_impact": float(expected_jump_impact),
            "jump_risk_premium": float(jump_prob * jump_magnitude * closes[-1])
        }
    
    def _estimate_tail_risk(self, paths: np.ndarray) -> Dict:
        """Estimate tail risk (VaR, CVaR)"""
        final_prices = paths[:, -1]
        S0 = paths[0, 0]
        
        returns = (final_prices - S0) / S0
        
        # Value at Risk (95%, 99%)
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # Conditional Value at Risk (Expected Shortfall)
        cvar_95 = np.mean(returns[returns <= var_95])
        cvar_99 = np.mean(returns[returns <= var_99])
        
        return {
            "VaR_95": float(var_95),
            "VaR_99": float(var_99),
            "CVaR_95": float(cvar_95),
            "CVaR_99": float(cvar_99),
            "tail_risk_score": float(abs(cvar_99))  # Higher = more tail risk
        }
