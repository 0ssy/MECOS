import asyncio
import os
from datetime import datetime
from loguru import logger
from memory_system import MemorySystem
from trading import *
from trading.broker.multi_broker_adapter import MultiBrokerAdapter
from trading.market_data_stream import MarketDataStream
from trading.live_signal_generator import LiveSignalGenerator
from trading.paper_trading_executor import PaperTradingExecutor
from trading.autonomous_trading_loop import AutonomousTradingLoop
from trading.universe_manager import UniverseManager
from trading.universe_scanner import UniverseScanner

async def main():
    logger.info('========================================')
    logger.info('MECOS INSTITUTIONAL TRADING SYSTEM')
    logger.info('Multi-Asset Autonomous Trading Platform')
    logger.info('========================================')
    
    memory = MemorySystem()
    db = TradeDatabase()
    quant_mode = os.getenv('MECOS_QUANT_MODE', 'balanced')
    logger.info(f'Quant mode selected: {quant_mode}')

    agent = TradingAgent(memory, quant_mode=quant_mode)
    
    stream = MarketDataStream()

    stream.set_broker_adapter(MultiBrokerAdapter())
    logger.info('Live broker adapter configured: MultiBroker (Alpaca/Binance/OANDA)')

    signal_gen = LiveSignalGenerator(agent, stream, memory)
    
    pos_mgr = PositionManager(db)
    risk_mon = RiskMonitor()
    perf_mon = PerformanceMonitor(db)
    
    executor = PaperTradingExecutor(db, pos_mgr, risk_mon, memory)
    
    universe_mgr = UniverseManager(memory)
    broker_adapter = stream.broker_adapter
    forex_available = bool(getattr(broker_adapter, "oanda", None))
    universe_mgr.set_forex_enabled(forex_available)
    
    scanner = UniverseScanner(universe_mgr, stream)
    
    loop = AutonomousTradingLoop(
        stream, 
        signal_gen, 
        executor, 
        perf_mon, 
        db,
        universe_mgr,
        scanner,
        quant_mode=quant_mode,
    )
    
    logger.info('')
    logger.info('UNIVERSE OPTIONS:')
    logger.info('1. STARTER (12 assets) - Recommended for validation')
    logger.info('   → 6 Stocks + 3 ETFs + 3 Crypto')
    logger.info('2. FULL (60+ assets) - Complete multi-asset universe')
    logger.info('')
    
    logger.warning('SAFETY CONTROLS:')
    logger.warning('→ Validation Mode: ACTIVE (signals only, no execution)')
    logger.warning('→ To enable paper trading: executor.enable_execution()')
    logger.warning('→ Kill switch: executor.trigger_kill_switch("reason")')
    logger.warning('')
    
    try:
        await loop.start(use_starter_universe=True)
        
    except KeyboardInterrupt:
        logger.info('Shutdown requested')
        loop.stop()
        
        final_stats = loop.get_status()
        logger.info('')
        logger.info('FINAL SESSION STATISTICS:')
        logger.info(f'Runtime: {(datetime.now() - loop.loop_stats["start_time"]).total_seconds():.0f}s')
        logger.info(f'Signals: {final_stats["signal_stats"]["total_signals"]}')
        logger.info(f'Trades: {final_stats["account"]["executed_orders"]}')
        logger.info(f'Final Equity: ')
        logger.info(f'Total Return: {final_stats["account"]["total_return"]:.2%}')

if __name__ == '__main__':
    asyncio.run(main())
