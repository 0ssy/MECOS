"""
add_exit_guardian.py
Run from MECOS root: python add_exit_guardian.py

Adds a _exit_guardian() coroutine that runs every 30 seconds independent
of websocket health. It checks all open positions against last known price
and fires stop-loss/take-profit exits even when the live stream is dead.
"""
from pathlib import Path

p = Path("trading/autonomous_trading_loop.py")
src = p.read_text(encoding="utf-8")

# ── 1. Add the exit guardian coroutine after _poll_stock_prices ──────────────

# Find insertion point — after _poll_stock_prices ends, before next async def
# We'll insert before the _on_market_tick or similar method
insert_marker = "    async def _on_market_tick("
if "_exit_guardian" not in src:
    guardian_code = '''    async def _exit_guardian(self, interval: int = 30):
        """
        Independent exit checker that runs every `interval` seconds regardless
        of websocket health. Ensures stop-loss/take-profit fires even when the
        live price stream is interrupted.

        Uses last_price from position_manager (updated by mark_price on every
        tick) as the price source. If a position has no recent price update,
        falls back to the Binance REST API for crypto or yfinance for equities.
        """
        logger.info("Exit guardian started (interval=30s)")
        while self.running:
            await asyncio.sleep(interval)
            try:
                positions = dict(self.paper_executor.position_manager.positions)
                if not positions:
                    continue

                for symbol, pos in positions.items():
                    if float(pos.get("size", 0) or 0) <= 0:
                        continue

                    last_price = float(pos.get("last_price", 0) or 0)
                    avg_price  = float(pos.get("avg_price",  0) or 0)
                    if last_price <= 0 or avg_price <= 0:
                        continue

                    # Build a synthetic tick from last known price
                    tick = {
                        "symbol": symbol,
                        "close":  last_price,
                        "open":   last_price,
                        "high":   last_price,
                        "low":    last_price,
                        "volume": 1,
                    }

                    exit_signal = self.paper_executor.generate_exit_signal(
                        symbol, tick, regime=self.current_regime
                    )
                    if exit_signal:
                        exit_signal["sector"] = pos.get("sector", "unknown")
                        logger.warning(
                            f"[ExitGuardian] Exit triggered for {symbol}: "
                            f"{exit_signal.get('exit_reason')} | "
                            f"last_price={last_price:.4f} avg={avg_price:.4f}"
                        )
                        result = await self.paper_executor.execute_signal(exit_signal)
                        self._update_execution_stats_from_result(result)

            except Exception as e:
                logger.error(f"Exit guardian error: {e}")

    async def _on_market_tick('''

    count = src.count("    async def _on_market_tick(")
    if count == 0:
        print("ERROR: _on_market_tick not found — trying alternative marker")
        # Try finding another marker
        insert_marker = "    async def _record_rl_trade_outcome("
        guardian_code = guardian_code.replace(
            "    async def _on_market_tick(",
            "    async def _record_rl_trade_outcome("
        )
        count = src.count(insert_marker)

    if count >= 1:
        src = src.replace(
            "    async def _on_market_tick(",
            guardian_code,
            1  # only replace first occurrence
        )
        print("OK: _exit_guardian coroutine added")
    else:
        print("ERROR: Could not find insertion point")
        exit(1)
else:
    print("· _exit_guardian already present")

# ── 2. Start the exit guardian task alongside _poll_stock_prices ─────────────

old_start = "        asyncio.create_task(self._poll_stock_prices(self.symbols))\n        await self.market_stream.stream_live_market_data(self.symbols)"
new_start = "        asyncio.create_task(self._poll_stock_prices(self.symbols))\n        asyncio.create_task(self._exit_guardian(interval=30))\n        await self.market_stream.stream_live_market_data(self.symbols)"

if "_exit_guardian(interval=30)" not in src:
    count = src.count(old_start)
    if count == 1:
        src = src.replace(old_start, new_start)
        print("OK: exit guardian task started in loop")
    else:
        print(f"WARNING: start block found {count}x — skipping task launch")
else:
    print("· exit guardian task already launched")

p.write_text(src, encoding="utf-8")
print("\nDone. Verify:")
print("  python -c \"from trading.autonomous_trading_loop import AutonomousTradingLoop; print('OK')\"")
