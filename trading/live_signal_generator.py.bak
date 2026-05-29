import asyncio
from typing import Dict, Any, List
from loguru import logger
from datetime import datetime

class LiveSignalGenerator:
    def __init__(self, trading_agent, data_stream, memory):
        self.trading_agent = trading_agent
        self.data_stream = data_stream
        self.memory = memory
        
        self.signal_history = []
        self.validation_mode = True
        
        self.signal_stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
            'avg_confidence': 0
        }
        
        logger.info('Live Signal Generator initialized (VALIDATION MODE)')

    async def on_market_data(self, symbol: str, tick: Dict[str, Any]):
        historical_data = self.data_stream.get_historical_cache(symbol, lookback=100)
        
        if len(historical_data) < 50:
            logger.debug(f'{symbol}: Insufficient data ({len(historical_data)} bars)')
            return
        
        try:
            analysis = await self.trading_agent.analyze_market(symbol, historical_data)
            if analysis is None:
                return None

            decision = analysis.get('decision', analysis.get('final_decision', 'HOLD'))
            if decision == 'HOLD':
                self.signal_stats['total_signals'] += 1
                self.signal_stats['hold_signals'] += 1
                return None
            
            signal = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'decision': decision,
                'confidence': analysis.get('confidence', 0.0),
                'regime': analysis.get('regime', 'unknown'),
                'buy_score': analysis.get('buy_score', 0.0),
                'sell_score': analysis.get('sell_score', 0.0),
                'edge': analysis.get('edge', 0.0),
                'expected_move': analysis.get('expected_move', 0.0),
                'spread_pressure': analysis.get('spread_pressure', 0.0),
                'features': analysis.get('features', {}),
                'physics': analysis.get('physics', {}),
                'portfolio': analysis.get('portfolio', {}),
                'allocation': analysis.get('allocation', analysis.get('position_size', 0.1)),
                'volatility': analysis.get('volatility', 0.0)
            }
            
            self.signal_history.append(signal)
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]
            
            self._update_stats(signal)
            
            if self.validation_mode:
                self._validate_signal(signal)
            
            logger.info(f'SIGNAL: {symbol} | {signal["decision"]} | Conf: {signal["confidence"]:.2f}')
            
            return signal
            
        except Exception as e:
            logger.error(f'Signal generation error for {symbol}: {e}')
            return None

    def _update_stats(self, signal: Dict):
        self.signal_stats['total_signals'] += 1
        
        if signal['decision'] == 'BUY':
            self.signal_stats['buy_signals'] += 1
        elif signal['decision'] == 'SELL':
            self.signal_stats['sell_signals'] += 1
        else:
            self.signal_stats['hold_signals'] += 1
        
        n = self.signal_stats['total_signals']
        old_avg = self.signal_stats['avg_confidence']
        self.signal_stats['avg_confidence'] = (old_avg * (n - 1) + signal['confidence']) / n

    def _validate_signal(self, signal: Dict):
        if signal['confidence'] > 0.9:
            logger.warning(f'HIGH CONFIDENCE SIGNAL: {signal["symbol"]} {signal["decision"]} @ {signal["confidence"]:.2f}')
        
        if signal['decision'] != 'HOLD' and signal['confidence'] < 0.3:
            logger.warning(f'LOW CONFIDENCE ACTION: {signal["symbol"]} {signal["decision"]} @ {signal["confidence"]:.2f}')

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.signal_stats,
            'signal_history_count': len(self.signal_history)
        }

    def enable_live_mode(self):
        self.validation_mode = False
        logger.warning('VALIDATION MODE DISABLED - LIVE SIGNAL MODE ENABLED')

    def disable_live_mode(self):
        self.validation_mode = True
        logger.info('LIVE MODE DISABLED - VALIDATION MODE ENABLED')
