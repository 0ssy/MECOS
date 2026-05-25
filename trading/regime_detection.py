# trading/regime_detection.py

def detect_regime(volatility, price_change):
    if volatility > 0.04:
        return "high_volatility"
    elif abs(price_change) < 0.002:
        return "range"
    else:
        return "trend"
