from typing import Dict, List, Any, Set
from loguru import logger
from datetime import datetime
import numpy as np
from .asset_profiles import get_asset_profile

# Asset Universe Definitions
MEGA_CAP_TECH = [
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN',
    'META', 'TSLA', 'AMD', 'NFLX', 'AVGO'
]

SEMICONDUCTORS = [
    'NVDA', 'AMD', 'INTC', 'MU', 'QCOM',
    'ASML', 'TSM', 'AMAT', 'LRCX', 'KLAC'
]

BANKS = [
    'JPM', 'BAC', 'GS', 'MS', 'WFC',
    'C', 'SCHW', 'AXP'
]

ENERGY = [
    'XOM', 'CVX', 'COP', 'SLB',
    'EOG', 'MPC', 'PSX'
]

HEALTHCARE = [
    'UNH', 'JNJ', 'PFE', 'ABBV',
    'MRK', 'LLY', 'TMO'
]

DEFENSIVE = [
    'KO', 'PEP', 'PG', 'WMT',
    'COST', 'MCD'
]

INDUSTRIALS = [
    'CAT', 'BA', 'GE', 'HON',
    'UPS', 'RTX'
]

ETFS = [
    'SPY', 'QQQ', 'IWM', 'DIA',
    'XLF', 'XLK', 'XLE', 'XLV',
    'XLI', 'ARKK', 'SMH', 'SOXX'
]

CRYPTO = [
    'BTC/USD', 'ETH/USD', 'SOL/USD',
    'AVAX/USD', 'LINK/USD', 'DOGE/USD', 'ADA/USD'
]

FOREX = [
    'EUR/USD', 'GBP/USD', 'USD/JPY',
    'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD'
]

COMMODITIES = [
    'GLD', 'SLV', 'USO', 'UNG', 'DBA'
]

