import asyncio
import inspect
from typing import Dict, Any, List, Callable, Awaitable, Optional
from loguru import logger
from datetime import datetime



def _realistic_fill_price(
    tick: dict,
    side: str,
    slippage_bps: float = 5.0,
) -> float:
    """
    Return a realistic fill price for paper trading.

    For BUY:  fill at ask + slippage  (we pay the offer)
    For SELL: fill at bid - slippage  (we hit the bid)
    Falls back to close price if bid/ask not available.

    slippage_bps: additional slippage in basis points (1 bps = 0.0001)
    """
    close = float(tick.get("close", 0.0) or 0.0)
    bid   = float(tick.get("bid",   close) or close)
    ask   = float(tick.get("ask",   close) or close)

    # Ensure valid spread
    if ask <= 0 or bid <= 0 or bid > ask:
        bid = close * 0.9999
        ask = close * 1.0001

    slip = close * (slippage_bps / 10_000.0)

    if str(side).upper() == "BUY":
        return float(ask + slip)
    else:
        return float(bid - slip)

from .broker.base_adapter import BrokerAdapter
from .order_manager import OrderManager
from .stability_layer import StabilityLayer
from .trade_journal import TradeJournal

class PaperTradingExecutor:
    def __init__(
        self,
        database,
        position_manager,
        risk_monitor,
        memory,
        order_manager: Optional[OrderManager] = None,
        broker_adapter: Optional[BrokerAdapter] = None,
        execution_mode: str = 'paper',
        stability_layer: Optional[StabilityLayer] = None,
        trade_journal: Optional[TradeJournal] = None,
    ):
        self.database = database
        self.position_manager = position_manager
        self.risk_monitor = risk_monitor
        self.memory = memory
        self.order_manager = order_manager or OrderManager(database)
        self.broker_adapter = broker_adapter
        self.stability_layer = stability_layer or StabilityLayer()
        self.trade_journal = trade_journal or TradeJournal()
        self.execution_mode = str(execution_mode or 'paper').strip().lower()
        if self.execution_mode not in {'paper', 'live'}:
            raise ValueError(f'Unsupported execution_mode: {self.execution_mode}')
        self.order_status_callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self.order_manager.register_status_callback(self._handle_order_status)

        self.paper_account = {
            'cash': 10000.0,
            'initial_capital': 10000.0,
            'equity': 10000.0
        }

        self.execution_enabled = True  # Force enable execution for paper trading
        self.kill_switch_triggered = False
        self.positions = {}
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.05
        self.trailing_stop_pct = 0.015
        self.max_holding_seconds = 4 * 60 * 60

        self.execution_stats = {
            'total_orders': 0,
            'executed_orders': 0,
            'rejected_orders': 0,
            'total_pnl': 0
        }

        self._restore_portfolio_state()
        self.stability_layer.position_store.replace_from_positions(self.position_manager.positions)
        logger.info(
            f'Paper Trading Executor initialized | Capital: {self.paper_account["cash"]:.2f} '
            f'| Execution enabled: {self.execution_enabled} | Mode: {self.execution_mode.upper()}'
        )

    def _restore_portfolio_state(self):
        snapshot = self.database.get_latest_portfolio_snapshot()
        if not snapshot:
            return

        cash = float(snapshot.get('cash', self.paper_account['cash']) or self.paper_account['cash'])
        total_value = float(snapshot.get('total_value', self.paper_account['equity']) or self.paper_account['equity'])
        positions = snapshot.get('positions', {})
        if not isinstance(positions, dict):
            positions = {}

        self.paper_account['cash'] = cash
        self.paper_account['equity'] = total_value
        if hasattr(self.position_manager, 'load_positions'):
            self.position_manager.load_positions(positions)
        self.positions = {}
        for symbol, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            size = float(pos.get('size', 0.0) or 0.0)
            if size <= 0:
                continue
            self.positions[symbol] = {'shares': size}

        logger.info(
            f'Portfolio state restored from snapshot: cash={cash:.2f}, equity={total_value:.2f}, positions={len(self.positions)}'
        )

    def register_order_status_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        self.order_status_callbacks.append(callback)

    async def _handle_order_status(self, status_event: Dict[str, Any]):
        for callback in self.order_status_callbacks:
            try:
                result = callback(status_event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger.error(f'Paper executor order callback failed: {exc}')

    def generate_exit_signal(self, symbol: str, tick: Dict[str, Any], regime: str = 'unknown') -> Dict[str, Any]:
        position = self.position_manager.positions.get(symbol)
        if not position or position.get('size', 0) <= 0:
            return {}

        current_price = _realistic_fill_price(tick, "SELL", slippage_bps=5.0)  # exits always sell
        if current_price <= 0:
            return {}

        self.position_manager.mark_price(symbol, current_price)

        avg_price = float(position.get('avg_price', current_price) or current_price)
        peak_price = float(position.get('peak_price', current_price) or current_price)
        holding_seconds = self.position_manager.get_holding_seconds(symbol)
        pnl_pct = (current_price - avg_price) / max(avg_price, 1e-9)
        drawdown_from_peak = (peak_price - current_price) / max(peak_price, 1e-9)

        exit_reason = ''
        if pnl_pct <= -self.stop_loss_pct:
            exit_reason = 'stop_loss'
        elif pnl_pct >= self.take_profit_pct:
            exit_reason = 'take_profit'
        elif drawdown_from_peak >= self.trailing_stop_pct:
            exit_reason = 'trailing_stop'
        elif holding_seconds >= self.max_holding_seconds:
            exit_reason = 'time_exit'

        if not exit_reason:
            return {}

        logger.info(f'EXIT TRIGGERED {symbol}: {exit_reason} | pnl={pnl_pct:.2%} | hold={holding_seconds:.0f}s')
        return {
            'symbol': symbol,
            'decision': 'SELL',
            'allocation': 1.0,
            'confidence': 1.0,
            'regime': regime,
            'features': {'close': current_price},
            'exit_reason': exit_reason,
            'force_exit': True,
        }

    async def execute_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        if not self.execution_enabled:
            logger.debug('Execution disabled')
            return {'status': 'DISABLED', 'reason': 'Execution not enabled'}
        
        if self.kill_switch_triggered:
            logger.error('KILL SWITCH ACTIVE - ALL EXECUTION HALTED')
            return {'status': 'KILLED', 'reason': 'Kill switch active'}
        
        if signal['decision'] == 'HOLD':
            return {'status': 'HOLD'}
        
        self.execution_stats['total_orders'] += 1
        
        symbol = signal.get('symbol')
        if not symbol:
            self.execution_stats['rejected_orders'] += 1
            return {'status': 'REJECTED', 'reason': 'Missing symbol'}

        decision = signal['decision']
        allowed, reason = self.stability_layer.can_place_order(symbol, decision)
        if not allowed:
            self.execution_stats['rejected_orders'] += 1
            if "circuit_breaker_halted" in reason:
                self.trigger_kill_switch(reason)
            logger.warning(f'Stability layer rejected {decision} for {symbol}: {reason}')
            return {'status': 'REJECTED', 'reason': reason}
        allocation = signal.get('allocation', signal.get('position_size', 0.1))
        price = signal.get('features', {}).get('close', 100.0)
        position_size = self.paper_account['cash'] * allocation
        tracked_position = self.position_manager.positions.get(symbol, {})
        has_open_position = float(tracked_position.get('size', 0.0) or 0.0) > 0.0
        reduce_only_exit = decision == 'SELL' and has_open_position
        
        trade = {
            'symbol': symbol,
            'side': decision,
            'size': allocation,
            'price': price
        }
        
        portfolio = {
            'total_value': self.paper_account['equity'],
            'cash': self.paper_account['cash']
        }
        
        risk_check = await self.risk_monitor.check_risk_limits(portfolio)
        
        if risk_check.get('breach', False):
            self.execution_stats['rejected_orders'] += 1
            logger.error(f'RISK BREACH: {risk_check["reason"]} - Order rejected')
            
            if risk_check.get('action') == 'HALT_TRADING':
                self.trigger_kill_switch(risk_check['reason'])
            
            return {'status': 'REJECTED', 'reason': risk_check['reason']}
        
        notional = position_size
        shares = notional / price
        if reduce_only_exit:
            shares = float(tracked_position.get('size', 0.0) or 0.0)

        if not reduce_only_exit:
            order_risk_check = await self.risk_monitor.check_order_risk(
                portfolio=portfolio,
                symbol=symbol,
                proposed_notional=notional,
                current_prices={symbol: price},
                positions=self.position_manager.positions,
            )

            if order_risk_check.get('breach', False):
                self.execution_stats['rejected_orders'] += 1
                logger.warning(f'ORDER RISK REJECTED: {order_risk_check["reason"]}')
                return {'status': 'REJECTED', 'reason': order_risk_check['reason']}
        
        if decision == 'BUY':
            if self.execution_mode == 'live':
                return await self._execute_live_order(
                    symbol=symbol,
                    side='BUY',
                    qty=shares,
                    signal=signal,
                    reference_price=price,
                )

            cost = shares * price
            
            if cost > self.paper_account['cash']:
                self.execution_stats['rejected_orders'] += 1
                logger.warning(f'Insufficient cash: need ${cost:.2f}, have ${self.paper_account["cash"]:.2f}')
                return {'status': 'REJECTED', 'reason': 'Insufficient cash'}
            
            self.paper_account['cash'] -= cost
            current_shares = self.positions.get(symbol, {}).get('shares', 0.0)
            self.positions[symbol] = {'shares': current_shares + shares}
            
            await self.position_manager.update_position(symbol, 'BUY', shares, price)
            if symbol in self.position_manager.positions:
                self.position_manager.positions[symbol]['sector'] = signal.get('sector', 'unknown')
            
            order = {
                'symbol': symbol,
                'side': 'BUY',
                'size': shares,
                'price': price,
                'status': 'FILLED'
            }
            order_id = await self.order_manager.create_order(order)
            await self.order_manager.submit_order(order_id)
            await self.order_manager.fill_order(order_id, price, shares)
            
            self.execution_stats['executed_orders'] += 1

            self.database.insert_trade({
                'symbol': symbol,
                'side': 'LONG',
                'entry_price': price,
                'quantity': shares,
                'confidence': signal.get('confidence', 0.0),
                'regime': signal.get('regime', 'unknown'),
            })
            self.stability_layer.record_order_fill(
                symbol=symbol,
                side='BUY',
                price=price,
                size=shares,
                metadata={
                    'regime': signal.get('regime', 'unknown'),
                    'confidence': float(signal.get('confidence', 0.0) or 0.0),
                },
            )
            self.trade_journal.record_entry(
                ticker=symbol,
                action='BUY',
                price=price,
                size=shares,
                reasoning={
                    'rsi': signal.get('features', {}).get('rsi_14', signal.get('features', {}).get('rsi')),
                    'regime': signal.get('regime', 'unknown'),
                    'sentiment': signal.get('news_sentiment'),
                    'macro': signal.get('macro_risk_regime'),
                    'pattern': signal.get('edge', 0.0),
                    'timeframe': signal.get('features', {}).get('timeframe_alignment'),
                    'confidence': signal.get('confidence', 0.0),
                },
            )
            
            logger.info(f'EXECUTING BUY {symbol} | size=${position_size:.2f}')
            logger.info(f'Portfolio Cash: ${self.paper_account["cash"]:.2f}')
            
            return {
                'status': 'EXECUTED',
                'order_id': order_id,
                'symbol': symbol,
                'side': 'BUY',
                'shares': shares,
                'price': price,
                'cost': cost
            }
        
        elif decision == 'SELL':
            if symbol not in self.positions and symbol not in self.position_manager.positions:
                logger.warning(f'No position to sell: {symbol}')
                return {'status': 'REJECTED', 'reason': 'No position'}

            local_position = self.positions.get(symbol, {'shares': 0.0})
            tracked_position = self.position_manager.positions.get(symbol, {'size': shares, 'avg_price': price})
            sell_shares = min(shares, tracked_position.get('size', shares))

            if self.execution_mode == 'live':
                return await self._execute_live_order(
                    symbol=symbol,
                    side='SELL',
                    qty=sell_shares,
                    signal=signal,
                    reference_price=price,
                )
            
            proceeds = sell_shares * price
            self.paper_account['cash'] += proceeds

            remaining = max(0.0, local_position.get('shares', 0.0) - sell_shares)
            if remaining <= 0:
                self.positions.pop(symbol, None)
            else:
                self.positions[symbol] = {'shares': remaining}
            
            holding_seconds = self.position_manager.get_holding_seconds(symbol)
            await self.position_manager.update_position(symbol, 'SELL', sell_shares, price)
            
            order = {
                'symbol': symbol,
                'side': 'SELL',
                'size': sell_shares,
                'price': price,
                'status': 'FILLED'
            }
            order_id = await self.order_manager.create_order(order)
            await self.order_manager.submit_order(order_id)
            await self.order_manager.fill_order(order_id, price, sell_shares)
            
            pnl = (price - tracked_position.get('avg_price', price)) * sell_shares
            self.execution_stats['total_pnl'] += pnl
            await self.risk_monitor.update_daily_pnl(pnl)

            open_trade = self.database.get_open_trade_for_symbol(symbol)
            if open_trade:
                self.database.close_trade(open_trade['id'], price, pnl, holding_seconds)
            self.stability_layer.record_order_fill(symbol=symbol, side='SELL', price=price, size=sell_shares)
            self.stability_layer.record_trade_close(
                symbol=symbol,
                pnl=pnl,
                exit_reason=signal.get('exit_reason', ''),
            )
            open_journal_trade_id = self.trade_journal.get_open_trade_id(symbol)
            if open_journal_trade_id:
                self.trade_journal.record_exit(
                    trade_id=open_journal_trade_id,
                    exit_price=price,
                    exit_reason=signal.get('exit_reason', ''),
                    pnl=pnl,
                    outcome='win' if pnl > 0 else 'loss' if pnl < 0 else 'flat',
                )
            if self.stability_layer.circuit_breaker.should_halt():
                self.trigger_kill_switch('circuit_breaker_triggered_after_losses')
            
            self.execution_stats['executed_orders'] += 1
            
            logger.info(f'EXECUTING SELL {symbol} | size=${position_size:.2f}')
            logger.info(f'Portfolio Cash: ${self.paper_account["cash"]:.2f}')
            
            return {
                'status': 'EXECUTED',
                'order_id': order_id,
                'symbol': symbol,
                'side': 'SELL',
                'shares': sell_shares,
                'price': price,
                'proceeds': proceeds,
                'pnl': pnl,
                'holding_seconds': holding_seconds,
                'exit_reason': signal.get('exit_reason', ''),
            }

        return {'status': 'REJECTED', 'reason': f'Unsupported decision: {decision}'}

    async def _execute_live_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        signal: Dict[str, Any],
        reference_price: float,
    ) -> Dict[str, Any]:
        if self.broker_adapter is None:
            self.execution_stats['rejected_orders'] += 1
            return {'status': 'REJECTED', 'reason': 'Live mode requires broker adapter'}

        order_qty = float(qty or 0.0)
        if order_qty <= 0.0:
            self.execution_stats['rejected_orders'] += 1
            return {'status': 'REJECTED', 'reason': f'Invalid order quantity: {order_qty}'}

        try:
            broker_order = await self.broker_adapter.submit_order(
                symbol=symbol,
                qty=order_qty,
                side=side,
                order_type='market',
            )
        except Exception as exc:
            self.execution_stats['rejected_orders'] += 1
            logger.error(f'LIVE ORDER FAILED {symbol} {side} qty={order_qty}: {exc}')
            return {'status': 'REJECTED', 'reason': str(exc), 'symbol': symbol, 'side': side}

        order = {
            'symbol': symbol,
            'side': side,
            'size': order_qty,
            'price': reference_price,
            'status': str(broker_order.get('status', 'SUBMITTED')),
            'broker_order_id': str(broker_order.get('id', '')),
        }
        order_id = await self.order_manager.create_order(order)
        await self.order_manager.submit_order(order_id)
        await self.order_manager.fill_order(order_id, reference_price, order_qty)

        self.execution_stats['executed_orders'] += 1
        logger.info(f'LIVE ORDER SENT {symbol} {side} qty={order_qty} broker={type(self.broker_adapter).__name__}')

        if side == 'BUY':
            await self.position_manager.update_position(symbol, 'BUY', order_qty, reference_price)
            if symbol in self.position_manager.positions:
                self.position_manager.positions[symbol]['sector'] = signal.get('sector', 'unknown')
            self.database.insert_trade({
                'symbol': symbol,
                'side': 'LONG',
                'entry_price': reference_price,
                'quantity': order_qty,
                'confidence': signal.get('confidence', 0.0),
                'regime': signal.get('regime', 'unknown'),
            })
            self.stability_layer.record_order_fill(
                symbol=symbol,
                side='BUY',
                price=reference_price,
                size=order_qty,
                metadata={
                    'regime': signal.get('regime', 'unknown'),
                    'confidence': float(signal.get('confidence', 0.0) or 0.0),
                    'live_execution': True,
                },
            )
            self.trade_journal.record_entry(
                ticker=symbol,
                action='BUY',
                price=reference_price,
                size=order_qty,
                reasoning={
                    'rsi': signal.get('features', {}).get('rsi_14', signal.get('features', {}).get('rsi')),
                    'regime': signal.get('regime', 'unknown'),
                    'sentiment': signal.get('news_sentiment'),
                    'macro': signal.get('macro_risk_regime'),
                    'pattern': signal.get('edge', 0.0),
                    'timeframe': signal.get('features', {}).get('timeframe_alignment'),
                    'confidence': signal.get('confidence', 0.0),
                },
            )
            return {
                'status': 'EXECUTED',
                'order_id': order_id,
                'broker_order_id': broker_order.get('id'),
                'symbol': symbol,
                'side': side,
                'shares': order_qty,
                'price': reference_price,
                'live_execution': True,
            }

        tracked_position = self.position_manager.positions.get(symbol, {'avg_price': reference_price})
        holding_seconds = self.position_manager.get_holding_seconds(symbol)
        await self.position_manager.update_position(symbol, 'SELL', order_qty, reference_price)
        pnl = (reference_price - tracked_position.get('avg_price', reference_price)) * order_qty
        self.execution_stats['total_pnl'] += pnl
        await self.risk_monitor.update_daily_pnl(pnl)

        open_trade = self.database.get_open_trade_for_symbol(symbol)
        if open_trade:
            self.database.close_trade(open_trade['id'], reference_price, pnl, holding_seconds)
        self.stability_layer.record_order_fill(symbol=symbol, side='SELL', price=reference_price, size=order_qty)
        self.stability_layer.record_trade_close(
            symbol=symbol,
            pnl=pnl,
            exit_reason=signal.get('exit_reason', ''),
        )
        open_journal_trade_id = self.trade_journal.get_open_trade_id(symbol)
        if open_journal_trade_id:
            self.trade_journal.record_exit(
                trade_id=open_journal_trade_id,
                exit_price=reference_price,
                exit_reason=signal.get('exit_reason', ''),
                pnl=pnl,
                outcome='win' if pnl > 0 else 'loss' if pnl < 0 else 'flat',
            )
        if self.stability_layer.circuit_breaker.should_halt():
            self.trigger_kill_switch('circuit_breaker_triggered_after_losses')

        return {
            'status': 'EXECUTED',
            'order_id': order_id,
            'broker_order_id': broker_order.get('id'),
            'symbol': symbol,
            'side': side,
            'shares': order_qty,
            'price': reference_price,
            'pnl': pnl,
            'holding_seconds': holding_seconds,
            'exit_reason': signal.get('exit_reason', ''),
            'live_execution': True,
        }

    async def update_equity(self, current_prices: Dict[str, float]):
        await self.position_manager.calculate_unrealized_pnl(current_prices)

        position_value = 0.0
        for symbol, position in self.position_manager.positions.items():
            size = float(position.get('size', 0.0) or 0.0)
            if size <= 0.0:
                continue
            mark_price = float(
                current_prices.get(
                    symbol,
                    position.get('last_price', position.get('avg_price', 0.0)),
                )
                or 0.0
            )
            if mark_price <= 0.0:
                mark_price = float(position.get('avg_price', 0.0) or 0.0)
            position_value += size * mark_price

        # Equity = cash + marked-to-market position value.
        self.paper_account['equity'] = self.paper_account['cash'] + position_value

    def enable_execution(self):
        self.execution_enabled = True
        logger.warning('PAPER TRADING EXECUTION ENABLED')

    def disable_execution(self):
        self.execution_enabled = False
        logger.info('Paper trading execution disabled')

    def trigger_kill_switch(self, reason: str):
        self.kill_switch_triggered = True
        self.execution_enabled = False
        logger.critical(f'KILL SWITCH TRIGGERED: {reason}')

    def reset_kill_switch(self):
        self.kill_switch_triggered = False
        logger.info('Kill switch reset')

    def get_account_status(self) -> Dict[str, Any]:
        return {
            'cash': self.paper_account['cash'],
            'equity': self.paper_account['equity'],
            'initial_capital': self.paper_account['initial_capital'],
            'total_return': (self.paper_account['equity'] - self.paper_account['initial_capital']) / self.paper_account['initial_capital'],
            'execution_enabled': self.execution_enabled,
            'kill_switch': self.kill_switch_triggered,
            **self.execution_stats
        }




