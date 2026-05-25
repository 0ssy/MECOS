"""
MECOS Full System Test Suite
Tests all 7 phases: memory, perception, reasoning, tools, agents, learning, evolution.
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from memory_system import MemorySystem
from tool_orchestrator import ToolOrchestrator
from tool_registry import ToolRegistry, ToolSpec, ToolPermission
from code_executor import CodeExecutor
from file_operations import FileOperations
from app_controller import AppController
from trading_agent import TradingAgent
from coding_agent import CodingAgent, SyntaxAnalyzer
from research_agent import ResearchAgent, KnowledgeGraph
from agent_coordinator import AgentCoordinator, AgentRole
from rl_trainer import RLTrainer, QTable, ReplayBuffer
from self_supervised_trainer import SelfSupervisedTrainer
from curriculum_manager import CurriculumManager, SkillLevel
from memory_consolidation import MemoryConsolidation
from benchmarking import BenchmarkingEngine, BenchmarkTask
from genetic_optimizer import GeneticOptimizer, Individual
from strategy_evolution import StrategyEvolution, Strategy
from checkpoint_manager import CheckpointManager
from world_model import WorldModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def memory():
    return MemorySystem()


@pytest.fixture
def orchestrator():
    return ToolOrchestrator()


# ── Phase 1: Memory System ────────────────────────────────────────────────────

class TestMemorySystem:
    def test_initialization(self, memory):
        assert memory is not None

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self, memory):
        await memory.add_experience("Test experience for MECOS", source="test")
        result = await memory.retrieve_context("MECOS experience")
        assert result is not None


# ── Phase 4: Tool Registry ────────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        async def dummy_fn(x: str) -> str:
            return x

        spec = ToolSpec(
            name="test_tool",
            description="A test tool",
            func=dummy_fn,
            parameters={"x": "input"},
            permissions=ToolPermission(),
            category="test",
        )
        registry.register(spec)
        retrieved = registry.get("test_tool")
        assert retrieved is not None
        assert retrieved.name == "test_tool"

    def test_list_tools(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert isinstance(tools, list)

    def test_enable_disable(self):
        registry = ToolRegistry()
        async def dummy_fn() -> str:
            return "ok"
        spec = ToolSpec(name="toggle_tool", description="Toggle", func=dummy_fn, parameters={})
        registry.register(spec)
        registry.disable("toggle_tool")
        assert not registry.get("toggle_tool").enabled
        registry.enable("toggle_tool")
        assert registry.get("toggle_tool").enabled


# ── Phase 4: Code Executor ────────────────────────────────────────────────────

class TestCodeExecutor:
    @pytest.mark.asyncio
    async def test_python_execution(self):
        executor = CodeExecutor()
        result = await executor.execute_python("print('hello mecos')")
        assert result.success
        assert "hello mecos" in result.stdout

    @pytest.mark.asyncio
    async def test_python_error(self):
        executor = CodeExecutor()
        result = await executor.execute_python("raise ValueError('test error')")
        assert not result.success
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_bash_execution(self):
        executor = CodeExecutor()
        result = await executor.execute_bash("echo 'bash works'")
        assert result.success
        assert "bash works" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout(self):
        executor = CodeExecutor()
        result = await executor.execute_python("import time; time.sleep(100)", timeout=2)
        assert not result.success
        assert "timed out" in result.stderr.lower()


# ── Phase 4: File Operations ──────────────────────────────────────────────────

class TestFileOperations:
    def test_write_and_read(self):
        ops = FileOperations()
        ops.write_text("test_file.txt", "hello world", backup=False)
        content = ops.read_text("test_file.txt")
        assert content == "hello world"

    def test_path_traversal_blocked(self):
        ops = FileOperations()
        with pytest.raises(PermissionError):
            ops.read_text("../../etc/passwd")

    def test_list_directory(self):
        ops = FileOperations()
        ops.write_text("list_test.txt", "content", backup=False)
        files = ops.list_directory()
        assert isinstance(files, list)

    def test_search_files(self):
        ops = FileOperations()
        ops.write_text("search_test.txt", "unique_search_term_xyz", backup=False)
        results = ops.search_files("unique_search_term_xyz")
        assert len(results) > 0

    def test_delete_file(self):
        ops = FileOperations()
        ops.write_text("delete_me.txt", "temp", backup=False)
        deleted = ops.delete_file("delete_me.txt", backup=False)
        assert deleted


# ── Phase 4: App Controller ───────────────────────────────────────────────────

class TestAppController:
    @pytest.mark.asyncio
    async def test_allowed_command(self):
        controller = AppController()
        result = await controller.run_command("echo test_output")
        assert "test_output" in result["stdout"]

    @pytest.mark.asyncio
    async def test_blocked_command(self):
        controller = AppController()
        result = await controller.run_command("rm -rf /")
        assert result["exit_code"] == "-1"
        assert "allowlist" in result["stderr"].lower()

    def test_system_info(self):
        controller = AppController()
        info = controller.get_system_info()
        assert "cpu_percent" in info
        assert "memory_used" in info


# ── Phase 4: Tool Orchestrator ────────────────────────────────────────────────

class TestToolOrchestrator:
    def test_initialization(self, orchestrator):
        assert orchestrator is not None
        tools = orchestrator.registry.list_tools()
        assert len(tools) >= 10

    @pytest.mark.asyncio
    async def test_execute_python_tool(self, orchestrator):
        result = await orchestrator.run_tool("execute_python", code="print(2 + 2)")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_system_info_tool(self, orchestrator):
        result = await orchestrator.run_tool("system_info")
        assert "cpu_percent" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self, orchestrator):
        result = await orchestrator.run_tool("nonexistent_tool")
        assert "Unknown tool" in result

    def test_describe_tools(self, orchestrator):
        desc = orchestrator.describe_tools()
        assert len(desc) > 0
        assert "execute_python" in desc


# ── Phase 5: Syntax Analyzer ─────────────────────────────────────────────────

class TestSyntaxAnalyzer:
    def test_valid_code(self):
        analyzer = SyntaxAnalyzer()
        result = analyzer.analyze("def foo(x):\n    return x * 2\n")
        assert result["valid"]
        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "foo"

    def test_invalid_code(self):
        analyzer = SyntaxAnalyzer()
        result = analyzer.analyze("def broken(:")
        assert not result["valid"]
        assert "error" in result

    def test_bug_detection(self):
        analyzer = SyntaxAnalyzer()
        code = "try:\n    pass\nexcept:\n    pass\n"
        bugs = analyzer.find_bugs(code)
        assert any("bare" in b.lower() or "except" in b.lower() for b in bugs)


# ── Phase 5: Knowledge Graph ──────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_add_and_query(self):
        kg = KnowledgeGraph()
        kg.add_entity("Python", "language", "A programming language")
        kg.add_relation("Python", "is_a", "Programming Language")
        result = kg.query("Python")
        assert result["entity"] == "Python"
        assert len(result["relations"]) >= 1

    def test_summary(self):
        kg = KnowledgeGraph()
        kg.add_entity("AI", "concept")
        summary = kg.summary()
        assert "1" in summary


# ── Phase 6: Q-Table ─────────────────────────────────────────────────────────

class TestQTable:
    def test_update_and_get(self):
        qt = QTable()
        qt.update("state1", "action1", 1.0, "state2", ["action1", "action2"])
        q_val = qt.get_q("state1", "action1")
        assert q_val > 0

    def test_get_action(self):
        qt = QTable()
        qt.update("s", "a1", 1.0, "s2", ["a1", "a2"])
        qt.update("s", "a2", -1.0, "s2", ["a1", "a2"])
        best = qt.predict("s", ["a1", "a2"])
        assert best == "a1"


# ── Phase 6: Replay Buffer ────────────────────────────────────────────────────

class TestReplayBuffer:
    def test_push_and_sample(self):
        buf = ReplayBuffer(capacity=100)
        for i in range(10):
            buf.push(f"s{i}", f"a{i}", float(i), f"s{i+1}", False)
        assert len(buf) == 10
        sample = buf.sample(5)
        assert len(sample) == 5


# ── Phase 6: Curriculum Manager ──────────────────────────────────────────────

class TestCurriculumManager:
    def test_get_next_task(self, memory):
        cm = CurriculumManager(memory)
        task = cm.get_next_task("coding")
        assert task is not None
        assert "task" in task

    @pytest.mark.asyncio
    async def test_record_performance(self, memory):
        cm = CurriculumManager(memory)
        result = await cm.record_performance("coding", 0.8, "test task")
        assert "level" in result
        assert "next_task" in result

    def test_skill_levels(self):
        assert SkillLevel.from_score(0.0) == SkillLevel.NOVICE
        assert SkillLevel.from_score(0.5) == SkillLevel.BEGINNER
        assert SkillLevel.from_score(0.65) == SkillLevel.INTERMEDIATE
        assert SkillLevel.from_score(0.8) == SkillLevel.ADVANCED
        assert SkillLevel.from_score(0.95) == SkillLevel.EXPERT


# ── Phase 7: Genetic Optimizer ───────────────────────────────────────────────

class TestGeneticOptimizer:
    def test_initialize_population(self, memory):
        optimizer = GeneticOptimizer(memory, population_size=5)
        template = {
            "lr": {"type": "float", "min": 0.001, "max": 0.1},
            "epochs": {"type": "int", "min": 1, "max": 10},
        }
        pop = optimizer.initialize_population(template)
        assert len(pop) == 5
        for ind in pop:
            assert "lr" in ind.genome
            assert "epochs" in ind.genome

    @pytest.mark.asyncio
    async def test_evolve(self, memory):
        optimizer = GeneticOptimizer(memory, population_size=4)
        template = {"x": {"type": "float", "min": 0.0, "max": 1.0}}

        def fitness(genome):
            return genome["x"]  # Maximize x

        best = await optimizer.evolve(fitness, template, n_generations=3)
        assert best.fitness > 0
        assert 0.0 <= best.genome["x"] <= 1.0


# ── Phase 7: Checkpoint Manager ──────────────────────────────────────────────

class TestCheckpointManager:
    @pytest.mark.asyncio
    async def test_create_and_list(self):
        cm = CheckpointManager()
        ckpt_id = await cm.create_checkpoint(label="test_checkpoint")
        assert ckpt_id.startswith("ckpt_")
        checkpoints = cm.list_checkpoints()
        assert any(c["id"] == ckpt_id for c in checkpoints)

    @pytest.mark.asyncio
    async def test_restore(self):
        cm = CheckpointManager()
        ckpt_id = await cm.create_checkpoint(label="restore_test")
        success = await cm.restore_checkpoint(ckpt_id)
        assert success


# ── Phase 7: World Model ─────────────────────────────────────────────────────

class TestWorldModel:
    def test_record_and_lookup(self, memory):
        wm = WorldModel(memory)
        wm.record_transition("state_A", "action_X", "outcome_Y", "state_B", reward=1.0)
        outcomes = wm.lookup_outcomes("state_A", "action_X")
        assert "outcome_Y" in outcomes

    @pytest.mark.asyncio
    async def test_simulate_plan(self, memory):
        wm = WorldModel(memory)
        plan = [
            {"tool": "execute_python", "args": {"code": "print('hello')"}},
            {"tool": "file_write", "args": {"path": "out.txt", "content": "test"}},
        ]
        results = await wm.simulate_plan("initial state", plan)
        assert len(results) == 2
        for r in results:
            assert "predicted_outcome" in r
            assert "predicted_success" in r

    def test_model_stats(self, memory):
        wm = WorldModel(memory)
        stats = wm.get_model_stats()
        assert "total_transitions" in stats
        assert "unique_states" in stats


# ── Integration Test ──────────────────────────────────────────────────────────

class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_tool_chain(self, orchestrator):
        """Test a chain of tool operations."""
        # Write a file
        write_result = await orchestrator.run_tool(
            "file_write", path="integration_test.txt", content="MECOS integration test"
        )
        assert "written" in write_result.lower() or "error" not in write_result.lower()

        # Read it back
        read_result = await orchestrator.run_tool("file_read", path="integration_test.txt")
        assert "MECOS integration test" in read_result

        # Execute code that uses the file
        code = "print('Integration test passed')"
        exec_result = await orchestrator.run_tool("execute_python", code=code)
        assert "Integration test passed" in exec_result

    @pytest.mark.asyncio
    async def test_rl_curriculum_integration(self, memory):
        """Test RL trainer and curriculum manager working together."""
        rl = RLTrainer(memory, domain="coding")
        cm = CurriculumManager(memory)

        # Get a task
        task = cm.get_next_task("coding")
        assert task is not None

        # Simulate executing the task
        action = rl.choose_action("coding_novice", ["generate_code", "analyze_code", "run_tests"])
        assert action in ["generate_code", "analyze_code", "run_tests"]

        # Record outcome
        rl.record_experience(
            state="coding_novice",
            action=action,
            outcome={"success": True},
            next_state="coding_beginner",
        )

        # Update curriculum
        result = await cm.record_performance("coding", 0.7, task["task"])
        assert result["level"] in SkillLevel.LEVELS
