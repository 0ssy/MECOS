content = open('trading/autonomous_trading_loop.py', 'r').read()

old = '''    async def _poll_stock_prices(self, symbols: list, interval: int = 60):
        import yfinance as yf
        stock_symbols = [s for s in symbols if "/" not in s]
        if not stock_symbols:
            return
        logger.info(f"Stock polling started for {len(stock_symbols)} symbols")
        while self.running:
            for symbol in stock_symbols:
                try:
                    def _yf_fetch_poll(sym):
                        import yfinance as yf
                        return yf.Ticker(sym).history(period="1d", interval="1m", auto_adjust=True, timeout=10)
                    df = await asyncio.to_thread(_yf_fetch_poll, symbol)
                    if df.empty:
                        continue
                    row   = df.iloc[-1]
                    close = float(row.get("Close", 0) or 0)
                    if close <= 0:
                        continue
                    await self.market_stream.emit_market_data(symbol, {
                        "symbol":    symbol,
                        "open":      float(row.get("Open",   close) or close),
                        "close":     close,
                        "high":      float(row.get("High",   close) or close),
                        "low":       float(row.get("Low",    close) or close),
                        "volume":    float(row.get("Volume", 1)     or 1),
                        "timestamp": str(df.index[-1]),
                    })
                except Exception as e:
                    logger.debug(f"Stock poll failed for {symbol}: {e}")
            await asyncio.sleep(interval)'''

new = '''    async def _poll_stock_prices(self, symbols: list, interval: float = 60):
        import yfinance as yf
        stock_symbols = [s for s in symbols if "/" not in s]
        crypto_symbols = [s for s in symbols if "/" in s]
        if stock_symbols:
            logger.info(f"Stock polling started for {len(stock_symbols)} symbols")
        if crypto_symbols:
            logger.info(f"Crypto polling started for {len(crypto_symbols)} symbols: {crypto_symbols}")
        while self.running:
            for symbol in stock_symbols:
                try:
                    def _yf_fetch_poll(sym):
                        import yfinance as yf
                        return yf.Ticker(sym).history(period="1d", interval="1m", auto_adjust=True, timeout=10)
                    df = await asyncio.to_thread(_yf_fetch_poll, symbol)
                    if df.empty:
                        continue
                    row   = df.iloc[-1]
                    close = float(row.get("Close", 0) or 0)
                    if close <= 0:
                        continue
                    await self.market_stream.emit_market_data(symbol, {
                        "symbol":    symbol,
                        "open":      float(row.get("Open",   close) or close),
                        "close":     close,
                        "high":      float(row.get("High",   close) or close),
                        "low":       float(row.get("Low",    close) or close),
                        "volume":    float(row.get("Volume", 1)     or 1),
                        "timestamp": str(df.index[-1]),
                    })
                except Exception as e:
                    logger.debug(f"Stock poll failed for {symbol}: {e}")
            for symbol in crypto_symbols:
                try:
                    yf_symbol = symbol.replace("/", "-")
                    df = yf.Ticker(yf_symbol).history(period="1d", interval="1m", auto_adjust=True, timeout=10)
                    if df.empty:
                        continue
                    row   = df.iloc[-1]
                    close = float(row.get("Close", 0) or 0)
                    if close <= 0:
                        continue
                    await self.market_stream.emit_market_data(symbol, {
                        "symbol":    symbol,
                        "open":      float(row.get("Open",   close) or close),
                        "close":     close,
                        "high":      float(row.get("High",   close) or close),
                        "low":       float(row.get("Low",    close) or close),
                        "volume":    float(row.get("Volume", 1)     or 1),
                        "timestamp": str(df.index[-1]),
                    })
                except Exception as e:
                    logger.debug(f"Crypto poll failed for {symbol}: {e}")
            await asyncio.sleep(interval)'''

if old in content:
    content = content.replace(old, new)
    open('trading/autonomous_trading_loop.py', 'w').write(content)
    print("Modified successfully")
else:
    print("Pattern not found")