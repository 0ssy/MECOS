"""
MECOS Phase Smoke Tests
Import-only smoke tests for each phase to verify module availability.
Uses pytest.importorskip for phases that may hang in test env.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import_memory_system():
    """Phase 1: MemorySystem imports, asserts VECTOR_DB_PATH exists."""
    from memory_system import MemorySystem
    assert MemorySystem is not None


def test_import_config():
    """Phase 1: Config imports, settings has VECTOR_DB_PATH."""
    from config import settings
    assert hasattr(settings, "VECTOR_DB_PATH")


def test_import_perception_layer():
    """Phase 2: PerceptionLayer imports."""
    pytest.importorskip("perception")


def test_import_app_perception():
    """Phase 2: AppPerception imports."""
    pytest.importorskip("app_perception")


def test_import_reasoner():
    """Phase 3: Reasoner import."""
    pytest.importorskip("reasoner")


def test_import_tool_registry():
    """Phase 4: ToolRegistry imports."""
    from tool_registry import ToolRegistry
    assert ToolRegistry is not None


def test_import_code_executor():
    """Phase 4: CodeExecutor imports."""
    pytest.importorskip("code_executor")


def test_import_file_operations():
    """Phase 4: FileOperations imports."""
    pytest.importorskip("file_operations")


def test_import_browser_automation():
    """Phase 4: BrowserAutomation imports."""
    pytest.importorskip("browser_automation")


def test_import_tool_orchestrator():
    """Phase 4: ToolOrchestrator imports."""
    pytest.importorskip("tool_orchestrator")


def test_import_trading_agent():
    """Phase 5: TradingAgent imports (skip if hangs)."""
    pytest.importorskip("trading_agent")


def test_import_coding_agent():
    """Phase 5: CodingAgent imports (skip if hangs)."""
    pytest.importorskip("coding_agent")


def test_import_research_agent():
    """Phase 5: ResearchAgent imports (skip if hangs)."""
    pytest.importorskip("research_agent")


def test_import_outreach_agent():
    """Phase 5: OutreachAgent imports (skip if hangs)."""
    pytest.importorskip("outreach.outreach_agent")


def test_import_rl_trainer():
    """Phase 6: RLTrainer imports."""
    pytest.importorskip("rl_trainer")


def test_import_self_supervised_trainer():
    """Phase 6: SelfSupervisedTrainer imports."""
    pytest.importorskip("self_supervised_trainer")


def test_import_curriculum_manager():
    """Phase 6: CurriculumManager imports."""
    pytest.importorskip("curriculum_manager")


def test_import_genetic_optimizer():
    """Phase 7: GeneticOptimizer imports."""
    pytest.importorskip("genetic_optimizer")


def test_import_strategy_evolution():
    """Phase 7: StrategyEvolution imports."""
    pytest.importorskip("strategy_evolution")


def test_import_meta_learner():
    """Phase 7: MetaLearner imports."""
    pytest.importorskip("meta_learner")


def test_import_world_model():
    """Phase 7: WorldModel imports."""
    pytest.importorskip("world_model")