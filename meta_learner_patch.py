"""
meta_learner_patch.py
=====================
This file shows the TWO blocks to add to meta_learner.py.
Search for the markers below and insert the code.
Nothing existing is removed.
"""

# ===========================================================================
# PATCH A — Add to MetaLearner.__init__()
# After the line:  self.benchmarking = BenchmarkingEngine(...)
# ===========================================================================

PATCH_A = """
        # --- Validity Pipeline ---
        from runtime.validity_filter import build_validity_pipeline
        from runtime.drift_guard import DriftGuard
        self.validity_filter, self.score_store = build_validity_pipeline(
            audit_rate=0.10,
            baseline_path="data/trusted_memory_anchors.json",
        )
        self.drift_guard = DriftGuard(
            baseline_path="data/trusted_memory_anchors.json",
        )
"""

# ===========================================================================
# PATCH B — Add to run_meta_cycle()
# AFTER:  benchmark_results = await self.benchmarking.run_benchmarks()
# BEFORE: await self.strategy_evolution.evolve(benchmark_results)
# ===========================================================================

PATCH_B = """
        # --- Validity Filter ---
        from runtime.validity_filter import ScoredOutput
        import time as _time
        scored_outputs = [
            ScoredOutput(
                subsystem=subsystem,
                task_id=f"{subsystem}_cycle_{int(_time.time())}",
                output=result.get("output", ""),
                raw_score=result.get("score", 0.0),
                metadata=result,
            )
            for subsystem, result in benchmark_results.items()
            if isinstance(result, dict)
        ]
        validation_results = self.validity_filter.filter(scored_outputs)
        trusted = {r.subsystem: r.validated_score for r in validation_results if r.passed}

        if not trusted:
            logger.warning("ValidityFilter: no scores passed this cycle. Skipping evolution.")
            return benchmark_results

        # --- Drift Guard ---
        drift_events = self.drift_guard.check(trusted)
        if any(e.direction == "REGRESSION" for e in drift_events):
            logger.warning(f"DriftGuard: {len(drift_events)} regression(s). Creating rollback anchor.")
            self.drift_guard.create_rollback_checkpoint(
                checkpoint_manager=getattr(self, "checkpoint_manager", None)
            )

        benchmark_results = trusted
        # --- end validity + drift block ---
"""

if __name__ == "__main__":
    print("Apply PATCH_A inside MetaLearner.__init__() after self.benchmarking = ...")
    print("Apply PATCH_B inside run_meta_cycle() after benchmark_results = await ...")
    print()
    print("PATCH_A:")
    print(PATCH_A)
    print("PATCH_B:")
    print(PATCH_B)
