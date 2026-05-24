import asyncio
from typing import Dict, Any, List
from loguru import logger
from datetime import datetime

class PaperTradingExecutor:
    def __init__(self, database, position_manager, risk_monitor, memory):
        self.database = database
        self.position_manager = position_manager
        self.risk_monitor = risk_monitor
        self.memory = memory
        
        self.paper_account = {
            'cash': 10000.0,
            'initial_capital': 10000.0,
            'equity': 10000.0
        }
        
        self.execution_enabled = False
        self.kill_switch_triggered = False
        
        self.execution_stats = {
            'total_orders': 0,
            'executed_orders': 0,
            'rejected_orders': 0,
            'total_pnl': 0
        }
        
        logger.info(f'Paper Trading Executor initialized | Capital: ')

    async def execute_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        if not self.execution_enabled:
            logger.debug(f'Execution disabled - signal ignored: {signal["symbol"]} {signal["decision"]}')
            return {'status': 'DISABLED', 'reason': 'Execution not enabled'}
        
        if self.kill_switch_triggered:
            logger.error('KILL SWITCH ACTIVE - ALL EXECUTION HALTED')
            return {'status': 'KILLED', 'reason': 'Kill switch active'}
        
        if signal['decision'] == 'HOLD':
            return {'status': 'HOLD'}
        
        self.execution_stats['total_orders'] += 1
        
        symbol = signal['symbol']
        decision = signal['decision']
        confidence = signal['confidence']
        
        position_size = signal.get('position_size', 0.1)
        price = signal['features'].get('close', 100.0)
        
        trade = {
            'symbol': symbol,
            'side': decision,
            'size': position_size,
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
        
        notional = position_size * self.paper_account['equity']
        shares = notional / price

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
            cost = shares * price
            
            if cost > self.paper_account['cash']:
                self.execution_stats['rejected_orders'] += 1
                logger.warning(f'Insufficient cash:  < ')
                return {'status': 'REJECTED', 'reason': 'Insufficient cash'}
            
            self.paper_account['cash'] -= cost
            
            await self.position_manager.update_position(symbol, 'BUY', shares, price)
            
            order_id = self.database.insert_order({
                'symbol': symbol,
                'side': 'BUY',
                'size': shares,
                'price': price,
                'status': 'FILLED'
            })
            
            self.database.insert_fill({
                'order_id': order_id,
                'symbol': symbol,
                'size': shares,
                'price': price
            })
            
            self.execution_stats['executed_orders'] += 1
            
            logger.info(f'EXECUTED BUY: {symbol} | Shares: {shares:.2f} @  | Cost: ')
            
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
            if symbol not in self.position_manager.positions:
                logger.warning(f'No position to sell: {symbol}')
                return {'status': 'REJECTED', 'reason': 'No position'}
            
            position = self.position_manager.positions[symbol]
            sell_shares = min(shares, position['size'])
            
            proceeds = sell_shares * price
            self.paper_account['cash'] += proceeds
            
            await self.position_manager.update_position(symbol, 'SELL', sell_shares, price)
            
            order_id = self.database.insert_order({
                'symbol': symbol,
                'side': 'SELL',
                'size': sell_shares,
                'price': price,
                'status': 'FILLED'
            })
            
            self.database.insert_fill({
                'order_id': order_id,
                'symbol': symbol,
                'size': sell_shares,
                'price': price
            })
            
            pnl = (price - position['avg_price']) * sell_shares
            self.execution_stats['total_pnl'] += pnl
            await self.risk_monitor.update_daily_pnl(pnl)
            
            self.execution_stats['executed_orders'] += 1
            
            logger.info(f'EXECUTED SELL: {symbol} | Shares: {sell_shares:.2f} @  | Proceeds:  | PnL: ')
            
            return {
                'status': 'EXECUTED',
                'order_id': order_id,
                'symbol': symbol,
                'side': 'SELL',
                'shares': sell_shares,
                'price': price,
                'proceeds': proceeds,
                'pnl': pnl
            }

    async def update_equity(self, current_prices: Dict[str, float]):
        unrealized_pnl = await self.position_manager.calculate_unrealized_pnl(current_prices)
        self.paper_account['equity'] = self.paper_account['cash'] + unrealized_pnl

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
