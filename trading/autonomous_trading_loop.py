import asyncio
from typing import List, Dict, Any
from loguru import logger
from datetime import datetime

class AutonomousTradingLoop:
    def __init__(self, 
                 market_stream,
                 signal_generator,
                 paper_executor,
                 performance_monitor,
                 database,
                 universe_manager,
                 universe_scanner=None):
        
        self.market_stream = market_stream
        self.signal_generator = signal_generator
        self.paper_executor = paper_executor
        self.performance_monitor = performance_monitor
        self.database = database
        self.universe_manager = universe_manager
        self.universe_scanner = universe_scanner
        
        self.running = False
        self.symbols = []
        self.current_regime = 'trending'
        
        self.loop_stats = {
            'iterations': 0,
            'start_time': None,
            'signals_processed': 0,
            'trades_executed': 0,
            'universe_rotations': 0
        }
        
        logger.info('Enhanced Autonomous Trading Loop initialized')

    async def start(self, use_starter_universe: bool = True):
        if self.running:
            logger.warning('Trading loop already running')
            return
        
        self.running = True
        self.loop_stats['start_time'] = datetime.now()
        
        if use_starter_universe:
            self.symbols = self.universe_manager.load_starter_universe()
            logger.info('Using STARTER universe (12 assets)')
        else:
            self.symbols = self.universe_manager.load_default_universe()
            logger.info('Using FULL universe')
        
        logger.warning('========================================')
        logger.warning('AUTONOMOUS TRADING LOOP STARTING')
        logger.warning(f'Universe size: {len(self.symbols)}')
        logger.warning(f'Execution enabled: {self.paper_executor.execution_enabled}')
        logger.warning('========================================')
        
        sector_allocation = self.universe_manager.get_sector_allocation()
        logger.info(f'Sector allocation: {sector_allocation}')
        
        for symbol in self.symbols:
            self.market_stream.subscribe(symbol, self._on_market_tick)
        
        if self.universe_scanner:
            asyncio.create_task(
                self.universe_scanner.continuous_scanning(
                    self.universe_manager.load_default_universe()
                )
            )
        
        if self.market_stream.has_live_adapter():
            await self.market_stream.stream_live_market_data(self.symbols)
        else:
            await self.market_stream.simulate_market_stream(self.symbols)

    async def _on_market_tick(self, symbol: str, tick: Dict[str, Any]):
        if not self.running:
            return
        
        self.loop_stats['iterations'] += 1
        
        signal = await self.signal_generator.on_market_data(symbol, tick)
        
        if signal:
            self.loop_stats['signals_processed'] += 1
            
            if signal['decision'] != 'HOLD':
                result = await self.paper_executor.execute_signal(signal)
                
                if result.get('status') == 'EXECUTED':
                    self.loop_stats['trades_executed'] += 1
                    
                    current_prices = {symbol: tick['close']}
                    await self.paper_executor.update_equity(current_prices)
                    
                    await self.performance_monitor.update(
                        self.paper_executor.paper_account['equity']
                    )
                    
                    self.database.save_portfolio_snapshot({
                        'total_value': self.paper_executor.paper_account['equity'],
                        'cash': self.paper_executor.paper_account['cash'],
                        'positions': self.paper_executor.position_manager.positions
                    })
        
        if self.loop_stats['iterations'] % 100 == 0:
            self._log_status()
        
        if self.loop_stats['iterations'] % 1000 == 0:
            await self._maybe_rotate_universe()

    async def _maybe_rotate_universe(self):
        '''Check if universe rotation is needed'''
        
        if not self.universe_scanner:
            return
        
        scan_results = self.universe_scanner.get_scan_results()
        
        if not scan_results:
            logger.debug('No scan results available for rotation')
            return
        
        new_universe = self.universe_manager.rotate_universe(
            self.current_regime,
            scan_results
        )
        
        if set(new_universe) != set(self.symbols):
            logger.warning('UNIVERSE ROTATION DETECTED')
            
            removed = set(self.symbols) - set(new_universe)
            added = set(new_universe) - set(self.symbols)
            
            logger.info(f'Removed: {removed}')
            logger.info(f'Added: {added}')
            
            self.symbols = new_universe
            
            self.market_stream.stop()
            
            for symbol in self.symbols:
                self.market_stream.subscribe(symbol, self._on_market_tick)
            
            if self.market_stream.has_live_adapter():
                asyncio.create_task(
                    self.market_stream.stream_live_market_data(self.symbols)
                )
            else:
                asyncio.create_task(
                    self.market_stream.simulate_market_stream(self.symbols)
                )
            
            self.loop_stats['universe_rotations'] += 1

    def _log_status(self):
        runtime = (datetime.now() - self.loop_stats['start_time']).total_seconds()
        
        account = self.paper_executor.get_account_status()
        signal_stats = self.signal_generator.get_stats()
        perf_metrics = self.performance_monitor.get_metrics()
        universe_stats = self.universe_manager.get_universe_statistics()
        
        logger.info('========================================')
        logger.info(f'RUNTIME: {runtime:.0f}s | Iterations: {self.loop_stats["iterations"]}')
        logger.info(f'UNIVERSE: {universe_stats["active_universe_size"]} assets | Rotations: {self.loop_stats["universe_rotations"]}')
        logger.info(f'ACCOUNT:  | Return: {account["total_return"]:.2%} | Cash: ')
        logger.info(f'SIGNALS: {signal_stats["total_signals"]} | BUY: {signal_stats["buy_signals"]} | SELL: {signal_stats["sell_signals"]}')
        logger.info(f'TRADES: {account["executed_orders"]} | PnL: ')
        logger.info(f'PERFORMANCE: Sharpe: {perf_metrics["sharpe_ratio"]:.2f} | Max DD: {perf_metrics["max_drawdown"]:.2%}')
        logger.info('========================================')

    def stop(self):
        self.running = False
        self.market_stream.stop()
        logger.warning('AUTONOMOUS TRADING LOOP STOPPED')
        self._log_status()

    def get_status(self) -> Dict[str, Any]:
        return {
            'running': self.running,
            'symbols': self.symbols,
            'current_regime': self.current_regime,
            'loop_stats': self.loop_stats,
            'account': self.paper_executor.get_account_status(),
            'signal_stats': self.signal_generator.get_stats(),
            'performance': self.performance_monitor.get_metrics(),
            'universe': self.universe_manager.get_universe_statistics()
        }
