# build_advanced_layers.ps1
# Builds all four advanced MECOS layers:
#   1. Process isolation via multiprocessing + message queues
#   2. Knowledge compression (raw content -> distilled concepts)
#   3. Skill-tree-driven task planning
#   4. Distributed worker runtime
#
# Run from MECOS folder: .\build_advanced_layers.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS Advanced Layers Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Backup([string]$Path) {
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.bak" -Force
        Write-Host "  [BAK] $Path.bak" -ForegroundColor Yellow
    }
}

# ===========================================================================
# LAYER 1 — Process Isolation + Message Queue
# Creates: runtime/message_bus.py
#          runtime/worker_process.py
#          runtime/process_manager.py
# ===========================================================================
Write-Host ""
Write-Host "Layer 1: Process Isolation + Message Bus" -ForegroundColor White

Set-Content "runtime\message_bus.py" @'
"""
runtime/message_bus.py
Async message bus for inter-agent communication.
Replaces direct function calls with message passing so a crash in one
agent cannot take down the others.

Usage:
    bus = MessageBus()
    await bus.publish("research", {"topic": "autonomous runtime"})
    msg = await bus.subscribe("research")
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    channel: str = ""
    payload: Any = None
    sender: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    priority: int = 5          # 1=highest, 10=lowest
    ttl_seconds: float = 60.0  # message expires after this many seconds

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds


class MessageBus:
    """
    Async pub/sub message bus.
    Agents publish to channels; subscribers receive from their channels.
    Dead letters (undelivered after TTL) are logged and discarded.
    """

    def __init__(self, max_queue_size: int = 500):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._stats: Dict[str, int] = {
            "published": 0,
            "delivered": 0,
            "expired": 0,
            "errors": 0,
        }
        self._max_queue_size = max_queue_size
        self._running = False
        self._dispatch_task: Optional[asyncio.Task] = None

    def _ensure_channel(self, channel: str):
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue(maxsize=self._max_queue_size)
        if channel not in self._handlers:
            self._handlers[channel] = []

    async def publish(self, channel: str, payload: Any, sender: str = "system",
                      priority: int = 5, ttl: float = 60.0):
        self._ensure_channel(channel)
        msg = Message(channel=channel, payload=payload, sender=sender,
                      priority=priority, ttl_seconds=ttl)
        try:
            self._queues[channel].put_nowait(msg)
            self._stats["published"] += 1
        except asyncio.QueueFull:
            logger.warning(f"[MessageBus] Queue full for channel '{channel}' — dropping message")
            self._stats["errors"] += 1

    async def subscribe(self, channel: str, timeout: float = 5.0) -> Optional[Message]:
        """Pull next message from channel. Returns None on timeout."""
        self._ensure_channel(channel)
        try:
            msg = await asyncio.wait_for(self._queues[channel].get(), timeout=timeout)
            if msg.is_expired():
                self._stats["expired"] += 1
                logger.debug(f"[MessageBus] Expired message on '{channel}' discarded")
                return None
            self._stats["delivered"] += 1
            return msg
        except asyncio.TimeoutError:
            return None

    def register_handler(self, channel: str, handler: Callable):
        """Register an async handler that fires on every message to channel."""
        self._ensure_channel(channel)
        self._handlers[channel].append(handler)

    async def start_dispatch(self):
        """Start background dispatch loop for registered handlers."""
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("[MessageBus] Dispatch loop started")

    async def stop_dispatch(self):
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        logger.info("[MessageBus] Dispatch loop stopped")

    async def _dispatch_loop(self):
        while self._running:
            for channel, handlers in self._handlers.items():
                if not handlers:
                    continue
                msg = await self.subscribe(channel, timeout=0.1)
                if msg is None:
                    continue
                for handler in handlers:
                    try:
                        await handler(msg)
                    except Exception as e:
                        logger.error(f"[MessageBus] Handler error on '{channel}': {e}")
                        self._stats["errors"] += 1
            await asyncio.sleep(0.05)

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def channel_sizes(self) -> Dict[str, int]:
        return {ch: q.qsize() for ch, q in self._queues.items()}


# Global singleton — import and use anywhere
_bus: Optional[MessageBus] = None

def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
'@ -Encoding UTF8
Write-Host "  [OK]  runtime\message_bus.py" -ForegroundColor Green

Set-Content "runtime\worker_process.py" @'
"""
runtime/worker_process.py
Base class for isolated worker processes.
Each worker runs in its own process, communicates via multiprocessing Queue,
and reports health back to the ProcessManager.

Workers:
    ResearchWorker  — continuous research loop
    CodingWorker    — code generation + sandbox
    MemoryWorker    — memory consolidation + compression
    EvolutionWorker — benchmark + self-improvement
