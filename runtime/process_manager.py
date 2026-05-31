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
import sys
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

    HEARTBEAT_TIMEOUT = 300.0  # Must exceed longest worker cycle (evolution=180s)  # seconds before declaring worker dead

    def __init__(self):
        # Use a single explicit spawn context on Windows/Python 3.14 to avoid
        # mixed-context handle duplication failures in child bootstrap.
        self._mp_ctx = multiprocessing.get_context("spawn")
        multiprocessing.set_executable(sys.executable)
        self._workers: Dict[str, WorkerState] = {}
        self._running = False
        self._stopping = False
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
        self._stopping = False
        self._running = True
        for wid, state in self._workers.items():
            self._start_worker(state)
        logger.info(f"[ProcessManager] Started {len(self._workers)} workers")

    def _start_worker(self, state: WorkerState):
        inbox  = self._mp_ctx.Queue(maxsize=100)
        outbox = self._mp_ctx.Queue(maxsize=500)
        proc   = self._mp_ctx.Process(
            target=state.spec.target_fn,
            args=(state.spec.worker_id, inbox, outbox, state.spec.cycle_interval),
            daemon=False,
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
        if self._stopping or not self._running:
            return
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
            self._close_state_queues(state)
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
        self._stopping = True
        for wid, state in self._workers.items():
            self.send_command(wid, "stop", None)
        time.sleep(2)
        for wid, state in self._workers.items():
            if state.process and state.process.is_alive():
                state.process.terminate()
                state.process.join(timeout=5)
            if state.process:
                try:
                    state.process.close()
                except Exception:
                    pass
                state.process = None
            self._close_state_queues(state)
        logger.info("[ProcessManager] All workers stopped")

    @staticmethod
    def _close_state_queues(state: WorkerState):
        for queue_name in ("inbox", "outbox"):
            queue_obj = getattr(state, queue_name, None)
            if queue_obj is None:
                continue
            try:
                queue_obj.close()
            except Exception:
                pass
            try:
                queue_obj.join_thread()
            except Exception:
                pass
            setattr(state, queue_name, None)

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

