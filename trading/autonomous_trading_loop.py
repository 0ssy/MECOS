import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime
from pathlib import Path
from .cooldown_manager import CooldownManager
from .regime_detection import detect_regime
from .exposure_manager import ExposureManager
from .equity_persistence import EquityPersistence
from .pnl_engine import PnLEngine
from .attribution_logger import AttributionLogger
from .confidence_calibrator import ConfidenceCalibrator

try:
    from rl_trainer import RLTrainer
except Exception:
    RLTrainer = None

SESSION_THRESHOLD_PROFILES = {
    'conservative': {
        'market_hours': 0.70,
        'after_hours': 0.72,
        'crypto_weekend': 0.70,
    },
    'balanced': {
        'market_hours': 0.60,
        'after_hours': 0.62,
        'crypto_weekend': 0.60,
    },
    'aggressive_research': {
        'market_hours': 0.50,
        'after_hours': 0.52,
        'crypto_weekend': 0.50,
    },
}

# Backward-compatible constant used by existing imports and scripts.
SESSION_THRESHOLDS = SESSION_THRESHOLD_PROFILES['balanced'].copy()


def _normalize_quant_mode(mode: str) -> str:
    normalized = (mode or 'balanced').strip().lower().replace('-', '_')
    aliases = {
        'research': 'aggressive_research',
        'aggressive': 'aggressive_research',
        'option2': 'balanced',
        'option3': 'aggressive_research',
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SESSION_THRESHOLD_PROFILES:
        return 'balanced'
    return normalized

class AutonomousTradingLoop:
    def __init__(self, 
                 market_stream,
                 signal_generator,
                 paper_executor,
                 performance_monitor,
                 database,
                 universe_manager,
                 universe_scanner=None,
                 quant_mode: str = 'balanced'):
        self.market_stream = market_stream
        self.signal_generator = signal_generator
        self.paper_executor = paper_executor
        self.performance_monitor = performance_monitor
        self.database = database
        self.universe_manager = universe_manager
        self.universe_scanner = universe_scanner
        self.quant_mode = _normalize_quant_mode(quant_mode)
        self.session_thresholds = SESSION_THRESHOLD_PROFILES[self.quant_mode]

        self.cooldown_manager = CooldownManager()
        self.exposure_manager = ExposureManager()
        self.equity_persistence = EquityPersistence()
        self.pnl_engine = PnLEngine()
        self.attribution_logger = AttributionLogger()
        self.confidence_calibrator = ConfidenceCalibrator()

        self.running = False
        self.symbols = []
        self.current_regime = 'trending'
        self.cycle_interval_seconds = 10.0
        self._last_symbol_cycle_time = {}

        self.loop_stats = {
            'iterations': 0,
            'start_time': None,
            'signals_processed': 0,
            'trades_executed': 0,
            'rejected_trades': 0,
            'hold_signals': 0,
            'universe_rotations': 0
        }

        self.rl_trainer: Optional[Any] = None
        self.rl_trade_context: Dict[str, Dict[str, Any]] = {}
        self._init_rl_trainer()
        if hasattr(self.paper_executor, 'register_order_status_callback'):
            self.paper_executor.register_order_status_callback(self._on_order_status)

        logger.info('Enhanced Autonomous Trading Loop initialized')
        logger.info(f'Quant mode: {self.quant_mode} | session_thresholds={self.session_thresholds}')

    def _init_rl_trainer(self):
        if RLTrainer is None:
            logger.warning('RL trainer import failed; running rule-based policy only')
            return

        memory = getattr(self.signal_generator, 'memory', None) or getattr(self.universe_manager, 'memory', None)
        if memory is None:
            logger.warning('RL memory dependency unavailable; running rule-based policy only')
            return

        try:
            self.rl_trainer = RLTrainer(memory, domain='trading')
            qtable_path = Path('data/qtable.json')  # Replace with actual path if different
            self.rl_trainer.q_table.load(qtable_path)
            logger.info('Trading RL policy enabled (Q-learning + replay)')
        except Exception as exc:
            logger.error(f'Failed to initialize trading RL policy: {exc}')
            self.rl_trainer = None

    def _build_rl_state(self, symbol: str, tick: Dict[str, Any], signal: Dict[str, Any], session_name: str) -> str:
        confidence = float(signal.get('confidence', 0.0) or 0.0)
        volatility = float(tick.get('volatility', signal.get('volatility', 0.0)) or 0.0)
        price_change = 0.0
        if tick.get('open'):
            try:
                price_change = float(tick.get('close', 0.0) or 0.0) / float(tick.get('open', 1.0) or 1.0) - 1.0
            except Exception:
                price_change = 0.0

        conf_bucket = 'high' if confidence >= 0.75 else 'mid' if confidence >= 0.6 else 'low'
        vol_bucket = 'high' if volatility >= 0.03 else 'mid' if volatility >= 0.01 else 'low'
        trend_bucket = 'up' if price_change > 0.001 else 'down' if price_change < -0.001 else 'flat'
        regime = str(signal.get('regime', self.current_regime) or self.current_regime)

        return '|'.join([
            f'sym={symbol}',
            f'session={session_name}',
            f'regime={regime}',
            f'conf={conf_bucket}',
            f'vol={vol_bucket}',
            f'trend={trend_bucket}',
        ])

    def _apply_rl_policy(self, signal: Dict[str, Any], state: str) -> Dict[str, Any]:
        if self.rl_trainer is None:
            signal['decision_source'] = 'rules'
            return signal

        base_decision = signal.get('decision', 'HOLD')
        available_actions = ['BUY', 'SELL', 'HOLD']
        rl_action = self.rl_trainer.choose_action(state, available_actions)

        # Allow RL to override base decision for more aggressive learning
        if rl_action not in {'BUY', 'SELL', 'HOLD'}:
            rl_action = base_decision

        signal['base_decision'] = base_decision
        signal['rl_action'] = rl_action
        signal['decision_source'] = 'rl_policy' if rl_action != base_decision else 'rules_with_rl_guard'
        signal['decision'] = rl_action
        signal['final_decision'] = rl_action
        return signal

    async def _record_rl_trade_outcome(
        self,
        symbol: str,
        tick: Dict[str, Any],
        result: Dict[str, Any],
        metrics: Dict[str, Any],
    ):
        if self.rl_trainer is None:
            return

        context = self.rl_trade_context.pop(symbol, None)
        if not context:
            return

        try:
            raw_pnl = float(result.get('pnl', 0.0) or 0.0)
            holding_seconds = float(result.get('holding_seconds', 0.0) or 0.0)
            max_drawdown = float(metrics.get('max_drawdown', 0.0) or 0.0)

            # Penalty shaping discourages repeating high-drawdown and overlong holds.
            drawdown_penalty = max(0.0, max_drawdown - 0.05) * 100.0
            holding_penalty = max(0.0, holding_seconds - 4 * 3600) / 3600.0 * 0.1
            adjusted_pnl = raw_pnl - drawdown_penalty - holding_penalty

            next_session, _ = self._get_market_session_policy(tick)
            next_state = self._build_rl_state(
                symbol,
                tick,
                {'decision': 'HOLD', 'confidence': 0.0, 'regime': self.current_regime},
                next_session,
            )

            self.rl_trainer.record_experience(
                state=context['state'],
                action=context['action'],
                outcome={
                    'pnl': adjusted_pnl,
                    'raw_pnl': raw_pnl,
                    'drawdown_penalty': drawdown_penalty,
                    'holding_penalty': holding_penalty,
                },
                next_state=next_state,
                done=True,
            )
            await self.rl_trainer.train_from_replay(batch_size=32)
            logger.info(
                f"RL update {symbol}: action={context['action']} raw_pnl={raw_pnl:.2f} adjusted={adjusted_pnl:.2f}"
            )
        except Exception as exc:
            logger.error(f'RL trade outcome update failed for {symbol}: {exc}')

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
        
        await self.market_stream.stream_live_market_data(self.symbols)

    async def _on_market_tick(self, symbol: str, tick: Dict[str, Any]):
        if not self.running:
            return

        now = asyncio.get_running_loop().time()
        last = self._last_symbol_cycle_time.get(symbol, 0.0)
        if now - last < self.cycle_interval_seconds:
            return
        self._last_symbol_cycle_time[symbol] = now

        self.loop_stats['iterations'] += 1

        # Keep account equity in sync before risk checks and sizing decisions.
        await self.paper_executor.update_equity({symbol: tick.get('close', 0.0)})

        # Regime detection
        price_change = tick['close'] / tick['open'] - 1 if tick['open'] else 0
        volatility = tick.get('volatility', 0)
        self.current_regime = detect_regime(volatility, price_change)

        session_name, session_policy = self._get_market_session_policy(tick)

        # Prioritize risk exits before new entries.
        exit_signal = {}
        if hasattr(self.paper_executor, 'generate_exit_signal'):
            exit_signal = self.paper_executor.generate_exit_signal(symbol, tick, regime=self.current_regime)
        if exit_signal:
            exit_signal['sector'] = tick.get('sector', 'unknown')
            result = await self.paper_executor.execute_signal(exit_signal)
            self._update_execution_stats_from_result(result)
            if result.get('status') == 'EXECUTED':
                await self._post_trade_updates(symbol, tick, result)
            return

        signal = await self.signal_generator.on_market_data(symbol, tick)

        if signal:
            self.loop_stats['signals_processed'] += 1

            if signal.get('decision') == 'HOLD':
                self.loop_stats['hold_signals'] += 1
                return

            signal['session'] = session_name
            signal['regime'] = self.current_regime
            signal['symbol'] = symbol
            signal['sector'] = tick.get('sector', 'unknown')

            # Session-aware policy: lower participation outside liquid sessions.
            signal['allocation'] = float(signal.get('allocation', signal.get('size', 0.1))) * session_policy['size_multiplier']

            threshold_session = (
                'crypto_weekend'
                if session_name == 'crypto_weekend'
                else 'after_hours'
                if session_name == 'after_hours'
                else 'market_hours'
            )
            min_conf = self.session_thresholds.get(threshold_session, 0.72)
            if signal.get('confidence', 0.0) < min_conf:
                self.loop_stats['hold_signals'] += 1
                logger.info(f"Session gate HOLD for {symbol}: conf={signal.get('confidence', 0.0):.2f} < {min_conf:.2f} ({session_name})")
                return

            # Confidence calibration
            if 'confidence' in signal:
                signal['confidence'] = self.confidence_calibrator.calibrate(signal['confidence'])

            rl_state = self._build_rl_state(symbol, tick, signal, session_name)
            signal['rl_state'] = rl_state
            signal = self._apply_rl_policy(signal, rl_state)
            if signal.get('decision') == 'HOLD':
                self.loop_stats['hold_signals'] += 1
                logger.info(f"RL policy HOLD for {symbol}: base={signal.get('base_decision', 'N/A')}")
                return

            # Attribution logging
            self.attribution_logger.log(signal)

            # Trade cooldown
            if signal['decision'] != 'HOLD':
                if not self.cooldown_manager.can_trade(symbol):
                    logger.info(f"Cooldown active for {symbol}, skipping trade.")
                    return

                # Exposure management (sector must be provided by tick or symbol mapping)
                sector = tick.get('sector', 'unknown')
                notional = tick['close'] * signal.get('size', 1.0)
                portfolio_value = self.paper_executor.paper_account.get('equity', 1.0)
                if not self.exposure_manager.can_add(sector, notional, portfolio_value):
                    logger.info(f"Sector exposure cap reached for {sector}, skipping trade.")
                    return

                result = await self.paper_executor.execute_signal(signal)
                self._update_execution_stats_from_result(result)

                if result.get('status') == 'EXECUTED':
                    executed_side = result.get('side', signal.get('decision', 'HOLD'))
                    if executed_side in {'BUY', 'SELL'} and 'pnl' not in result:
                        self.rl_trade_context[symbol] = {
                            'state': rl_state,
                            'action': signal.get('decision', executed_side),
                            'ts': datetime.now().isoformat(),
                        }
                    self.cooldown_manager.record_trade(symbol)
                    self.exposure_manager.update_exposure(symbol, sector, notional)
                    await self._post_trade_updates(symbol, tick, result)

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
            
            asyncio.create_task(
                self.market_stream.stream_live_market_data(self.symbols)
            )
            
            self.loop_stats['universe_rotations'] += 1

    def _log_status(self):
        runtime = (datetime.now() - self.loop_stats['start_time']).total_seconds()
        
        account = self.paper_executor.get_account_status()
        signal_stats = self.signal_generator.get_stats()
        perf_metrics = self.performance_monitor.get_metrics()
        universe_stats = self.universe_manager.get_universe_statistics()
        exposure = self.exposure_manager.sector_exposure
        
        logger.info('========================================')
        logger.info(f'RUNTIME: {runtime:.0f}s | Iterations: {self.loop_stats["iterations"]}')
        logger.info(f'UNIVERSE: {universe_stats["active_universe_size"]} assets | Rotations: {self.loop_stats["universe_rotations"]}')
        logger.info(f'ACCOUNT:  | Return: {account["total_return"]:.2%} | Cash: ')
        logger.info(f'SIGNALS: {signal_stats["total_signals"]} | BUY: {signal_stats["buy_signals"]} | SELL: {signal_stats["sell_signals"]}')
        logger.info(f'TRADES: executed={account["executed_orders"]} rejected={account["rejected_orders"]} | PnL={account.get("total_pnl", 0):.2f}')
        logger.info(f'PERFORMANCE: Sharpe={perf_metrics["sharpe_ratio"]:.2f} | Max DD={perf_metrics["max_drawdown"]:.2%} | WinRate={perf_metrics.get("win_rate", 0):.2%} | ProfitFactor={perf_metrics.get("profit_factor", 0):.2f}')
        logger.info(f'EXPOSURE BY SECTOR: {exposure}')
        logger.info('========================================')

    async def _post_trade_updates(self, symbol: str, tick: Dict[str, Any], result: Dict[str, Any]):
        current_prices = {symbol: tick['close']}
        await self.paper_executor.update_equity(current_prices)

        self.pnl_engine.update_unrealized(self.paper_executor.position_manager.positions, current_prices)
        await self.performance_monitor.update(self.paper_executor.paper_account['equity'])

        if result.get('side') == 'SELL' and 'pnl' in result:
            self.performance_monitor.record_trade_close(
                pnl=result['pnl'],
                holding_seconds=result.get('holding_seconds', 0.0),
            )

        self.database.save_portfolio_snapshot({
            'total_value': self.paper_executor.paper_account['equity'],
            'cash': self.paper_executor.paper_account['cash'],
            'positions': self.paper_executor.position_manager.positions
        })

        import time as _time
        metrics = self.performance_monitor.get_metrics()

        if result.get('side') == 'SELL' and 'pnl' in result:
            await self._record_rl_trade_outcome(symbol, tick, result, metrics)

        self.equity_persistence.save(
            _time.time(),
            self.paper_executor.paper_account['equity'],
            str(self.paper_executor.position_manager.positions),
            str(result),
            metrics.get('max_drawdown', 0),
            metrics.get('sharpe_ratio', 0),
            metrics.get('win_rate', 0)
        )

    async def _on_order_status(self, status_event: Dict[str, Any]):
        order_id = status_event.get('order_id')
        symbol = status_event.get('symbol', '')
        status = status_event.get('status', '')
        logger.debug(f'Order status callback: order={order_id} symbol={symbol} status={status}')

    def _update_execution_stats_from_result(self, result: Dict[str, Any]):
        status = result.get('status')
        if status == 'EXECUTED':
            self.loop_stats['trades_executed'] += 1
        elif status in {'REJECTED', 'KILLED'}:
            self.loop_stats['rejected_trades'] += 1

    def _get_market_session_policy(self, tick: Dict[str, Any]):
        ts = tick.get('timestamp')
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
            except ValueError:
                dt = datetime.utcnow()
        else:
            dt = datetime.utcnow()
        hour = dt.hour
        weekday = dt.weekday()

        market_hours_conf = self.session_thresholds.get('market_hours', 0.72)
        after_hours_conf = self.session_thresholds.get('after_hours', 0.72)
        weekend_conf = self.session_thresholds.get('crypto_weekend', 0.72)

        if weekday >= 5:
            return 'crypto_weekend', {'min_confidence': weekend_conf, 'size_multiplier': 0.50}
        if 9 <= hour < 11:
            return 'us_open', {'min_confidence': market_hours_conf, 'size_multiplier': 1.00}
        if 11 <= hour < 14:
            return 'lunch_chop', {'min_confidence': market_hours_conf, 'size_multiplier': 0.70}
        if 14 <= hour < 16:
            return 'us_close', {'min_confidence': market_hours_conf, 'size_multiplier': 0.90}
        return 'after_hours', {'min_confidence': after_hours_conf, 'size_multiplier': 0.40}

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
            'exposure_by_sector': self.exposure_manager.sector_exposure,
            'universe': self.universe_manager.get_universe_statistics(),
            'rl': self.rl_trainer.get_stats() if self.rl_trainer else {'enabled': False},
        }