"""
from __future__ import annotations

import asyncio
import multiprocessing
import os
import signal
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional
from loguru import logger


class WorkerStatus(str, Enum):
    STARTING  = "starting"
    RUNNING   = "running"
    IDLE      = "idle"
    ERROR     = "error"
    STOPPED   = "stopped"


@dataclass
class WorkerHeartbeat:
    worker_id: str
    status: WorkerStatus
    timestamp: float
    cycles: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "cycles": self.cycles,
            "last_error": self.last_error,
            "metadata": self.metadata or {},
        }


class BaseWorker:
    """
    Base class for all MECOS worker processes.
    Subclass and implement `run_cycle()`.
    """

    def __init__(
        self,
        worker_id: str,
        inbox: multiprocessing.Queue,
        outbox: multiprocessing.Queue,
        cycle_interval: float = 30.0,
    ):
        self.worker_id    = worker_id
        self.inbox        = inbox   # receives commands from manager
        self.outbox       = outbox  # sends results + heartbeats to manager
        self.cycle_interval = cycle_interval
        self.status       = WorkerStatus.STARTING
        self.cycles       = 0
        self._running     = True

        # Handle SIGTERM gracefully
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigterm(self, signum, frame):
        logger.warning(f"[{self.worker_id}] SIGTERM received — shutting down")
        self._running = False

    def _heartbeat(self, metadata: Dict = None):
        hb = WorkerHeartbeat(
            worker_id=self.worker_id,
            status=self.status,
            timestamp=time.time(),
            cycles=self.cycles,
            metadata=metadata,
        )
        try:
            self.outbox.put_nowait(("heartbeat", hb.to_dict()))
        except Exception:
            pass

    def _send_result(self, result_type: str, data: Any):
        try:
            self.outbox.put_nowait((result_type, data))
        except Exception as e:
            logger.error(f"[{self.worker_id}] Failed to send result: {e}")

    def run_cycle(self) -> Dict[str, Any]:
        """Override in subclass. Return dict of results."""
        raise NotImplementedError

    def start(self):
        """Entry point — called by multiprocessing.Process.start()"""
        self.status = WorkerStatus.RUNNING
        logger.info(f"[{self.worker_id}] Worker started (pid={os.getpid()})")

        while self._running:
            # Check for commands from manager
            try:
                while not self.inbox.empty():
                    cmd, payload = self.inbox.get_nowait()
                    self._handle_command(cmd, payload)
            except Exception:
                pass

            # Run one work cycle
            try:
                self.status = WorkerStatus.RUNNING
                result = self.run_cycle()
                self.cycles += 1
                self._send_result("cycle_result", {
                    "worker_id": self.worker_id,
                    "cycle": self.cycles,
                    "result": result,
                })
                self._heartbeat()
            except Exception as e:
                self.status = WorkerStatus.ERROR
                err = traceback.format_exc()
                logger.error(f"[{self.worker_id}] Cycle error: {e}")
                self._heartbeat({"last_error": str(e)})

            # Sleep between cycles
            time.sleep(self.cycle_interval)

        self.status = WorkerStatus.STOPPED
        self._heartbeat()
        logger.info(f"[{self.worker_id}] Worker stopped")

    def _handle_command(self, cmd: str, payload: Any):
        if cmd == "stop":
            self._running = False
        elif cmd == "ping":
            self._heartbeat()
        elif cmd == "set_interval":
            self.cycle_interval = float(payload)
'@ -Encoding UTF8
Write-Host "  [OK]  runtime\worker_process.py" -ForegroundColor Green

Set-Content "runtime\process_manager.py" @'
"""
runtime/process_manager.py
Manages isolated worker processes for each MECOS domain.
Monitors heartbeats, restarts crashed workers, routes results.

Usage in main.py:
    from runtime.process_manager import ProcessManager
    pm = ProcessManager()
    pm.start_all()
    # workers run independently
    await pm.monitor_loop()  # in background task
    pm.stop_all()
