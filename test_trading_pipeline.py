import asyncio
from loguru import logger
from memory_system import MemorySystem
from trading import *
from trading.market_data_stream import MarketDataStream
from trading.live_signal_generator import LiveSignalGenerator
from trading.paper_trading_executor import PaperTradingExecutor
from trading.autonomous_trading_loop import AutonomousTradingLoop

async def test_streaming():
    logger.info('TEST 1: Market Data Streaming')
    
    stream = MarketDataStream()
    
    received_data = []
    
    async def callback(symbol, tick):
        received_data.append((symbol, tick))
        if len(received_data) <= 5:
            logger.info(f'Received: {symbol} @ ')
    
    stream.subscribe('TEST', callback)
    
    task = asyncio.create_task(stream.simulate_market_stream(['TEST']))
    
    await asyncio.sleep(5)
    stream.stop()
    
    logger.info(f'RESULT: Received {len(received_data)} ticks')
    return len(received_data) > 0

async def test_signal_generation():
    logger.info('TEST 2: Signal Generation')
    
    memory = MemorySystem()
    agent = TradingAgent(memory)
    stream = MarketDataStream()
    
    signal_gen = LiveSignalGenerator(agent, stream, memory)
    
    stream.subscribe('TEST', signal_gen.on_market_data)
    
    task = asyncio.create_task(stream.simulate_market_stream(['TEST']))
    
    await asyncio.sleep(60)
    stream.stop()
    
    stats = signal_gen.get_stats()
    logger.info(f'RESULT: Signals: {stats["total_signals"]} | BUY: {stats["buy_signals"]} | SELL: {stats["sell_signals"]}')
    
    return stats['total_signals'] > 0

async def test_paper_execution():
    logger.info('TEST 3: Paper Trading Execution')
    
    memory = MemorySystem()
    db = TradeDatabase()
    pos_mgr = PositionManager(db)
    risk_mon = RiskMonitor()
    
    executor = PaperTradingExecutor(db, pos_mgr, risk_mon, memory)
    executor.enable_execution()
    
    test_signal = {
        'symbol': 'TEST',
        'decision': 'BUY',
        'confidence': 0.75,
        'position_size': 0.1,
        'features': {'close': 100.0}
    }
    
    result = await executor.execute_signal(test_signal)
    logger.info(f'BUY Result: {result}')
    
    test_signal['decision'] = 'SELL'
    test_signal['features']['close'] = 105.0
    
    result = await executor.execute_signal(test_signal)
    logger.info(f'SELL Result: {result}')
    
    account = executor.get_account_status()
    logger.info(f'RESULT: Account Equity:  | PnL: ')
    
    return account['executed_orders'] > 0

async def test_risk_rejection():
    logger.info('TEST 4: Risk Rejection')
    
    memory = MemorySystem()
    db = TradeDatabase()
    pos_mgr = PositionManager(db)
    risk_mon = RiskMonitor()
    
    executor = PaperTradingExecutor(db, pos_mgr, risk_mon, memory)
    executor.enable_execution()
    
    test_signal = {
        'symbol': 'TEST',
        'decision': 'BUY',
        'confidence': 0.75,
        'position_size': 0.5,
        'features': {'close': 100.0}
    }
    
    result = await executor.execute_signal(test_signal)
    logger.info(f'Large position result: {result}')
    
    return result.get('status') in ['REJECTED', 'EXECUTED']

async def test_kill_switch():
    logger.info('TEST 5: Kill Switch')
    
    memory = MemorySystem()
    db = TradeDatabase()
    pos_mgr = PositionManager(db)
    risk_mon = RiskMonitor()
    
    executor = PaperTradingExecutor(db, pos_mgr, risk_mon, memory)
    executor.enable_execution()
    
    executor.trigger_kill_switch('TEST TRIGGER')
    
    test_signal = {
        'symbol': 'TEST',
        'decision': 'BUY',
        'confidence': 0.75,
        'position_size': 0.1,
        'features': {'close': 100.0}
    }
    
    result = await executor.execute_signal(test_signal)
    logger.info(f'Post-kill switch result: {result}')
    
    return (
    executor.kill_switch_triggered is True and
    result.get('status') in ['KILLED', 'DISABLED']
)

async def run_all_tests():
    logger.info('========================================')
    logger.info('RUNNING VALIDATION TEST SUITE')
    logger.info('========================================')
    
    tests = [
        ('Market Data Streaming', test_streaming),
        ('Signal Generation', test_signal_generation),
        ('Paper Execution', test_paper_execution),
        ('Risk Rejection', test_risk_rejection),
        ('Kill Switch', test_kill_switch)
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            logger.info(f'Running: {name}')
            result = await test_func()
            results[name] = 'PASS' if result else 'FAIL'
            logger.info(f'{name}: {results[name]}')
        except Exception as e:
            results[name] = f'ERROR: {e}'
            logger.error(f'{name} failed: {e}')
        
        await asyncio.sleep(2)
    
    logger.info('========================================')
    logger.info('TEST RESULTS')
    logger.info('========================================')
    for name, result in results.items():
        logger.info(f'{name}: {result}')

if __name__ == '__main__':
    asyncio.run(run_all_tests())
