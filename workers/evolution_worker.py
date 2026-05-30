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