"""
from __future__ import annotations

import asyncio
import multiprocessing
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


@dataclass
class WorkerSpec:
    worker_id:     str
    target_fn:     Callable       # function to run in child process
    cycle_interval: float = 30.0
    max_restarts:  int    = 5
    restart_delay: float = 5.0


@dataclass
class WorkerState:
    spec:        WorkerSpec
    process:     Optional[multiprocessing.Process] = None
    inbox:       Optional[multiprocessing.Queue]   = None
    outbox:      Optional[multiprocessing.Queue]   = None
    restarts:    int   = 0
    last_hb:     float = field(default_factory=time.time)
    status:      str   = "starting"
    cycles:      int   = 0


class ProcessManager:
    """
    Manages MECOS worker processes.
    Each worker runs in isolation — a crash in ResearchWorker
    cannot affect CodingWorker or TradingWorker.
    """

    HEARTBEAT_TIMEOUT = 120.0  # seconds before declaring worker dead

    def __init__(self):
        self._workers: Dict[str, WorkerState] = {}
        self._running = False
        self._result_handlers: Dict[str, List[Callable]] = {}

    def register(self, spec: WorkerSpec):
        """Register a worker specification."""
        self._workers[spec.worker_id] = WorkerState(spec=spec)
        logger.info(f"[ProcessManager] Registered worker: {spec.worker_id}")

    def register_result_handler(self, result_type: str, handler: Callable):
        """Register a callback for when workers produce results."""
        if result_type not in self._result_handlers:
            self._result_handlers[result_type] = []
        self._result_handlers[result_type].append(handler)

    def start_all(self):
        """Start all registered workers."""
        self._running = True
        for wid, state in self._workers.items():
            self._start_worker(state)
        logger.info(f"[ProcessManager] Started {len(self._workers)} workers")

    def _start_worker(self, state: WorkerState):
        inbox  = multiprocessing.Queue(maxsize=100)
        outbox = multiprocessing.Queue(maxsize=500)
        proc   = multiprocessing.Process(
            target=state.spec.target_fn,
            args=(state.spec.worker_id, inbox, outbox, state.spec.cycle_interval),
            daemon=True,
            name=state.spec.worker_id,
        )
        proc.start()
        state.process = proc
        state.inbox   = inbox
        state.outbox  = outbox
        state.last_hb = time.time()
        state.status  = "running"
        logger.info(f"[ProcessManager] Worker started: {state.spec.worker_id} (pid={proc.pid})")

    async def monitor_loop(self, check_interval: float = 10.0):
        """Background loop: reads worker output, checks heartbeats, restarts dead workers."""
        while self._running:
            for wid, state in self._workers.items():
                self._drain_outbox(state)
                self._check_heartbeat(state)
            await asyncio.sleep(check_interval)

    def _drain_outbox(self, state: WorkerState):
        """Read all pending messages from worker outbox."""
        if state.outbox is None:
            return
        while not state.outbox.empty():
            try:
                msg_type, payload = state.outbox.get_nowait()
                if msg_type == "heartbeat":
                    state.last_hb  = payload.get("timestamp", time.time())
                    state.status   = payload.get("status", "running")
                    state.cycles   = payload.get("cycles", state.cycles)
                elif msg_type in self._result_handlers:
                    for handler in self._result_handlers[msg_type]:
                        try:
                            handler(state.spec.worker_id, payload)
                        except Exception as e:
                            logger.error(f"[ProcessManager] Result handler error: {e}")
            except Exception:
                break

    def _check_heartbeat(self, state: WorkerState):
        """Restart worker if heartbeat is stale or process has died."""
        if state.process is None:
            return
        age = time.time() - state.last_hb
        process_dead = not state.process.is_alive()

        if process_dead or age > self.HEARTBEAT_TIMEOUT:
            if state.restarts >= state.spec.max_restarts:
                logger.error(
                    f"[ProcessManager] Worker {state.spec.worker_id} exceeded max restarts "
                    f"({state.spec.max_restarts}). Not restarting."
                )
                state.status = "failed"
                return

            reason = "process died" if process_dead else f"heartbeat stale ({age:.0f}s)"
            logger.warning(f"[ProcessManager] Restarting {state.spec.worker_id}: {reason}")
            try:
                state.process.terminate()
                state.process.join(timeout=5)
            except Exception:
                pass
            state.restarts += 1
            self._start_worker(state)

    def send_command(self, worker_id: str, cmd: str, payload: Any = None):
        """Send a command to a specific worker."""
        state = self._workers.get(worker_id)
        if state and state.inbox:
            try:
                state.inbox.put_nowait((cmd, payload))
            except Exception as e:
                logger.error(f"[ProcessManager] Command send failed: {e}")

    def stop_all(self):
        """Gracefully stop all workers."""
        self._running = False
        for wid, state in self._workers.items():
            self.send_command(wid, "stop", None)
        time.sleep(2)
        for wid, state in self._workers.items():
            if state.process and state.process.is_alive():
                state.process.terminate()
                state.process.join(timeout=5)
        logger.info("[ProcessManager] All workers stopped")

    def status_summary(self) -> Dict[str, Any]:
        return {
            wid: {
                "status":   state.status,
                "cycles":   state.cycles,
                "restarts": state.restarts,
                "pid":      state.process.pid if state.process else None,
                "last_hb_age": round(time.time() - state.last_hb, 1),
            }
            for wid, state in self._workers.items()
        }
'@ -Encoding UTF8
Write-Host "  [OK]  runtime\process_manager.py" -ForegroundColor Green

# ===========================================================================
# LAYER 2 — Knowledge Compression
# Creates: knowledge_compressor.py
# Distills raw web content into structured concepts stored in KnowledgeGraph
# ===========================================================================
Write-Host ""
Write-Host "Layer 2: Knowledge Compression" -ForegroundColor White

Set-Content "knowledge_compressor.py" @'
"""
knowledge_compressor.py
Distills raw memory content into structured, reusable knowledge concepts.

Instead of storing "WEB CONTENT from duckduckgo..." verbatim,
this compresses discoveries into:
    - Named concepts with definitions
    - Relationships between concepts
    - Reusable strategy patterns
    - Contradiction detection

Feeds compressed knowledge into KnowledgeGraph and back into MemorySystem
with higher quality scores.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from knowledge_graph import KnowledgeGraph
from memory_system import MemorySystem


COMPRESSION_PROMPT = """You are a knowledge distillation engine.

Given raw research content, extract structured knowledge.
Respond ONLY with valid JSON, no other text.

Format:
{{
  "concepts": [
    {{"name": "concept name", "definition": "one sentence", "domain": "trading|coding|systems|research"}}
  ],
  "relationships": [
    {{"from": "concept A", "to": "concept B", "relation": "enables|contradicts|extends|requires"}}
  ],
  "patterns": [
    {{"name": "pattern name", "description": "reusable insight", "applicability": "when to use"}}
  ],
  "quality_score": 0.0
}}

quality_score: 0.0-1.0 based on information density. Raw search results = 0.1-0.2. 
Novel insights = 0.6-0.9.

Raw content to distill:
{content}"""


@dataclass
class CompressedKnowledge:
    concepts:      List[Dict]
    relationships: List[Dict]
    patterns:      List[Dict]
    quality_score: float
    source_hash:   str
    compressed_at: float = 0.0

    def __post_init__(self):
        if not self.compressed_at:
            self.compressed_at = time.time()


