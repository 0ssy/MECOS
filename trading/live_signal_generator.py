import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime, timezone
from trading.confidence_calibrator import ConfidenceCalibrator


class LiveSignalGenerator:
    def __init__(self, trading_agent, data_stream, memory):
        self.trading_agent = trading_agent
        self.data_stream = data_stream
        self.memory = memory

        self.signal_history: List[Dict] = []
        self.validation_mode = True

        # Confidence calibrator: 20s half-life, 0.5% baseline decay per tick
        self.calibrator = ConfidenceCalibrator(
            half_life_seconds=20.0,
            baseline_decay=0.995,
        )

        # Track last signal time per symbol to calculate age
        self._last_signal_time: Dict[str, datetime] = {}

        self.signal_stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
            'avg_confidence': 0.0,
            'avg_raw_confidence': 0.0,
            'calibration_ratio': 1.0,   # calibrated/raw — watch for drift
        }

        logger.info('Live Signal Generator initialized (VALIDATION MODE) | ConfidenceCalibrator active')

    async def on_market_data(self, symbol: str, tick: Dict[str, Any]):
        historical_data = self.data_stream.get_historical_cache(symbol, lookback=100)

        if len(historical_data) < 50:
            logger.debug(f'{symbol}: Insufficient data ({len(historical_data)} bars)')
            return None

        try:
            analysis = await self.trading_agent.analyze_market(symbol, historical_data)
            if analysis is None:
                return None

            decision = analysis.get('decision', analysis.get('final_decision', 'HOLD'))

            if decision == 'HOLD':
                self.signal_stats['total_signals'] += 1
                self.signal_stats['hold_signals'] += 1
                return None

            # --- Signal age: how long since last signal for this symbol ---
            now = datetime.now(timezone.utc)
            last_time = self._last_signal_time.get(symbol)
            age_seconds = (now - last_time).total_seconds() if last_time else 0.0
            self._last_signal_time[symbol] = now

            # --- Calibrate confidence ---
            raw_confidence = float(analysis.get('confidence', 0.0))
            calibrated_confidence = self.calibrator.calibrate(
                raw_confidence=raw_confidence,
                age_seconds=age_seconds,
            )

            signal = {
                'timestamp': now.isoformat(),
                'symbol': symbol,
                'decision': decision,
                'confidence': calibrated_confidence,          # use calibrated downstream
                'raw_confidence': raw_confidence,             # keep for logging/audit
                'age_seconds': age_seconds,
                'regime': analysis.get('regime', 'ranging'),
                'buy_score': analysis.get('buy_score', 0.0),
                'sell_score': analysis.get('sell_score', 0.0),
                'edge': analysis.get('edge', 0.0),
                'expected_move': analysis.get('expected_move', 0.0),
                'spread_pressure': analysis.get('spread_pressure', 0.0),
                'features': analysis.get('features', {}),
                'physics': analysis.get('physics', {}),
                'portfolio': analysis.get('portfolio', {}),
                'allocation': analysis.get('allocation', analysis.get('position_size', 0.1)),
                'volatility': analysis.get('volatility', 0.0),
                'kelly_fraction': analysis.get('kelly_fraction', 0.0),
                'agreement': analysis.get('agreement', 0.0),
            }

            self.signal_history.append(signal)
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]

            self._update_stats(signal, raw_confidence)

            if self.validation_mode:
                self._validate_signal(signal)

            logger.info(
                f'SIGNAL: {symbol} | {decision} | '
                f'conf={calibrated_confidence:.3f} (raw={raw_confidence:.3f}) | '
                f'edge={signal["edge"]:.3f} | regime={signal["regime"]}'
            )

            return signal

        except Exception as e:
            logger.error(f'Signal generation error for {symbol}: {e}')
            return None

    def _update_stats(self, signal: Dict, raw_confidence: float):
        self.signal_stats['total_signals'] += 1
        if signal['decision'] == 'BUY':
            self.signal_stats['buy_signals'] += 1
        elif signal['decision'] == 'SELL':
            self.signal_stats['sell_signals'] += 1
        else:
            self.signal_stats['hold_signals'] += 1

        n = self.signal_stats['total_signals']
        self.signal_stats['avg_confidence'] = (
            self.signal_stats['avg_confidence'] * (n - 1) + signal['confidence']
        ) / n
        self.signal_stats['avg_raw_confidence'] = (
            self.signal_stats['avg_raw_confidence'] * (n - 1) + raw_confidence
        ) / n
        if self.signal_stats['avg_raw_confidence'] > 1e-6:
            self.signal_stats['calibration_ratio'] = (
                self.signal_stats['avg_confidence'] /
                self.signal_stats['avg_raw_confidence']
            )

    def _validate_signal(self, signal: Dict):
        conf = signal['confidence']
        raw  = signal['raw_confidence']
        sym  = signal['symbol']
        dec  = signal['decision']

        if raw > 0.9:
            logger.warning(
                f'HIGH RAW CONFIDENCE: {sym} {dec} raw={raw:.3f} -> calibrated={conf:.3f}'
            )
        if dec != 'HOLD' and conf < 0.3:
            logger.warning(f'LOW CALIBRATED CONFIDENCE: {sym} {dec} conf={conf:.3f}')
        if signal['edge'] < 0.10 and dec != 'HOLD':
            logger.warning(
                f'WEAK EDGE: {sym} {dec} edge={signal["edge"]:.3f} '
                f'(below 0.10 threshold)'
            )

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.signal_stats,
            'signal_history_count': len(self.signal_history),
        }

    def enable_live_mode(self):
        self.validation_mode = False
        logger.warning('VALIDATION MODE DISABLED - LIVE SIGNAL MODE ENABLED')

    def disable_live_mode(self):
        self.validation_mode = True
        logger.info('LIVE MODE DISABLED - VALIDATION MODE ENABLED')