class UniverseManager:
    def __init__(self, memory_system):
        self.memory = memory_system
        
        self.universe = {
            'stocks': {
                'mega_cap_tech': MEGA_CAP_TECH,
                'semiconductors': SEMICONDUCTORS,
                'banks': BANKS,
                'energy': ENERGY,
                'defensive': DEFENSIVE,
                'healthcare': HEALTHCARE,
                'industrials': INDUSTRIALS
            },
            'etfs': ETFS,
            'crypto': CRYPTO,
            'forex': FOREX,
            'commodities': COMMODITIES
        }
        
        self.active_universe = set()
        
        self.filters = {
            'min_price': 5.0,
            'min_volume': 1000000,
            'max_spread': 0.005,
            'min_liquidity_score': 0.3
        }
        
        self.regime_preferences = {
            'trending': {
                'sectors': ['mega_cap_tech', 'semiconductors', 'energy'],
                'asset_classes': ['stocks', 'crypto'],
                'weight': 1.5
            },
            'ranging': {
                'sectors': ['banks', 'defensive', 'industrials'],
                'asset_classes': ['etfs', 'forex'],
                'weight': 1.3
            },
            'volatile_trend': {
                'sectors': ['semiconductors', 'energy'],
                'asset_classes': ['crypto', 'commodities'],
                'weight': 1.4
            },
            'panic': {
                'sectors': ['healthcare', 'defensive'],
                'asset_classes': ['etfs', 'commodities'],
                'weight': 1.2
            }
        }
        
        self.rotation_config = {
            'max_stocks': 28,
            'max_etfs': 8,
            'max_crypto': 5,
            'max_forex': 4,
            'max_commodities': 2,
            'rotation_frequency': 3600
        }
        
        self.last_rotation = None
        
        logger.info('Universe Manager initialized')
        logger.info(f'Total universe size: {self.get_total_universe_size()}')

    def get_total_universe_size(self) -> int:
        total = 0
        for category in self.universe.values():
            if isinstance(category, dict):
                for subcategory in category.values():
                    total += len(subcategory)
            else:
                total += len(category)
        return total

    def load_starter_universe(self) -> List[str]:
        '''Load recommended initial universe for validation'''
        
        starter = []
        
        starter.extend(['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'META'])
        
        starter.extend(['SPY', 'QQQ', 'IWM'])
        
        starter.extend(['BTC/USD', 'ETH/USD', 'SOL/USD'])
        
        self.active_universe = set(starter)
        
        logger.info(f'Loaded starter universe: {len(starter)} assets')
        logger.info(f'Stocks: 6 | ETFs: 3 | Crypto: 3')
        
        return starter

    def load_default_universe(self) -> List[str]:
        '''Load full default universe (all assets)'''
        
        all_assets = []
        seen = set()
        
        for category in self.universe.values():
            if isinstance(category, dict):
                for subcategory in category.values():
                    all_assets.extend(subcategory)
            else:
                all_assets.extend(category)

        unique_assets = []
        for symbol in all_assets:
            if symbol in seen:
                continue
            seen.add(symbol)
            unique_assets.append(symbol)
        
        self.active_universe = set(unique_assets)
        
        logger.info(f'Loaded full universe: {len(unique_assets)} assets')
        
        return unique_assets

    def get_regime_optimized_universe(self, 
                                     current_regime: str,
                                     market_conditions: Dict[str, Any]) -> List[str]:
        '''Select assets dynamically based on market regime'''
        
        if current_regime not in self.regime_preferences:
            logger.warning(f'Unknown regime: {current_regime}, using full universe')
            return self.load_default_universe()
        
        regime_config = self.regime_preferences[current_regime]
        selected = []
        
        preferred_sectors = regime_config.get('sectors', [])
        for sector in preferred_sectors:
            if sector in self.universe['stocks']:
                sector_assets = self.universe['stocks'][sector]
                
                count = min(len(sector_assets), self.rotation_config['max_stocks'] // len(preferred_sectors))
                selected.extend(sector_assets[:count])
        
        preferred_classes = regime_config.get('asset_classes', [])
        
        if 'etfs' in preferred_classes:
            selected.extend(self.universe['etfs'][:self.rotation_config['max_etfs']])
        
        if 'crypto' in preferred_classes:
            selected.extend(self.universe['crypto'][:self.rotation_config['max_crypto']])

        if 'forex' in preferred_classes:
            selected.extend(self.universe['forex'][:self.rotation_config['max_forex']])
        
        if 'commodities' in preferred_classes:
            selected.extend(self.universe['commodities'][:self.rotation_config['max_commodities']])
        
        self.active_universe = set(selected)
        self.last_rotation = datetime.now()
        
        logger.info(f'Regime-optimized universe for {current_regime}: {len(selected)} assets')
        
        return selected

    def filter_by_liquidity(self, 
                           symbol_metrics: Dict[str, Dict],
                           min_volume: int = None) -> List[str]:
        '''Filter assets by liquidity metrics'''
        
        min_vol = min_volume or self.filters['min_volume']
        
        filtered = []
        
        for symbol, metrics in symbol_metrics.items():
            volume = metrics.get('volume', 0)
            spread = metrics.get('spread', 1.0)
            liquidity_score = metrics.get('liquidity_score', 0)
            
            if (volume >= min_vol and 
                spread <= self.filters['max_spread'] and
                liquidity_score >= self.filters['min_liquidity_score']):
                
                filtered.append(symbol)
        
        logger.info(f'Liquidity filter: {len(filtered)}/{len(symbol_metrics)} assets passed')
        
        return filtered

    def filter_by_volatility(self,
                            symbol_metrics: Dict[str, Dict],
                            regime: str) -> List[str]:
        '''Filter assets by volatility regime preference'''
        
        filtered = []
        
        for symbol, metrics in symbol_metrics.items():
            volatility = metrics.get('volatility', 0)
            
            if regime in ['volatile_trend', 'panic']:
                if volatility > 0.02:
                    filtered.append(symbol)
            
            elif regime == 'trending':
                if 0.01 <= volatility <= 0.04:
                    filtered.append(symbol)
            
            else:
                if volatility <= 0.03:
                    filtered.append(symbol)
        
        logger.info(f'Volatility filter ({regime}): {len(filtered)} assets selected')
        
        return filtered

    def rank_by_momentum(self,
                        symbol_metrics: Dict[str, Dict],
                        top_n: int = 20) -> List[str]:
        '''Rank assets by momentum and return top N'''
        
        ranked = []
        
        for symbol, metrics in symbol_metrics.items():
            momentum = metrics.get('momentum', 0)
            ranked.append((symbol, momentum))
        
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        top_symbols = [sym for sym, _ in ranked[:top_n]]
        
        logger.info(f'Momentum ranking: Top {len(top_symbols)} selected')
        
        return top_symbols

    def get_sector_allocation(self) -> Dict[str, int]:
        '''Get current sector allocation in active universe'''
        
        allocation = {
            'mega_cap_tech': 0,
            'semiconductors': 0,
            'banks': 0,
            'energy': 0,
            'defensive': 0,
            'industrials': 0,
            'healthcare': 0,
            'etfs': 0,
            'crypto': 0,
            'forex': 0,
            'commodities': 0
        }
        
        for symbol in self.active_universe:
            for sector, symbols in self.universe['stocks'].items():
                if symbol in symbols:
                    allocation[sector] += 1
                    break
            
            if symbol in self.universe['etfs']:
                allocation['etfs'] += 1
            elif symbol in self.universe['crypto']:
                allocation['crypto'] += 1
            elif symbol in self.universe['forex']:
                allocation['forex'] += 1
            elif symbol in self.universe['commodities']:
                allocation['commodities'] += 1
        
        return allocation

    def get_asset_profile(self, symbol: str) -> Dict[str, Any]:
        return get_asset_profile(symbol)

    def get_active_universe(self) -> List[str]:
        '''Get current active trading universe'''
        return list(self.active_universe)

    def add_symbol(self, symbol: str, category: str = 'custom'):
        '''Add a custom symbol to universe'''
        
        if 'custom' not in self.universe:
            self.universe['custom'] = []
        
        if symbol not in self.universe['custom']:
            self.universe['custom'].append(symbol)
            self.active_universe.add(symbol)
            
            logger.info(f'Added custom symbol: {symbol}')

    def remove_symbol(self, symbol: str):
        '''Remove symbol from active universe'''
        
        if symbol in self.active_universe:
            self.active_universe.remove(symbol)
            logger.info(f'Removed symbol: {symbol}')

    def rotate_universe(self,
                       regime: str,
                       market_metrics: Dict[str, Dict]) -> List[str]:
        '''
        Perform intelligent universe rotation
        
        Steps:
        1. Get regime-optimized base universe
        2. Apply liquidity filters
        3. Apply volatility filters
        4. Rank by momentum
        5. Select top N by rotation config
        '''
        
        if self.last_rotation:
            time_since_rotation = (datetime.now() - self.last_rotation).total_seconds()
            if time_since_rotation < self.rotation_config['rotation_frequency']:
                logger.debug(f'Rotation skipped: {time_since_rotation:.0f}s since last rotation')
                return self.get_active_universe()
        
        logger.info('========================================')
        logger.info('UNIVERSE ROTATION INITIATED')
        logger.info('========================================')
        
        base_universe = self.get_regime_optimized_universe(regime, market_metrics)
        
        liquid_assets = self.filter_by_liquidity(market_metrics)
        
        volatile_assets = self.filter_by_volatility(market_metrics, regime)
        
        candidates = set(base_universe) & set(liquid_assets) & set(volatile_assets)
        
        candidate_metrics = {sym: market_metrics[sym] for sym in candidates if sym in market_metrics}
        
        if candidate_metrics:
            final_universe = self.rank_by_momentum(
                candidate_metrics, 
                top_n=self.rotation_config['max_stocks'] + 
                      self.rotation_config['max_etfs'] + 
                      self.rotation_config['max_crypto']
            )
        else:
            final_universe = list(candidates)
        
        self.active_universe = set(final_universe)
        self.last_rotation = datetime.now()
        
        allocation = self.get_sector_allocation()
        
        logger.info(f'New universe: {len(final_universe)} assets')
        logger.info(f'Sector allocation: {allocation}')
        logger.info('========================================')
        
        return final_universe

    def get_universe_statistics(self) -> Dict[str, Any]:
        '''Get comprehensive universe statistics'''
        
        return {
            'total_universe_size': self.get_total_universe_size(),
            'active_universe_size': len(self.active_universe),
            'sector_allocation': self.get_sector_allocation(),
            'last_rotation': self.last_rotation.isoformat() if self.last_rotation else None,
            'rotation_config': self.rotation_config,
            'filters': self.filters
        }
