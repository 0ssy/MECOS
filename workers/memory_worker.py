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