async def start_trading_loop():
    """
    Initializes and starts the AutonomousTradingLoop with multi-broker live connectivity.
    """
    from trading.broker.multi_broker_adapter import MultiBrokerAdapter
    from trading.market_data_stream import MarketDataStream
    from trading.live_signal_generator import LiveSignalGenerator
    from trading.paper_trading_executor import PaperTradingExecutor
    from trading.performance_monitor import PerformanceMonitor
    from trading.trade_database import TradeDatabase
    from trading.universe_manager import UniverseManager
    from trading.trading_agent import TradingAgent
    from memory_system import MemorySystem

    # Initialize components
    broker_adapter = MultiBrokerAdapter()
    market_stream = MarketDataStream()
    market_stream.set_broker_adapter(broker_adapter)
    memory = MemorySystem()
    database = TradeDatabase()
    from trading.position_manager import PositionManager
    from trading.risk_monitor import RiskMonitor
    position_manager = PositionManager(database)
    risk_monitor = RiskMonitor()
    trading_agent = TradingAgent(memory, quant_mode='aggressive_research')
    signal_generator = LiveSignalGenerator(trading_agent, market_stream, memory)
    paper_executor = PaperTradingExecutor(database, position_manager, risk_monitor, memory)
    performance_monitor = PerformanceMonitor(database)
    universe_manager = UniverseManager(memory)

    # Initialize the trading loop
    trading_loop = AutonomousTradingLoop(
        market_stream=market_stream,
        signal_generator=signal_generator,
        paper_executor=paper_executor,
        performance_monitor=performance_monitor,
        database=database,
        universe_manager=universe_manager,
        quant_mode='aggressive_research'  # Use aggressive mode for more exploration
    )

    logger.info("Starting the autonomous trading loop with multi-broker live adapter...")
    await trading_loop.start(use_starter_universe=True)