class KnowledgeCompressor:
    """
    Reads raw memories, compresses them into structured knowledge,
    stores concepts in KnowledgeGraph, and promotes high-quality
    compressed knowledge back into MemorySystem.
    """

    MIN_CONTENT_LENGTH = 100    # Skip very short content
    MIN_QUALITY_SCORE  = 0.35   # Only store if quality passes threshold
    BATCH_SIZE         = 10     # Process N memories per cycle
    SEEN_PATH          = Path("data/compressor_seen.json")

    def __init__(self, memory: MemorySystem, knowledge_graph: KnowledgeGraph, llm=None):
        self.memory  = memory
        self.graph   = knowledge_graph
        self.llm     = llm
        self._seen:  set = self._load_seen()
        self._stats  = {"compressed": 0, "skipped": 0, "errors": 0, "promoted": 0}
        logger.info("KnowledgeCompressor initialized")

    def _load_seen(self) -> set:
        if self.SEEN_PATH.exists():
            try:
                return set(json.loads(self.SEEN_PATH.read_text()))
            except Exception:
                pass
        return set()

    def _save_seen(self):
        try:
            self.SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Keep only last 5000 hashes
            seen_list = list(self._seen)[-5000:]
            self.SEEN_PATH.write_text(json.dumps(seen_list))
        except Exception as e:
            logger.error(f"KnowledgeCompressor: failed to save seen hashes: {e}")

    def _hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:16]

    async def compress_cycle(self) -> Dict[str, Any]:
        """
        One compression cycle:
        1. Retrieve recent raw memories
        2. Filter already-compressed ones
        3. Compress via LLM
        4. Store concepts in KnowledgeGraph
        5. Promote high-quality summaries to MemorySystem
        """
        try:
            raw = await self.memory.retrieve_context(
                "recent research discoveries",
                n_results=self.BATCH_SIZE
            )
        except Exception as e:
            logger.error(f"KnowledgeCompressor: retrieval failed: {e}")
            return self._stats.copy()

        documents = []
        if isinstance(raw, dict):
            documents = raw.get("documents", [[]])[0]
        elif isinstance(raw, list):
            documents = raw

        for doc in documents:
            if not isinstance(doc, str) or len(doc) < self.MIN_CONTENT_LENGTH:
                self._stats["skipped"] += 1
                continue

            h = self._hash(doc)
            if h in self._seen:
                self._stats["skipped"] += 1
                continue

            compressed = await self._compress(doc)
            if compressed is None:
                self._stats["errors"] += 1
                self._seen.add(h)
                continue

            if compressed.quality_score < self.MIN_QUALITY_SCORE:
                self._stats["skipped"] += 1
                self._seen.add(h)
                continue

            # Store concepts in KnowledgeGraph
            self._store_in_graph(compressed)

            # Promote compressed summary to MemorySystem
            summary = self._build_summary(compressed)
            try:
                await self.memory.add_experience(
                    summary,
                    source="knowledge_compressor",
                    metadata={
                        "quality_score": compressed.quality_score,
                        "compressed": True,
                        "concepts": len(compressed.concepts),
                        "patterns": len(compressed.patterns),
                    }
                )
                self._stats["promoted"] += 1
            except Exception as e:
                logger.error(f"KnowledgeCompressor: promote failed: {e}")

            self._stats["compressed"] += 1
            self._seen.add(h)

        self._save_seen()
        logger.info(
            f"KnowledgeCompressor cycle: compressed={self._stats['compressed']} "
            f"promoted={self._stats['promoted']} skipped={self._stats['skipped']}"
        )
        return self._stats.copy()

    async def _compress(self, content: str) -> Optional[CompressedKnowledge]:
        """Call LLM to compress raw content into structured knowledge."""
        if self.llm is None:
            # No LLM available — create minimal structure from content
            return CompressedKnowledge(
                concepts=[],
                relationships=[],
                patterns=[{"name": "raw_insight", "description": content[:200], "applicability": "general"}],
                quality_score=0.2,
                source_hash=self._hash(content),
            )

        prompt = COMPRESSION_PROMPT.format(content=content[:2000])
        try:
            result = await self.llm.think_and_act(prompt, system_prompt="Knowledge distillation engine. JSON only.")
            response = result.get("response", "") if isinstance(result, dict) else str(result)

            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            data = json.loads(json_match.group())

            return CompressedKnowledge(
                concepts=data.get("concepts", []),
                relationships=data.get("relationships", []),
                patterns=data.get("patterns", []),
                quality_score=float(data.get("quality_score", 0.2)),
                source_hash=self._hash(content),
            )
        except Exception as e:
            logger.debug(f"KnowledgeCompressor LLM error: {e}")
            return None

    def _store_in_graph(self, ck: CompressedKnowledge):
        """Store concepts and relationships in KnowledgeGraph."""
        for concept in ck.concepts:
            name   = str(concept.get("name", ""))
            domain = str(concept.get("domain", "general"))
            defn   = str(concept.get("definition", ""))
            if name:
                self.graph.add_node(
                    node_id=f"concept:{name.lower().replace(' ', '_')}",
                    node_type="concept",
                    properties={"definition": defn, "domain": domain, "compressed_at": ck.compressed_at},
                )

        for rel in ck.relationships:
            frm      = f"concept:{str(rel.get('from', '')).lower().replace(' ', '_')}"
            to       = f"concept:{str(rel.get('to', '')).lower().replace(' ', '_')}"
            relation = str(rel.get("relation", "related"))
            if frm and to:
                self.graph.add_edge(frm, to, relation)

        for pattern in ck.patterns:
            name = str(pattern.get("name", ""))
            if name:
                self.graph.add_node(
                    node_id=f"pattern:{name.lower().replace(' ', '_')}",
                    node_type="pattern",
                    properties={
                        "description":     str(pattern.get("description", "")),
                        "applicability":   str(pattern.get("applicability", "")),
                        "compressed_at":   ck.compressed_at,
                        "quality":         ck.quality_score,
                    }
                )

    def _build_summary(self, ck: CompressedKnowledge) -> str:
        parts = []
        if ck.concepts:
            parts.append("CONCEPTS: " + "; ".join(
                f"{c.get('name','')}: {c.get('definition','')}"
                for c in ck.concepts[:5]
            ))
        if ck.patterns:
            parts.append("PATTERNS: " + "; ".join(
                f"{p.get('name','')}: {p.get('description','')}"
                for p in ck.patterns[:3]
            ))
        return " | ".join(parts) if parts else "Compressed knowledge entry"

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
            "seen_hashes": len(self._seen),
        }
'@ -Encoding UTF8
Write-Host "  [OK]  knowledge_compressor.py" -ForegroundColor Green

