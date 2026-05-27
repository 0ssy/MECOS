"""
Unified TradingSystem: Central entry point for all trading infrastructure.
Wires up universe, data, execution, risk, adapters, and orchestrators.
"""
from typing import Optional, Dict, Any
from loguru import logger

from .universe_manager import UniverseManager
from .universe_scanner import UniverseScanner
from .market_data_stream import MarketDataStream
from .live_signal_generator import LiveSignalGenerator
from .paper_trading_executor import PaperTradingExecutor
from .risk_monitor import RiskMonitor
from .performance_monitor import PerformanceMonitor
from .position_manager import PositionManager
from .order_manager import OrderManager
from .trade_database import TradeDatabase
from .trading_agent import TradingAgent
from .broker.multi_broker_adapter import MultiBrokerAdapter
from .broker.base_adapter import BrokerAdapter

class TradingSystem:
    def __init__(
        self,
        memory_system=None,
        broker_adapter: Optional[BrokerAdapter] = None,
        quant_mode: str = 'balanced',
        execution_mode: str = 'paper',
    ):
        self.memory = memory_system
        self.quant_mode = quant_mode
        self.execution_mode = str(execution_mode or 'paper').strip().lower()
        self.db = TradeDatabase()
        self.agent = TradingAgent(self.memory, quant_mode=self.quant_mode)
        self.stream = MarketDataStream()
        self.universe_manager = UniverseManager(self.memory)
        self.universe_scanner = UniverseScanner(self.universe_manager, self.stream)
        self.position_manager = PositionManager(self.db)
        self.order_manager = OrderManager(self.db)
        self.risk_monitor = RiskMonitor()
        self.performance_monitor = PerformanceMonitor(self.db)

        # Broker adapter (multi-broker live routing: IBKR + Alpaca + Binance)
        self.broker_adapter = broker_adapter or MultiBrokerAdapter()
        self.stream.set_broker_adapter(self.broker_adapter)
        self.executor = PaperTradingExecutor(
            self.db,
            self.position_manager,
            self.risk_monitor,
            self.memory,
            self.order_manager,
            broker_adapter=self.broker_adapter,
            execution_mode=self.execution_mode,
        )
        self.signal_generator = LiveSignalGenerator(self.agent, self.stream, self.memory)
        logger.info(
            f"TradingSystem initialized with broker adapter: {type(self.broker_adapter).__name__} "
            f"| execution_mode={self.execution_mode.upper()}"
        )

    def get_components(self) -> Dict[str, Any]:
        return {
            'memory': self.memory,
            'db': self.db,
            'agent': self.agent,
            'stream': self.stream,
            'universe_manager': self.universe_manager,
            'universe_scanner': self.universe_scanner,
            'position_manager': self.position_manager,
            'order_manager': self.order_manager,
            'risk_monitor': self.risk_monitor,
            'performance_monitor': self.performance_monitor,
            'executor': self.executor,
            'signal_generator': self.signal_generator,
            'broker_adapter': self.broker_adapter,
        }

    async def start(self, use_starter_universe: bool = True):
        from .autonomous_trading_loop import AutonomousTradingLoop
        self.loop = AutonomousTradingLoop(
            self.stream,
            self.signal_generator,
            self.executor,
            self.performance_monitor,
            self.db,
            self.universe_manager,
            self.universe_scanner,
            quant_mode=self.quant_mode,
        )
        await self.loop.start(use_starter_universe=use_starter_universe)

    def stop(self):
        if hasattr(self, 'loop'):
            self.loop.stop()

    def get_status(self) -> Dict[str, Any]:
        if hasattr(self, 'loop'):
            return self.loop.get_status()
        return {}
