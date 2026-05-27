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
from .event_bus import EventBus, Event, EventType
from .schemas import Signal, Decision, MarketEvent

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
        self.event_bus = EventBus()

        self.running = False
        self.symbols = []
        self.current_regime = 'trending'
        self.cycle_interval_seconds = 10.0
        self.symbol_cooldown_seconds = 300
        self._last_symbol_cycle_time = {}
        self._signal_persistence: Dict[str, Dict[str, Any]] = {}
        self.max_correlated_positions = 3
        self.min_acceptable_volatility = 0.003
        self.max_acceptable_volatility = 0.050
        self.enable_trade_quality_filter = True
        self.trade_quality_spread_multiplier = 2.5
        self.enable_signal_persistence = True
        self.signal_persistence_count_required = 2
        self.signal_persistence_seconds = 5.0

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
        self.rl_min_buffer_to_override = 128
        self.rl_min_confidence_for_override = 0.75
        self.rl_min_q_advantage = 0.03
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
        confidence = float(signal.get('confidence', 0.0) or 0.0)
        rl_stats = self.rl_trainer.get_stats() if hasattr(self.rl_trainer, 'get_stats') else {}
        buffer_size = int(rl_stats.get('buffer_size', 0))

        # Stability guard: keep rule engine in control until RL has enough evidence.
        if buffer_size < self.rl_min_buffer_to_override or confidence < self.rl_min_confidence_for_override:
            signal['base_decision'] = base_decision
            signal['rl_action'] = base_decision
            signal['decision_source'] = 'rules_rl_warmup'
            signal['decision'] = base_decision
            signal['final_decision'] = base_decision
            return signal

        rl_action = self.rl_trainer.choose_action(state, available_actions, allow_exploration=False)

        # Allow RL to override base decision for more aggressive learning
        if rl_action not in {'BUY', 'SELL', 'HOLD'}:
            rl_action = base_decision

        if hasattr(self.rl_trainer, 'q_values'):
            qvals = self.rl_trainer.q_values(state, available_actions)
            q_best = float(qvals.get(rl_action, 0.0))
            q_base = float(qvals.get(base_decision, 0.0))
            if q_best - q_base < self.rl_min_q_advantage:
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
            entry_context = context.get('entry_context', {}) if isinstance(context, dict) else {}
            causal = self._infer_loss_causes(entry_context, tick, result, metrics)
            causal_penalty = float(causal.get('causal_penalty', 0.0) or 0.0)

            # Penalty shaping discourages repeating high-drawdown and overlong holds.
            drawdown_penalty = max(0.0, max_drawdown - 0.05) * 100.0
            holding_penalty = max(0.0, holding_seconds - 4 * 3600) / 3600.0 * 0.1
            adjusted_pnl = raw_pnl - drawdown_penalty - holding_penalty - causal_penalty

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
                    'causal_penalty': causal_penalty,
                    'loss_causes': causal.get('loss_causes', []),
                },
                next_state=next_state,
                done=True,
            )
            await self.rl_trainer.train_from_replay(batch_size=32)
            logger.info(
                f"RL update {symbol}: action={context['action']} raw_pnl={raw_pnl:.2f} "
                f"adjusted={adjusted_pnl:.2f} causes={causal.get('loss_causes', [])}"
            )
            if raw_pnl < 0:
                self.attribution_logger.log(
                    {
                        'symbol': symbol,
                        'decision': context.get('action', 'HOLD'),
                        'event': 'RL_CAUSAL_UPDATE',
                        'pnl': raw_pnl,
                        'adjusted_pnl': adjusted_pnl,
                        'loss_causes': causal.get('loss_causes', []),
                        'causal_penalty': causal_penalty,
                        'regime': entry_context.get('regime', self.current_regime),
                        'session': entry_context.get('session', 'unknown'),
                    }
                )
        except Exception as exc:
            logger.error(f'RL trade outcome update failed for {symbol}: {exc}')

    def _infer_loss_causes(
        self,
        entry_context: Dict[str, Any],
        tick: Dict[str, Any],
        result: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        pnl = float(result.get('pnl', 0.0) or 0.0)
        if pnl >= 0:
            return {'loss_causes': [], 'causal_penalty': 0.0}

        causes = []
        penalty = 0.0

        confidence = float(entry_context.get('confidence', 0.0) or 0.0)
        threshold = float(entry_context.get('confidence_threshold', 0.0) or 0.0)
        edge = abs(float(entry_context.get('edge', 0.0) or 0.0))
        spread = float(entry_context.get('spread_pressure', 0.0) or 0.0)
        expected_move = float(entry_context.get('expected_move', 0.0) or 0.0)
        session = str(entry_context.get('session', 'unknown')).lower()
        entry_vol = float(entry_context.get('volatility', 0.0) or 0.0)
        current_vol = float(tick.get('volatility', entry_vol) or entry_vol)
        drawdown = float(metrics.get('max_drawdown', 0.0) or 0.0)
        holding_seconds = float(result.get('holding_seconds', 0.0) or 0.0)

        if confidence <= max(0.55, threshold):
            causes.append('weak_confidence_entry')
            penalty += 0.05
        if edge < 0.20:
            causes.append('weak_edge_entry')
            penalty += 0.06
        if spread > 0.006 and expected_move <= spread * 1.5:
            causes.append('spread_dominated_entry')
            penalty += 0.08
        if session in {'lunch_chop', 'after_hours', 'crypto_weekend'}:
            causes.append('adverse_session')
            penalty += 0.05
        if current_vol > self.max_acceptable_volatility or current_vol < self.min_acceptable_volatility:
            causes.append('volatility_dislocation')
            penalty += 0.07
        elif abs(current_vol - entry_vol) > max(0.01, entry_vol * 0.8):
            causes.append('volatility_regime_shift')
            penalty += 0.05
        if drawdown > 0.08:
            causes.append('portfolio_drawdown_stress')
            penalty += 0.05
        if holding_seconds >= self.paper_executor.max_holding_seconds * 0.8:
            causes.append('stale_holding_time')
            penalty += 0.03

        return {'loss_causes': causes, 'causal_penalty': min(0.35, penalty)}

    async def start(self, use_starter_universe: bool = True):
        if self.running:
            logger.warning('Trading loop already running')
            return
        
        self.running = True
        self.loop_stats['start_time'] = datetime.now()
        await self.event_bus.start()
        
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
        await self.event_bus.publish(
            Event(
                EventType.MARKET_TICK,
                {
                    'symbol': symbol,
                    'price': float(tick.get('close', 0.0) or 0.0),
                    'regime': self.current_regime,
                    'volatility': float(volatility or 0.0),
                },
            )
        )

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
            signal.setdefault('features', {})

            # Session-aware policy: lower participation outside liquid sessions.
            signal['allocation'] = float(signal.get('allocation', signal.get('size', 0.1))) * session_policy['size_multiplier']

            # Confidence calibration
            if 'confidence' in signal:
                signal_age = self._signal_age_seconds(signal)
                signal['confidence'] = self.confidence_calibrator.calibrate(
                    signal['confidence'],
                    age_seconds=signal_age,
                )

            min_conf = session_policy['min_confidence']
            if signal.get('confidence', 0.0) < min_conf:
                self.loop_stats['hold_signals'] += 1
                logger.info(f"Session gate HOLD for {symbol}: conf={signal.get('confidence', 0.0):.2f} < {min_conf:.2f} ({session_name})")
                return

            if self.enable_trade_quality_filter:
                if not self._passes_trade_quality(symbol, tick, signal, min_conf):
                    self.loop_stats['hold_signals'] += 1
                    return

            rl_state = self._build_rl_state(symbol, tick, signal, session_name)
            signal['rl_state'] = rl_state
            signal = self._apply_rl_policy(signal, rl_state)
            if signal.get('decision') == 'HOLD':
                self.loop_stats['hold_signals'] += 1
                logger.info(f"RL policy HOLD for {symbol}: base={signal.get('base_decision', 'N/A')}")
                return

            if self.enable_signal_persistence:
                if not self._passes_signal_persistence(symbol, signal):
                    self.loop_stats['hold_signals'] += 1
                    return

            await self.event_bus.publish(
                Event(
                    EventType.SIGNAL_CREATED,
                    {
                        'symbol': symbol,
                        'decision': signal.get('decision', 'HOLD'),
                        'confidence': float(signal.get('confidence', 0.0) or 0.0),
                        'edge': float(signal.get('edge', 0.0) or 0.0),
                        'regime': signal.get('regime', self.current_regime),
                    },
                )
            )

            # Trade cooldown
            if signal['decision'] != 'HOLD':
                if not self.cooldown_manager.can_trade(symbol, cooldown_seconds=self.symbol_cooldown_seconds):
                    logger.info(f"Cooldown active for {symbol}, skipping trade.")
                    return

                # Exposure management (sector must be provided by tick or symbol mapping)
                sector = tick.get('sector', 'unknown')
                allocation = float(signal.get('allocation', signal.get('size', 0.1)) or 0.1)
                notional = self.paper_executor.paper_account.get('equity', 1.0) * allocation
                portfolio_value = self.paper_executor.paper_account.get('equity', 1.0)
                if not self.exposure_manager.can_add(
                    sector=sector,
                    notional=notional,
                    portfolio_value=portfolio_value,
                    symbol=symbol,
                    max_correlated_positions=self.max_correlated_positions,
                ):
                    logger.info(f"Exposure/correlation cap reached for {symbol} ({sector}), skipping trade.")
                    return

                await self.event_bus.publish(
                    Event(
                        EventType.RISK_APPROVED,
                        {'symbol': symbol, 'decision': signal.get('decision', 'HOLD'), 'notional': float(notional)},
                    )
                )
                result = await self.paper_executor.execute_signal(signal)
                self._update_execution_stats_from_result(result)
                await self.event_bus.publish(
                    Event(
                        EventType.ORDER_SUBMITTED,
                        {
                            'symbol': symbol,
                            'status': result.get('status', 'UNKNOWN'),
                            'side': result.get('side', signal.get('decision', 'HOLD')),
                        },
                    )
                )

                if result.get('status') == 'EXECUTED':
                    await self.event_bus.publish(
                        Event(
                            EventType.ORDER_FILLED,
                            {
                                'symbol': symbol,
                                'side': result.get('side', signal.get('decision', 'HOLD')),
                                'price': float(result.get('price', tick.get('close', 0.0)) or 0.0),
                                'shares': float(result.get('shares', 0.0) or 0.0),
                            },
                        )
                    )
                    executed_side = result.get('side', signal.get('decision', 'HOLD'))
                    if executed_side in {'BUY', 'SELL'} and 'pnl' not in result:
                        self.rl_trade_context[symbol] = {
                            'state': rl_state,
                            'action': signal.get('decision', executed_side),
                            'ts': datetime.now().isoformat(),
                            'entry_context': {
                                'confidence': float(signal.get('confidence', 0.0) or 0.0),
                                'edge': float(signal.get('edge', 0.0) or 0.0),
                                'spread_pressure': float(signal.get('spread_pressure', 0.0) or 0.0),
                                'expected_move': float(signal.get('expected_move', 0.0) or 0.0),
                                'regime': str(signal.get('regime', self.current_regime)),
                                'session': str(signal.get('session', 'unknown')),
                                'volatility': float(signal.get('volatility', 0.0) or 0.0),
                                'confidence_threshold': float(signal.get('confidence_threshold', 0.0) or 0.0),
                            },
                        }
                    self.cooldown_manager.record_trade(symbol)
                    self.exposure_manager.update_exposure(symbol, sector, notional)
                    self.attribution_logger.log(self._build_structured_telemetry(signal, result))
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
            await self.event_bus.publish(
                Event(
                    EventType.PNL_UPDATED,
                    {'symbol': symbol, 'pnl': float(result.get('pnl', 0.0) or 0.0)},
                )
            )

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
            return 'us_open', {'min_confidence': market_hours_conf + 0.03, 'size_multiplier': 1.00}
        if 11 <= hour < 14:
            return 'lunch_chop', {'min_confidence': market_hours_conf + 0.10, 'size_multiplier': 0.70}
        if 14 <= hour < 16:
            return 'power_hour', {'min_confidence': market_hours_conf + 0.02, 'size_multiplier': 0.90}
        return 'after_hours', {'min_confidence': after_hours_conf, 'size_multiplier': 0.40}

    def _signal_age_seconds(self, signal: Dict[str, Any]) -> float:
        timestamp = signal.get('timestamp')
        if not timestamp:
            return 0.0
        try:
            ts = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
            return max(0.0, (datetime.now(ts.tzinfo) - ts).total_seconds())
        except ValueError:
            return 0.0

    def _adaptive_confidence_threshold(self, signal: Dict[str, Any], base_threshold: float) -> float:
        regime = str(signal.get('regime', self.current_regime) or self.current_regime).lower()
        volatility = float(signal.get('volatility', signal.get('features', {}).get('realized_volatility', 0.0)) or 0.0)
        threshold = float(base_threshold)
        if regime in {'panic', 'volatile_trend', 'high_volatility'}:
            threshold += 0.05
        elif regime in {'trending'}:
            threshold -= 0.02
        if volatility > 0.03:
            threshold += 0.04
        return min(max(threshold, 0.30), 0.95)

    def _passes_trade_quality(self, symbol: str, tick: Dict[str, Any], signal: Dict[str, Any], base_threshold: float) -> bool:
        features = signal.get('features', {}) if isinstance(signal.get('features', {}), dict) else {}
        spread = float(
            signal.get('spread_pressure', features.get('spread_pressure', 0.0))
            or 0.0
        )
        expected_move = float(signal.get('expected_move', 0.0) or 0.0)
        if expected_move <= 0.0 and tick.get('open'):
            expected_move = abs(float(tick.get('close', 0.0) or 0.0) / float(tick.get('open', 1.0) or 1.0) - 1.0)
        volatility = float(signal.get('volatility', tick.get('volatility', 0.0)) or 0.0)
        confidence = float(signal.get('confidence', 0.0) or 0.0)
        adaptive_threshold = self._adaptive_confidence_threshold(signal, base_threshold)
        signal['confidence_threshold'] = adaptive_threshold

        quality_checks = (
            expected_move > (spread * self.trade_quality_spread_multiplier),
            self.min_acceptable_volatility <= volatility <= self.max_acceptable_volatility,
            confidence > adaptive_threshold,
        )
        if all(quality_checks):
            return True
        logger.info(
            f"Quality gate HOLD for {symbol}: expected_move={expected_move:.4f} spread={spread:.4f} "
            f"vol={volatility:.4f} conf={confidence:.2f} thr={adaptive_threshold:.2f}"
        )
        return False

    def _passes_signal_persistence(self, symbol: str, signal: Dict[str, Any]) -> bool:
        now = datetime.now()
        decision = str(signal.get('decision', 'HOLD')).upper()
        state = self._signal_persistence.get(symbol)

        if not state or state.get('decision') != decision:
            self._signal_persistence[symbol] = {
                'decision': decision,
                'count': 1,
                'first_seen': now,
            }
            logger.debug(f"Persistence warmup for {symbol}: decision={decision} count=1")
            return False

        state['count'] = int(state.get('count', 1)) + 1
        first_seen = state.get('first_seen', now)
        if isinstance(first_seen, datetime):
            elapsed = (now - first_seen).total_seconds()
        else:
            elapsed = 0.0
        if state['count'] >= self.signal_persistence_count_required or elapsed >= self.signal_persistence_seconds:
            return True
        logger.debug(f"Persistence gate HOLD for {symbol}: decision={decision} count={state['count']} elapsed={elapsed:.1f}s")
        return False

    def _build_structured_telemetry(self, signal: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        reasons = []
        if signal.get('decision_source'):
            reasons.append(str(signal.get('decision_source')))
        if signal.get('base_decision'):
            reasons.append(f"base={signal.get('base_decision')}")
        if signal.get('exit_reason'):
            reasons.append(f"exit={signal.get('exit_reason')}")

        market_event = MarketEvent(
            event_type='EXECUTION_DECISION',
            symbol=str(signal.get('symbol', '')),
            timestamp=datetime.now().isoformat(),
            payload={'status': result.get('status', 'UNKNOWN')},
        )
        decision = Decision(
            symbol=str(signal.get('symbol', '')),
            action=str(signal.get('decision', 'HOLD')),
            confidence=float(signal.get('confidence', 0.0) or 0.0),
            threshold=float(signal.get('confidence_threshold', 0.0) or 0.0),
            approved=result.get('status') == 'EXECUTED',
            reasons=reasons,
        )
        _ = Signal(
            symbol=str(signal.get('symbol', '')),
            decision=str(signal.get('decision', 'HOLD')),
            confidence=float(signal.get('confidence', 0.0) or 0.0),
            buy_score=float(signal.get('buy_score', 0.0) or 0.0),
            sell_score=float(signal.get('sell_score', 0.0) or 0.0),
            edge=float(signal.get('edge', 0.0) or 0.0),
            regime=str(signal.get('regime', 'unknown')),
            session=str(signal.get('session', 'unknown')),
            reasons=reasons,
        )

        return {
            'symbol': decision.symbol,
            'decision': decision.action,
            'confidence': decision.confidence,
            'regime': signal.get('regime', 'unknown'),
            'session': signal.get('session', 'unknown'),
            'volatility': float(signal.get('volatility', 0.0) or 0.0),
            'buy_score': float(signal.get('buy_score', 0.0) or 0.0),
            'sell_score': float(signal.get('sell_score', 0.0) or 0.0),
            'edge': float(signal.get('edge', 0.0) or 0.0),
            'expected_move': float(signal.get('expected_move', 0.0) or 0.0),
            'spread_pressure': float(signal.get('spread_pressure', 0.0) or 0.0),
            'reason': reasons,
            'execution_status': result.get('status', 'UNKNOWN'),
            'event': market_event.event_type,
        }

    def stop(self):
        self.running = False
        self.market_stream.stop()
        try:
            asyncio.get_running_loop().create_task(self.event_bus.stop())
        except RuntimeError:
            pass
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
