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
