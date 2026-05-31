"""
Unified TradingSystem: Central entry point for all trading infrastructure.
Wires up universe, data, execution, risk, adapters, and orchestrators.
"""
from typing import Optional, Dict, Any
from loguru import logger

from runtime import AppDiscovery, AppLearner, UncertaintyFlagger
from reporting import (
    AlertDispatcher,
    DailyReportGenerator,
    MilestoneAlertSystem,
    ReportingScheduler,
    WeeklyReviewGenerator,
)

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
from .openbb_adapter import OpenBBDataAdapter
from .cockpit_app import build_cockpit_snapshot

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
        self.uncertainty_flagger = UncertaintyFlagger(
            confidence_threshold=0.60,
            track_assumptions=True,
            flag_limitations=True,
        )
        self.alert_dispatcher = AlertDispatcher()
        self.alert_dispatcher.register_callback("runtime_log", self._log_alert)
        self.milestone_system = MilestoneAlertSystem(
            self.performance_monitor.tracker,
            self.alert_dispatcher,
        )
        self.daily_report_generator = DailyReportGenerator(
            self.performance_monitor.tracker,
            output_dir="reports/daily",
            goal_equity=self.performance_monitor.tracker.goal_equity,
        )
        self.weekly_review_generator = WeeklyReviewGenerator(
            self.performance_monitor.tracker,
            self.uncertainty_flagger,
            output_dir="reports/weekly",
        )
        self.reporting_scheduler = ReportingScheduler(
            daily_generator=self.daily_report_generator,
            weekly_generator=self.weekly_review_generator,
            dispatcher=self.alert_dispatcher,
            daily_hour=17,
            weekly_day=4,
            weekly_hour=18,
        )
        self.app_discovery = AppDiscovery(cache_dir="data/app_discovery")
        self.app_learner = AppLearner(memory_dir="data/app_workflows")
        self._initialize_app_learning()

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
        self.openbb_adapter = OpenBBDataAdapter()
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
            'uncertainty_flagger': self.uncertainty_flagger,
            'milestone_system': self.milestone_system,
            'daily_report_generator': self.daily_report_generator,
            'weekly_review_generator': self.weekly_review_generator,
            'reporting_scheduler': self.reporting_scheduler,
            'app_discovery': self.app_discovery,
            'app_learner': self.app_learner,
            'executor': self.executor,
            'signal_generator': self.signal_generator,
            'broker_adapter': self.broker_adapter,
            'persona_engine': getattr(self.agent, "persona_engine", None),
            'openbb_adapter': self.openbb_adapter,
            'cockpit_snapshot': self.get_cockpit_snapshot(),
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
            uncertainty_flagger=self.uncertainty_flagger,
            milestone_system=self.milestone_system,
            reporting_scheduler=self.reporting_scheduler,
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

    def get_cockpit_snapshot(self) -> Dict[str, Any]:
        return build_cockpit_snapshot(self)

    def get_external_market_context(self, symbol: str, macro_indicator: str = "DGS10") -> Dict[str, Any]:
        context = {
            "symbol": symbol,
            "macro_indicator": macro_indicator,
            "market_data": self.openbb_adapter.safe_get_market_data(symbol),
            "macro_data": None,
        }
        if self.openbb_adapter.available:
            try:
                context["macro_data"] = self.openbb_adapter.get_macro_data(macro_indicator)
            except Exception as exc:
                logger.warning(f"OpenBB macro data fetch failed for {macro_indicator}: {exc}")
                context["macro_data"] = {"error": str(exc)}
        else:
            context["macro_data"] = {"available": False, "error": "openbb_not_installed"}
        return context

    def _initialize_app_learning(self) -> None:
        try:
            apps = self.app_discovery.scan_installed_apps()
            self.app_discovery.save_discovery()
            if apps:
                self.app_learner.record_workflow(
                    app_name="MECOS",
                    task_description="Daily trading reporting",
                    steps=[
                        "Scan app ecosystem",
                        "Generate reports",
                        "Dispatch milestone and summary alerts",
                    ],
                    success=True,
                )
                self.app_learner.save_workflows()
            logger.info(f"App discovery initialized with {len(apps)} applications")
        except Exception as exc:
            logger.warning(f"App discovery initialization skipped: {exc}")

    @staticmethod
    def _log_alert(title: str, message: str, metadata: Optional[Dict[str, Any]]) -> None:
        logger.info(f"ALERT: {title} | {message} | metadata={metadata or {}}")