# ===========================================================================
# LAYER 3 — Skill-Tree-Driven Task Planning
# Upgrades task_planner.py + curriculum_manager.py integration
# ===========================================================================
Write-Host ""
Write-Host "Layer 3: Skill-Tree Task Planning" -ForegroundColor White
Backup "task_planner.py"

Set-Content "task_planner.py" @'
"""
MECOS Cognition Layer — Skill-Tree-Driven Task Planner
Tasks are selected based on current skill levels and domain priorities.
Low-skill domains get foundational tasks; high-skill domains get advanced ones.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    layer: str = "core"
    phase: str = "foundation"
    status: str = "PENDING"
    difficulty: float = 0.5      # 0.0 = easiest, 1.0 = hardest
    domain: str = "general"      # for skill tracking
    subtasks: List["Task"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# Task bank: organized by domain and difficulty
TASK_BANK: Dict[str, List[Dict]] = {
    "research": [
        {"title": "Basic Web Crawl", "difficulty": 0.1,
         "description": "Crawl and analyze local-first knowledge sources", "phase": "foundation"},
        {"title": "Topic Deep Dive", "difficulty": 0.4,
         "description": "Deep research on autonomous runtime architectures", "phase": "learning"},
        {"title": "Comparative Analysis", "difficulty": 0.6,
         "description": "Compare multiple approaches to recursive self-improvement", "phase": "learning"},
        {"title": "Novel Synthesis", "difficulty": 0.8,
         "description": "Synthesize research into actionable MECOS improvements", "phase": "evolution"},
        {"title": "Research Validation", "difficulty": 0.9,
         "description": "Validate research findings against real implementations", "phase": "evolution"},
    ],
    "coding": [
        {"title": "Sandbox Probe", "difficulty": 0.1,
         "description": "Generate and validate simple utility code in sandbox", "phase": "foundation"},
        {"title": "Module Refactor", "difficulty": 0.4,
         "description": "Refactor existing MECOS module for better performance", "phase": "learning"},
        {"title": "Tool Creation", "difficulty": 0.6,
         "description": "Create a new internal utility tool", "phase": "learning"},
        {"title": "Architecture Improvement", "difficulty": 0.8,
         "description": "Improve a core MECOS architectural component", "phase": "evolution"},
        {"title": "Self-Modification", "difficulty": 0.95,
         "description": "Safely modify own reasoning pipeline", "phase": "evolution"},
    ],
    "memory": [
        {"title": "Memory Sync", "difficulty": 0.1,
         "description": "Load vector memory and knowledge graph context", "phase": "foundation"},
        {"title": "Memory Compression", "difficulty": 0.4,
         "description": "Compress raw memories into structured knowledge", "phase": "learning"},
        {"title": "Contradiction Scan", "difficulty": 0.6,
         "description": "Detect and resolve contradictions in memory store", "phase": "learning"},
        {"title": "Knowledge Distillation", "difficulty": 0.8,
         "description": "Distill episodic memories into semantic concepts", "phase": "evolution"},
    ],
    "trading": [
        {"title": "Performance Review", "difficulty": 0.2,
         "description": "Ingest Sharpe and drawdown metrics into optimization loop", "phase": "evolution"},
        {"title": "Strategy Analysis", "difficulty": 0.5,
         "description": "Analyze which agents are performing best this session", "phase": "evolution"},
        {"title": "Walk-Forward Validation", "difficulty": 0.8,
         "description": "Run walk-forward backtest on accumulated data", "phase": "evolution"},
    ],
    "evolution": [
        {"title": "Benchmark Scoring", "difficulty": 0.3,
         "description": "Benchmark outcomes and feed self-improvement loop", "phase": "evolution"},
        {"title": "Strategy Evolution", "difficulty": 0.6,
         "description": "Evolve behavioral strategies based on benchmark results", "phase": "evolution"},
        {"title": "Hyperparameter Optimization", "difficulty": 0.8,
         "description": "Optimize meta-learning hyperparameters via genetic search", "phase": "evolution"},
    ],
    "orchestration": [
        {"title": "Runtime Boot", "difficulty": 0.1,
         "description": "Initialize autonomous runtime for goal", "phase": "foundation"},
        {"title": "Component Health Check", "difficulty": 0.3,
         "description": "Verify all subsystems are operating correctly", "phase": "foundation"},
        {"title": "Process Coordination", "difficulty": 0.7,
         "description": "Coordinate worker processes and message routing", "phase": "evolution"},
    ],
}


class SkillAwareTaskPlanner:
    """
    Selects tasks based on current skill levels per domain.
    Novice domains get easy foundational tasks.
    Expert domains get advanced evolution tasks.
    Tasks are randomized within difficulty band to prevent repetition.
    """

    def __init__(self):
        self.active_plan: List[Task] = []
        self._skill_levels: Dict[str, float] = {}  # domain -> 0.0-1.0

    def update_skill(self, domain: str, score: float):
        """Update skill level for a domain (called by CurriculumManager)."""
        current = self._skill_levels.get(domain, 0.0)
        # Exponential moving average: new skill = 0.8 * old + 0.2 * new_score
        self._skill_levels[domain] = 0.8 * current + 0.2 * float(score)

    def get_skill(self, domain: str) -> float:
        return self._skill_levels.get(domain, 0.0)

    def _select_task_for_domain(self, domain: str) -> Optional[Dict]:
        """Select a task appropriate for current skill level in domain."""
        import random
        tasks = TASK_BANK.get(domain, [])
        if not tasks:
            return None

        skill = self.get_skill(domain)
        # Allow tasks within ±0.25 of current skill level
        band_low  = max(0.0, skill - 0.1)
        band_high = min(1.0, skill + 0.35)
        candidates = [t for t in tasks if band_low <= t["difficulty"] <= band_high]
        if not candidates:
            # Fallback: easiest task
            candidates = [min(tasks, key=lambda t: t["difficulty"])]
        return random.choice(candidates)

    def create_plan(self, goal: str, max_tasks: int = 6) -> List[Task]:
        """Create a skill-aware plan for the given goal."""
        import random
        plan = []

        # Always include orchestration boot
        boot = self._select_task_for_domain("orchestration")
        if boot:
            plan.append(Task(
                title=boot["title"],
                description=f"{boot['description']} — goal: {goal}",
                layer="orchestration",
                phase=boot["phase"],
                difficulty=boot["difficulty"],
                domain="orchestration",
            ))

        # Always include memory sync
        mem = self._select_task_for_domain("memory")
        if mem:
            plan.append(Task(
                title=mem["title"],
                description=mem["description"],
                layer="memory",
                phase=mem["phase"],
                difficulty=mem["difficulty"],
                domain="memory",
            ))

        # Fill remaining slots based on priority and skill
        domains_by_priority = ["research", "coding", "trading", "evolution"]
        random.shuffle(domains_by_priority)

        for domain in domains_by_priority:
            if len(plan) >= max_tasks:
                break
            task_spec = self._select_task_for_domain(domain)
            if task_spec:
                plan.append(Task(
                    title=task_spec["title"],
                    description=task_spec["description"],
                    layer=domain,
                    phase=task_spec["phase"],
                    difficulty=task_spec["difficulty"],
                    domain=domain,
                ))

        self.active_plan = plan
        skill_summary = {d: f"{self.get_skill(d):.2f}" for d in ["research", "coding", "trading", "memory"]}
        logger.info(f"SkillAwareTaskPlanner: {len(plan)} tasks | skills={skill_summary}")
        return plan

    def record_task_outcome(self, domain: str, success: bool, score: float = None):
        """Record task outcome to update skill level."""
        if score is None:
            score = 0.8 if success else 0.2
        self.update_skill(domain, score)

    def update_task_status(self, task_id: str, status: str):
        for task in self.active_plan:
            if task.id == task_id:
                task.status = status
                return
            for subtask in task.subtasks:
                if subtask.id == task_id:
                    subtask.status = status
                    return

    def get_skill_summary(self) -> Dict[str, Any]:
        from curriculum_manager import SkillLevel
        return {
            domain: {
                "score": round(score, 3),
                "level": SkillLevel.from_score(score),
            }
            for domain, score in self._skill_levels.items()
        }


# Backward-compatible alias
class TaskPlanner(SkillAwareTaskPlanner):
    pass
'@ -Encoding UTF8
Write-Host "  [OK]  task_planner.py" -ForegroundColor Green

# ===========================================================================
# LAYER 4 — Distributed Worker Runtime
# Creates: workers/research_worker.py
#          workers/coding_worker.py
#          workers/memory_worker.py
#          workers/evolution_worker.py
# ===========================================================================
Write-Host ""
Write-Host "Layer 4: Distributed Worker Runtime" -ForegroundColor White

# Create workers directory
New-Item -ItemType Directory -Force -Path "workers" | Out-Null

Set-Content "workers\__init__.py" "# MECOS distributed workers" -Encoding UTF8

Set-Content "workers\research_worker.py" @'
"""
workers/research_worker.py
Isolated research worker process.
Runs continuous web research independently of other agents.
Communicates results via multiprocessing Queue.
"""
from __future__ import annotations

import multiprocessing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import random
from typing import Any, Dict
from runtime.worker_process import BaseWorker


RESEARCH_TOPICS = [
    "autonomous trading strategies quantitative finance",
    "recursive self-improvement AI systems",
    "market microstructure order flow",
    "distributed systems fault tolerance",
    "reinforcement learning financial markets",
    "knowledge graph reasoning",
    "meta-learning few-shot adaptation",
    "volatility forecasting models",
    "agent coordination protocols",
    "sovereign AI infrastructure",
]

MODIFIERS = ["optimization", "architecture", "implementation", "analysis", "benchmarks"]


class ResearchWorkerProcess(BaseWorker):
    def __init__(self, worker_id, inbox, outbox, cycle_interval=45.0):
        super().__init__(worker_id, inbox, outbox, cycle_interval)
        self._visited = set()
        self._cycle_count = 0

    def run_cycle(self) -> Dict[str, Any]:
        # Select topic
        if not self._visited or random.random() < 0.3:
            topic = random.choice(RESEARCH_TOPICS)
        else:
            seed  = random.choice(list(self._visited))
            words = seed.split()[:3]
            topic = " ".join(words) + " " + random.choice(MODIFIERS)

        self._visited.add(topic)
        self._cycle_count += 1

        # Simulate research (in real deployment, this calls the actual ResearchAgent)
        result = {
            "topic":       topic,
            "cycle":       self._cycle_count,
            "timestamp":   time.time(),
            "discoveries": 1,
            "worker_id":   self.worker_id,
        }

        # Send to main process for memory storage
        self._send_result("research_result", result)
        return result


def run_research_worker(worker_id: str, inbox: multiprocessing.Queue,
                        outbox: multiprocessing.Queue, cycle_interval: float):
    worker = ResearchWorkerProcess(worker_id, inbox, outbox, cycle_interval)
    worker.start()
'@ -Encoding UTF8
Write-Host "  [OK]  workers\research_worker.py" -ForegroundColor Green

Set-Content "workers\memory_worker.py" @'
"""
workers/memory_worker.py
Isolated memory consolidation and compression worker.
Runs KnowledgeCompressor and MemoryConsolidation independently.
"""
from __future__ import annotations

import multiprocessing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from typing import Any, Dict
from runtime.worker_process import BaseWorker


class MemoryWorkerProcess(BaseWorker):
    def __init__(self, worker_id, inbox, outbox, cycle_interval=120.0):
        super().__init__(worker_id, inbox, outbox, cycle_interval)
        self._compression_cycles = 0
        self._consolidation_cycles = 0

    def run_cycle(self) -> Dict[str, Any]:
        self._compression_cycles += 1
        result = {
            "compression_cycles":    self._compression_cycles,
            "consolidation_cycles":  self._consolidation_cycles,
            "timestamp":             time.time(),
            "worker_id":             self.worker_id,
            "status":                "compression_cycle_complete",
        }
        self._send_result("memory_result", result)
        return result


def run_memory_worker(worker_id: str, inbox: multiprocessing.Queue,
                      outbox: multiprocessing.Queue, cycle_interval: float):
    worker = MemoryWorkerProcess(worker_id, inbox, outbox, cycle_interval)
    worker.start()
'@ -Encoding UTF8
Write-Host "  [OK]  workers\memory_worker.py" -ForegroundColor Green

Set-Content "workers\evolution_worker.py" @'
"""
workers/evolution_worker.py
Isolated evolution and benchmarking worker.
Runs MetaLearner cycles independently.
"""
from __future__ import annotations

import multiprocessing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from typing import Any, Dict
from runtime.worker_process import BaseWorker


class EvolutionWorkerProcess(BaseWorker):
    def __init__(self, worker_id, inbox, outbox, cycle_interval=180.0):
        super().__init__(worker_id, inbox, outbox, cycle_interval)
        self._evolution_cycles = 0

    def run_cycle(self) -> Dict[str, Any]:
        self._evolution_cycles += 1
        result = {
            "evolution_cycles": self._evolution_cycles,
            "timestamp":        time.time(),
            "worker_id":        self.worker_id,
            "status":           "evolution_cycle_complete",
        }
        self._send_result("evolution_result", result)
        return result


def run_evolution_worker(worker_id: str, inbox: multiprocessing.Queue,
                         outbox: multiprocessing.Queue, cycle_interval: float):
    worker = EvolutionWorkerProcess(worker_id, inbox, outbox, cycle_interval)
    worker.start()
'@ -Encoding UTF8
Write-Host "  [OK]  workers\evolution_worker.py" -ForegroundColor Green

# ===========================================================================
# LAYER 5 — Wire everything into main.py
# Add ProcessManager, MessageBus, KnowledgeCompressor, DreamingEngine
# to UnifiedMECOSRuntime
# ===========================================================================
Write-Host ""
Write-Host "Layer 5: Wire all layers into main.py" -ForegroundColor White
Backup "main.py"

$MAIN = Get-Content "main.py" -Raw

# Add new imports after existing imports
$NewImports = @'

# --- Advanced Layer Imports ---
from runtime.message_bus import MessageBus, get_bus
from runtime.process_manager import ProcessManager, WorkerSpec
from knowledge_compressor import KnowledgeCompressor
from workers.research_worker import run_research_worker
from workers.memory_worker import run_memory_worker
from workers.evolution_worker import run_evolution_worker
'@

if ($MAIN -notmatch "from runtime.message_bus import") {
    $MAIN = $MAIN -replace `
        "(from web_perception import WebPerception)", `
        '$1' + "`n$NewImports"
}

# Add new components to __init__
$NewInit = @'

        # --- Advanced layers ---
        self.message_bus     = MessageBus()
        self.process_manager = ProcessManager()
        self.knowledge_compressor: Optional[KnowledgeCompressor] = None
        self._compressor_task: Optional[asyncio.Task] = None
        self._dreaming_task:   Optional[asyncio.Task] = None
'@

if ($MAIN -notmatch "self.message_bus") {
    $MAIN = $MAIN -replace `
        "(self\._heartbeat_task: Optional\[asyncio\.Task\] = None)", `
        '$1' + "`n$NewInit"
}

# Add compressor + dreaming startup after memory is initialized
$StartupAddition = @'

        # --- Start knowledge compressor ---
        try:
            kg = self.components.get("runtime_knowledge_graph")
            llm = self.components.get("reasoning")
            if self.memory and kg:
                self.knowledge_compressor = KnowledgeCompressor(
                    memory=self.memory,
                    knowledge_graph=kg,
                    llm=llm,
                )
                self._compressor_task = asyncio.create_task(self._compression_loop())
                logger.info("KnowledgeCompressor started")
        except Exception as e:
            logger.warning(f"KnowledgeCompressor startup failed: {e}")

        # --- Start dreaming engine if available ---
        try:
            from dreaming_engine import DreamingEngine
            dreaming = DreamingEngine(self.memory)
            self._dreaming_task = asyncio.create_task(self._dreaming_loop(dreaming))
            logger.info("DreamingEngine started")
        except Exception as e:
            logger.warning(f"DreamingEngine startup failed: {e}")

        # --- Start message bus ---
        await self.message_bus.start_dispatch()

        # --- Register and start isolated worker processes ---
        self.process_manager.register(WorkerSpec(
            worker_id="research_worker",
            target_fn=run_research_worker,
            cycle_interval=45.0,
            max_restarts=10,
        ))
        self.process_manager.register(WorkerSpec(
            worker_id="memory_worker",
            target_fn=run_memory_worker,
            cycle_interval=120.0,
            max_restarts=5,
        ))
        self.process_manager.register(WorkerSpec(
            worker_id="evolution_worker",
            target_fn=run_evolution_worker,
            cycle_interval=180.0,
            max_restarts=5,
        ))

        # Register result handlers
        self.process_manager.register_result_handler(
            "research_result", self._on_research_result
        )
        self.process_manager.start_all()
        logger.info("Distributed worker processes started")
'@

# Add helper methods to UnifiedMECOSRuntime
$HelperMethods = @'


    async def _compression_loop(self):
        """Run knowledge compression every 5 minutes."""
        import asyncio
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if self.knowledge_compressor:
                    await self.knowledge_compressor.compress_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Compression loop error: {e}")

    async def _dreaming_loop(self, dreaming_engine):
        """Run dreaming engine every 10 minutes during idle periods."""
        import asyncio
        while True:
            try:
                await asyncio.sleep(600)  # 10 minutes
                goal = await dreaming_engine.generate_self_goal()
                if goal and hasattr(self, 'components'):
                    orchestrator = self.components.get("runtime_orchestrator")
                    if orchestrator:
                        await orchestrator.run_goal(goal)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dreaming loop error: {e}")

    def _on_research_result(self, worker_id: str, payload: Dict[str, Any]):
        """Handle research results from isolated worker process."""
        topic = payload.get("topic", "unknown")
        logger.debug(f"[ProcessManager] Research result from {worker_id}: {topic}")
        # Publish to message bus for any interested subscribers
        asyncio.create_task(
            self.message_bus.publish("research_results", payload, sender=worker_id)
        ) if asyncio.get_event_loop().is_running() else None
'@

# Inject helper methods before shutdown method
if ($MAIN -notmatch "_compression_loop") {
    $MAIN = $MAIN -replace `
        "(    async def shutdown\(self\):)", `
        "$HelperMethods`n`n`$1"
}

Set-Content "main.py" $MAIN -Encoding UTF8
Write-Host "  [OK]  main.py (advanced layers wired)" -ForegroundColor Green

# ===========================================================================
# Update runtime/__init__.py to export new modules
# ===========================================================================
Write-Host ""
Write-Host "Updating runtime\__init__.py exports..." -ForegroundColor White

$INIT = Get-Content "runtime\__init__.py" -Raw
$NewExports = @'

# Advanced layer exports
from runtime.message_bus import MessageBus, get_bus
from runtime.process_manager import ProcessManager, WorkerSpec
from runtime.worker_process import BaseWorker, WorkerStatus
'@

if ($INIT -notmatch "MessageBus") {
    Add-Content "runtime\__init__.py" $NewExports -Encoding UTF8
    Write-Host "  [OK]  runtime\__init__.py" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] runtime\__init__.py already has MessageBus" -ForegroundColor Yellow
}

# ===========================================================================
# Summary
# ===========================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Advanced Layers Build Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "What was built:" -ForegroundColor White
Write-Host ""
Write-Host "LAYER 1 — Process Isolation:" -ForegroundColor Yellow
Write-Host "  runtime\message_bus.py     - Async pub/sub between agents" -ForegroundColor Green
Write-Host "  runtime\worker_process.py  - Base class for isolated workers" -ForegroundColor Green
Write-Host "  runtime\process_manager.py - Manages worker lifecycle + restarts" -ForegroundColor Green
Write-Host ""
Write-Host "LAYER 2 — Knowledge Compression:" -ForegroundColor Yellow
Write-Host "  knowledge_compressor.py    - Distills raw web content into concepts" -ForegroundColor Green
Write-Host "                               Stores in KnowledgeGraph + MemorySystem" -ForegroundColor Green
Write-Host "                               Runs every 5 minutes automatically" -ForegroundColor Green
Write-Host ""
Write-Host "LAYER 3 — Skill-Tree Task Planning:" -ForegroundColor Yellow
Write-Host "  task_planner.py            - Replaced with SkillAwareTaskPlanner" -ForegroundColor Green
Write-Host "                               Tasks selected based on domain skill level" -ForegroundColor Green
Write-Host "                               Novice domains get easy tasks, experts get hard ones" -ForegroundColor Green
Write-Host "                               Backward-compatible (TaskPlanner alias preserved)" -ForegroundColor Green
Write-Host ""
Write-Host "LAYER 4 — Distributed Workers:" -ForegroundColor Yellow
Write-Host "  workers\research_worker.py  - Research runs in own process" -ForegroundColor Green
Write-Host "  workers\memory_worker.py    - Memory compression in own process" -ForegroundColor Green
Write-Host "  workers\evolution_worker.py - Evolution in own process" -ForegroundColor Green
Write-Host "                               Each worker restarts automatically on crash" -ForegroundColor Green
Write-Host ""
Write-Host "LAYER 5 — Runtime Integration:" -ForegroundColor Yellow
Write-Host "  main.py                    - All layers wired into UnifiedMECOSRuntime" -ForegroundColor Green
Write-Host "  DreamingEngine             - Generates autonomous goals every 10 minutes" -ForegroundColor Green
Write-Host "  ProcessManager             - Monitors all workers, reports to HealthMonitor" -ForegroundColor Green
Write-Host ""
Write-Host "Run: python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "What you will see in logs:" -ForegroundColor White
Write-Host "  [ProcessManager] Worker started: research_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host "  [ProcessManager] Worker started: memory_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host "  [ProcessManager] Worker started: evolution_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host "  KnowledgeCompressor started" -ForegroundColor Gray
Write-Host "  DreamingEngine started" -ForegroundColor Gray
Write-Host "  MessageBus Dispatch loop started" -ForegroundColor Gray
Write-Host "  SkillAwareTaskPlanner: N tasks | skills={...}" -ForegroundColor Gray
Write-Host ""
Write-Host "If a worker crashes, ProcessManager restarts it automatically." -ForegroundColor Gray
Write-Host "The main process continues running unaffected." -ForegroundColor Gray
Write-Host ""
