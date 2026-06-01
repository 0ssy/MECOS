"""
MECOS Live Trading Entry Point
Run with:
    python run_live_trading.py              # paper mode (default)
    python run_live_trading.py --live       # real money (requires TRADING_ENABLED=true in .env)
    python run_live_trading.py --once       # single cycle then exit (good for testing)
    python run_live_trading.py --backtest   # run indicator logic on historical data, no orders
"""
import asyncio
import sys
from loguru import logger
from config import settings
from memory_system import MemorySystem
from trading_agent import TradingAgent


def _print_status_banner():
    mode = settings.ALPACA_MODE.upper()
    testnet = "TESTNET" if settings.BINANCE_TESTNET else "LIVE"
    enabled = "✅ ENABLED" if settings.TRADING_ENABLED else "🔒 BLOCKED (kill-switch)"

    print("\n" + "=" * 60)
    print(f"  MECOS Trading Engine")
    print(f"  Alpaca mode  : {mode}")
    print(f"  Binance mode : {testnet}")
    print(f"  Order execution: {enabled}")
    print(f"  Max position : ${settings.MAX_POSITION_SIZE_USD}")
    print(f"  Daily loss limit: ${settings.MAX_DAILY_LOSS_USD}")
    print("=" * 60 + "\n")


async def run(once: bool = False, backtest: bool = False):
    _print_status_banner()

    if "--live" in sys.argv:
        if not settings.TRADING_ENABLED:
            print(
                "ERROR: --live flag given but TRADING_ENABLED is not true in your .env\n"
                "Set TRADING_ENABLED=true in .env to enable real orders."
            )
            sys.exit(1)
        print("⚠️  LIVE MODE — real orders may be placed. Press Ctrl-C within 5s to abort.")
        await asyncio.sleep(5)

    memory = MemorySystem()
    agent = TradingAgent(memory)

    if backtest:
        logger.info("Backtest mode: running signal generation only (no orders)")
        result = await agent.run_cycle()
        print(f"\nBacktest complete: {result}")
        return

    if once:
        logger.info("Single-cycle mode")
        result = await agent.run_cycle()
        metrics = agent.get_performance_metrics()
        print(f"\nCycle result  : {result}")
        print(f"Metrics       : {metrics}")
        return

    # Continuous loop
    logger.info(f"Entering trading loop (cycle every {settings.IDLE_SLEEP_TIME}s)")
    cycle = 0
    while True:
        cycle += 1
        logger.info(f"=== Trading Cycle #{cycle} ===")
        try:
            result = await agent.run_cycle()
            metrics = agent.get_performance_metrics()
            logger.info(f"Cycle #{cycle} done | signals={result['signals']} "
                        f"actionable={result['actionable']} | "
                        f"daily_pnl=${metrics['daily_pnl']:.2f}")
        except Exception as e:
            logger.error(f"Cycle #{cycle} error: {e}")

        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


if __name__ == "__main__":
    once_mode = "--once" in sys.argv
    backtest_mode = "--backtest" in sys.argv
    try:
        asyncio.run(run(once=once_mode, backtest=backtest_mode))
    except KeyboardInterrupt:
        print("\nTrading engine stopped.")

