from typing import Dict, Any

ASSET_PROFILES: Dict[str, Dict[str, Any]] = {
    'BTC/USD': {'market': 'crypto', 'volatility_multiplier': 3.0, 'trade_24h': True},
    'ETH/USD': {'market': 'crypto', 'volatility_multiplier': 2.5, 'trade_24h': True},
    'SOL/USD': {'market': 'crypto', 'volatility_multiplier': 3.2, 'trade_24h': True},
    'AVAX/USD': {'market': 'crypto', 'volatility_multiplier': 3.4, 'trade_24h': True},
    'LINK/USD': {'market': 'crypto', 'volatility_multiplier': 2.8, 'trade_24h': True},
    'DOGE/USD': {'market': 'crypto', 'volatility_multiplier': 4.0, 'trade_24h': True},
    'ADA/USD': {'market': 'crypto', 'volatility_multiplier': 3.0, 'trade_24h': True},
    'EUR/USD': {'market': 'forex', 'volatility_multiplier': 1.0, 'trade_24h': True},
    'GBP/USD': {'market': 'forex', 'volatility_multiplier': 1.1, 'trade_24h': True},
    'USD/JPY': {'market': 'forex', 'volatility_multiplier': 0.9, 'trade_24h': True},
    'AUD/USD': {'market': 'forex', 'volatility_multiplier': 1.0, 'trade_24h': True},
    'USD/CAD': {'market': 'forex', 'volatility_multiplier': 0.9, 'trade_24h': True},
    'USD/CHF': {'market': 'forex', 'volatility_multiplier': 0.8, 'trade_24h': True},
    'NZD/USD': {'market': 'forex', 'volatility_multiplier': 1.1, 'trade_24h': True},
    'XAU/USD': {'market': 'commodity_fx', 'volatility_multiplier': 1.8, 'trade_24h': True},
}

_FOREX_QUOTES = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD'}


def infer_market(symbol: str) -> str:
    profile = ASSET_PROFILES.get(symbol)
    if profile:
        return profile.get('market', 'equity')

    if '/' in symbol:
        base, quote = symbol.split('/', 1)
        if quote in _FOREX_QUOTES and base in _FOREX_QUOTES:
            return 'forex'
        return 'crypto'

    return 'equity'


def get_asset_profile(symbol: str) -> Dict[str, Any]:
    market = infer_market(symbol)
    default_profile = {
        'market': market,
        'volatility_multiplier': 1.0 if market in {'equity', 'forex'} else 2.0,
        'trade_24h': market in {'crypto', 'forex', 'commodity_fx'},
    }
    profile = ASSET_PROFILES.get(symbol, {})
    return {**default_profile, **profile}


# ---------------------------------------------------------------------------
# Sector mapping for exposure manager
# ---------------------------------------------------------------------------
SECTOR_MAP: Dict[str, str] = {
    # Mega-cap tech
    'AAPL':  'technology',
    'MSFT':  'technology',
    'GOOGL': 'technology',
    'GOOG':  'technology',
    'META':  'technology',
    'AMZN':  'technology',
    'NFLX':  'technology',
    'ADBE':  'technology',
    'CRM':   'technology',
    'ORCL':  'technology',
    # Semiconductors
    'NVDA':  'semiconductors',
    'AMD':   'semiconductors',
    'INTC':  'semiconductors',
    'QCOM':  'semiconductors',
    'AVGO':  'semiconductors',
    'MU':    'semiconductors',
    'AMAT':  'semiconductors',
    'LRCX':  'semiconductors',
    # Indices / ETFs
    'SPY':   'index',
    'QQQ':   'index',
    'DIA':   'index',
    'VTI':   'index',
    'VOO':   'index',
    'IVV':   'index',
    'IWM':   'small_cap',
    'VXX':   'volatility',
    # Automotive / EV
    'TSLA':  'automotive',
    'F':     'automotive',
    'GM':    'automotive',
    'RIVN':  'automotive',
    'LCID':  'automotive',
    # Finance
    'JPM':   'financials',
    'BAC':   'financials',
    'GS':    'financials',
    'MS':    'financials',
    'WFC':   'financials',
    'V':     'financials',
    'MA':    'financials',
    'AXP':   'financials',
    # Healthcare
    'JNJ':   'healthcare',
    'PFE':   'healthcare',
    'MRNA':  'healthcare',
    'UNH':   'healthcare',
    'ABBV':  'healthcare',
    'LLY':   'healthcare',
    # Energy
    'XOM':   'energy',
    'CVX':   'energy',
    'COP':   'energy',
    # Consumer
    'WMT':   'consumer',
    'COST':  'consumer',
    'TGT':   'consumer',
    'HD':    'consumer',
    'MCD':   'consumer',
    'SBUX':  'consumer',
    'NKE':   'consumer',
    # Crypto (symbol variants)
    'BTC/USD':  'crypto',
    'ETH/USD':  'crypto',
    'SOL/USD':  'crypto',
    'AVAX/USD': 'crypto',
    'LINK/USD': 'crypto',
    'DOGE/USD': 'crypto',
    'ADA/USD':  'crypto',
    'BTC/USDT': 'crypto',
    'ETH/USDT': 'crypto',
    'SOL/USDT': 'crypto',
}


def get_sector(symbol: str) -> str:
    """
    Return the sector for a symbol.
    Falls back to infer_market() so it never returns 'unknown'.
    """
    token = str(symbol or '').upper().strip()
    if token in SECTOR_MAP:
        return SECTOR_MAP[token]
    # Infer from symbol structure
    market = infer_market(token)
    if market == 'equity':
        return 'equity'
    return market  # crypto / forex / commodity_fx
