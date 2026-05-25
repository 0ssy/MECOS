import asyncio
import os
from datetime import datetime
from loguru import logger

from memory_system import MemorySystem
from trading.trade_database import TradeDatabase
from trading.trading_agent import TradingAgent
from trading.market_data_stream import MarketDataStream
from trading.live_signal_generator import LiveSignalGenerator
from trading.position_manager import PositionManager
from trading.risk_monitor import RiskMonitor
from trading.performance_monitor import PerformanceMonitor
from trading.paper_trading_executor import PaperTradingExecutor
from trading.universe_manager import UniverseManager
from trading.universe_scanner import UniverseScanner
from trading.autonomous_trading_loop import AutonomousTradingLoop
from trading.broker.multi_broker_adapter import MultiBrokerAdapter


async def run_burn_in(
    duration_hours: float = 24.0,
    use_starter_universe: bool = True,
    quant_mode: str | None = None,
):
    logger.info('=== MECOS 24H PAPER TRADING BURN-IN ===')

    mode = (quant_mode or os.getenv('MECOS_QUANT_MODE', 'balanced')).strip()
    logger.info(f'Quant mode selected: {mode}')

    memory = MemorySystem()
    db = TradeDatabase()
    agent = TradingAgent(memory, quant_mode=mode)
    stream = MarketDataStream()

    stream.set_broker_adapter(MultiBrokerAdapter())
    logger.info('Live adapter configured (MultiBroker: IBKR/Alpaca/Binance)')

    signal_gen = LiveSignalGenerator(agent, stream, memory)
    pos_mgr = PositionManager(db)
    risk_mon = RiskMonitor()
    perf_mon = PerformanceMonitor(db)
    executor = PaperTradingExecutor(db, pos_mgr, risk_mon, memory)
    universe_mgr = UniverseManager(memory)
    scanner = UniverseScanner(universe_mgr, stream)

    loop = AutonomousTradingLoop(
        stream,
        signal_gen,
        executor,
        perf_mon,
        db,
        universe_mgr,
        scanner,
        quant_mode=mode,
    )

    worker = asyncio.create_task(loop.start(use_starter_universe=use_starter_universe))
    started_at = datetime.now()
    max_seconds = max(1.0, duration_hours * 3600.0)

    try:
        while (datetime.now() - started_at).total_seconds() < max_seconds:
            await asyncio.sleep(60)
            status = loop.get_status()
            logger.info(
                'Burn-in heartbeat | signals=%s trades=%s rejected=%s sharpe=%.2f max_dd=%.2f%% win_rate=%.2f%% exposure=%s',
                status['signal_stats'].get('total_signals', 0),
                status['account'].get('executed_orders', 0),
                status['account'].get('rejected_orders', 0),
                status['performance'].get('sharpe_ratio', 0.0),
                status['performance'].get('max_drawdown', 0.0) * 100,
                status['performance'].get('win_rate', 0.0) * 100,
                status.get('exposure_by_sector', {}),
            )
    finally:
        loop.stop()
        if not worker.done():
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

    final_status = loop.get_status()
    trade_summary = db.get_trade_summary()

    logger.info('=== BURN-IN COMPLETE ===')
    logger.info(f'Total signals: {final_status["signal_stats"].get("total_signals", 0)}')
    logger.info(f'Executed trades: {final_status["account"].get("executed_orders", 0)}')
    logger.info(f'Rejected trades: {final_status["account"].get("rejected_orders", 0)}')
    logger.info(f'Win rate: {final_status["performance"].get("win_rate", 0):.2%}')
    logger.info(f'Max drawdown: {final_status["performance"].get("max_drawdown", 0):.2%}')
    logger.info(f'Sharpe ratio: {final_status["performance"].get("sharpe_ratio", 0):.2f}')
    logger.info(f'Profit factor: {final_status["performance"].get("profit_factor", 0):.2f}')
    logger.info(f'Exposure by sector: {final_status.get("exposure_by_sector", {})}')
    logger.info(f'Average holding time (s): {final_status["performance"].get("avg_holding_seconds", 0):.2f}')
    logger.info(f'Trade journal summary: {trade_summary}')


if __name__ == '__main__':
    asyncio.run(run_burn_in())
