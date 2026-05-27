# trading/regime_detection.py

def detect_regime(volatility, price_change):
    if volatility > 0.04:
        return "volatile_trend" if abs(price_change) >= 0.002 else "panic"
    if abs(price_change) < 0.002:
        return "ranging"
    return "trending"
