"""
integrate_collaboration_v2.py
Run from MECOS root: python integrate_collaboration_v2.py
"""
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Add analytics runner + RL weight updater to collaborative_decision_engine
# ─────────────────────────────────────────────────────────────────────────────

cde = Path("trading/collaborative_decision_engine.py")
src = cde.read_text(encoding="utf-8")

# Add BASE_ANALYTIC_WEIGHTS after BASE_PERSONA_WEIGHTS
old_min = "MIN_DIRECTIONAL_SCORE = 0.18"
if "BASE_ANALYTIC_WEIGHTS" not in src:
    new_min = """MIN_DIRECTIONAL_SCORE = 0.18

# Weights for analytic participants (MTF, regime, optimizer, backtest)
BASE_ANALYTIC_WEIGHTS: Dict[str, float] = {
    "multi_timeframe": 1.10,
    "rule_regime":     0.90,
    "optimizer":       0.75,
    "backtest":        0.65,
}"""
    assert old_min in src, "MIN_DIRECTIONAL_SCORE not found"
    src = src.replace(old_min, new_min)
    print("OK: BASE_ANALYTIC_WEIGHTS added")
else:
    print("· BASE_ANALYTIC_WEIGHTS already present")

# Add analytic: prefix handling to _fuse
old_fuse_prefix = (
    '            elif key.startswith("persona:"):\n'
    '                pname = key[8:]\n'
    '                ptype = "persona"\n'
    '                base_w = BASE_PERSONA_WEIGHTS.get(pname, 0.75)\n'
    '            else:\n'
    '                pname = key\n'
    '                ptype = "unknown"\n'
    '                base_w = 1.0'
)
new_fuse_prefix = (
    '            elif key.startswith("persona:"):\n'
    '                pname = key[8:]\n'
    '                ptype = "persona"\n'
    '                base_w = BASE_PERSONA_WEIGHTS.get(pname, 0.75)\n'
    '            elif key.startswith("analytic:"):\n'
    '                pname = key[9:]\n'
    '                ptype = "analytic"\n'
    '                base_w = BASE_ANALYTIC_WEIGHTS.get(pname, 0.80)\n'
    '            else:\n'
    '                pname = key\n'
    '                ptype = "unknown"\n'
    '                base_w = 1.0'
)
if "analytic:" not in src:
    assert old_fuse_prefix in src, "_fuse prefix block not found"
    src = src.replace(old_fuse_prefix, new_fuse_prefix)
    print("OK: analytic: prefix added to _fuse")
else:
    print("· analytic: prefix already in _fuse")

# Insert _run_analytics and update_rl_weight before _fuse
insertion_marker = "    def _fuse("
new_methods = '''    async def _run_analytics(
        self, context: dict
    ) -> dict:
        """
        Run analytic modules as voting participants instead of post-hoc vetoes.
        MTF, rule regime, optimizer, and backtest each contribute a signal.
        """
        out: dict = {}
        extra = context.get("external_market_context", {}) or {}

        # MultiTimeframe alignment
        try:
            mtf = extra.get("multi_timeframe", {}) or {}
            alignment = float(mtf.get("alignment_score", 0.0) or 0.0)
            composite = str(mtf.get("composite_trend", "mixed"))
            if alignment > 0.40:
                sig, conf = "BUY",  min(0.85, 0.50 + alignment * 0.40)
            elif alignment < -0.40:
                sig, conf = "SELL", min(0.85, 0.50 + abs(alignment) * 0.40)
            else:
                sig, conf = "HOLD", 0.30
            out["multi_timeframe"] = {
                "signal": sig, "confidence": conf,
                "reasoning": f"MTF alignment={alignment:.2f} composite={composite}",
            }
        except Exception as e:
            out["multi_timeframe"] = {"signal": "HOLD", "confidence": 0.1, "error": str(e)}

        # Rule-based regime
        try:
            rrd = extra.get("rule_regime", {}) or {}
            rr  = str(rrd.get("regime", "unknown")).lower()
            if rr in {"bull", "trending"}:
                out["rule_regime"] = {"signal": "BUY",  "confidence": 0.60,
                                      "reasoning": f"Rule regime: {rr}"}
            elif rr in {"bear", "panic"}:
                out["rule_regime"] = {"signal": "SELL", "confidence": 0.65,
                                      "reasoning": f"Rule regime: {rr}"}
            else:
                out["rule_regime"] = {"signal": "HOLD", "confidence": 0.30,
                                      "reasoning": f"Rule regime: {rr}"}
        except Exception as e:
            out["rule_regime"] = {"signal": "HOLD", "confidence": 0.1, "error": str(e)}

        # Portfolio optimizer
        try:
            opt = extra.get("optimizer", {}) or {}
            rec = str(opt.get("recommendation", "HOLD")).upper()
            opt_conf = float(opt.get("confidence", 0.3) or 0.3)
            sig = rec if rec in {"BUY", "SELL"} else "HOLD"
            out["optimizer"] = {"signal": sig, "confidence": min(0.70, opt_conf),
                                "reasoning": f"Optimizer: {rec}"}
        except Exception as e:
            out["optimizer"] = {"signal": "HOLD", "confidence": 0.1, "error": str(e)}

        # Quick backtest expectancy
        try:
            bt = extra.get("quick_backtest", {}) or {}
            bt_ret = float(bt.get("total_return", 0.0) or 0.0)
            if bt_ret > 0.02:
                out["backtest"] = {"signal": "BUY",  "confidence": min(0.65, 0.45 + bt_ret * 2),
                                   "reasoning": f"Backtest return={bt_ret:.2%}"}
            elif bt_ret < -0.02:
                out["backtest"] = {"signal": "SELL", "confidence": min(0.65, 0.45 + abs(bt_ret) * 2),
                                   "reasoning": f"Backtest return={bt_ret:.2%}"}
            else:
                out["backtest"] = {"signal": "HOLD", "confidence": 0.30,
                                   "reasoning": f"Backtest neutral: {bt_ret:.2%}"}
        except Exception as e:
            out["backtest"] = {"signal": "HOLD", "confidence": 0.1, "error": str(e)}

        return out

    def update_rl_weight(self, q_advantage: float) -> None:
        """
        Dynamically adjust the RL agent's fusion weight based on Q-advantage.
        Called after each trade outcome is recorded.
        """
        import numpy as np
        current = BASE_AGENT_WEIGHTS.get("reinforcement_learning", 0.50)
        delta = float(np.clip(q_advantage * 0.05, -0.10, 0.10))
        BASE_AGENT_WEIGHTS["reinforcement_learning"] = float(
            np.clip(current + delta, 0.30, 1.20)
        )

    def _fuse('''

if "_run_analytics" not in src:
    assert insertion_marker in src, "_fuse( not found"
    src = src.replace(insertion_marker, new_methods)
    print("OK: _run_analytics and update_rl_weight added")
else:
    print("· _run_analytics already present")

# Wire analytics into decide() - update the gather call
old_gather = (
    "        # Run quant agents and personas concurrently\n"
    "        agent_task   = asyncio.create_task(\n"
    "            self._run_all_agents(data, features, physics, symbol)\n"
    "        )\n"
    "        persona_task = asyncio.create_task(\n"
    "            self._run_all_personas(shared_context)\n"
    "        )\n"
    "\n"
    "        agent_signals, persona_signals = await asyncio.gather(\n"
    "            agent_task, persona_task, return_exceptions=False\n"
    "        )"
)
new_gather = (
    "        # Run quant agents, personas, and analytics concurrently\n"
    "        agent_task    = asyncio.create_task(\n"
    "            self._run_all_agents(data, features, physics, symbol)\n"
    "        )\n"
    "        persona_task  = asyncio.create_task(\n"
    "            self._run_all_personas(shared_context)\n"
    "        )\n"
    "        analytic_task = asyncio.create_task(\n"
    "            self._run_analytics(shared_context)\n"
    "        )\n"
    "\n"
    "        agent_signals, persona_signals, analytic_signals = await asyncio.gather(\n"
    "            agent_task, persona_task, analytic_task, return_exceptions=False\n"
    "        )"
)
if "analytic_task" not in src:
    assert old_gather in src, "gather block not found"
    src = src.replace(old_gather, new_gather)
    print("OK: analytics wired into decide() gather")
else:
    print("· analytics already in gather")

# Update pool block
old_pool = (
    "        # Pool all signals together\n"
    "        all_signals: Dict[str, Dict[str, Any]] = {\n"
    "            **{f\"agent:{k}\": v for k, v in agent_signals.items()},\n"
    "            **{f\"persona:{k}\": v for k, v in persona_signals.items()},\n"
    "        }"
)
new_pool = (
    "        # Pool all signals together\n"
    "        all_signals: Dict[str, Dict[str, Any]] = {\n"
    "            **{f\"agent:{k}\": v for k, v in agent_signals.items()},\n"
    "            **{f\"persona:{k}\": v for k, v in persona_signals.items()},\n"
    "            **{f\"analytic:{k}\": v for k, v in analytic_signals.items()},\n"
    "        }"
)
if '"analytic:{k}"' not in src:
    assert old_pool in src, "pool block not found"
    src = src.replace(old_pool, new_pool)
    print("OK: pool updated with analytics")
else:
    print("· pool already includes analytics")

# Update result dict
old_result = (
    '        result["symbol"]         = symbol\n'
    '        result["regime"]         = regime\n'
    '        result["agent_signals"]  = agent_signals\n'
    '        result["persona_signals"] = persona_signals\n'
    '        result["all_signals"]    = all_signals'
)
new_result = (
    '        result["symbol"]           = symbol\n'
    '        result["regime"]           = regime\n'
    '        result["agent_signals"]    = agent_signals\n'
    '        result["persona_signals"]  = persona_signals\n'
    '        result["analytic_signals"] = analytic_signals\n'
    '        result["all_signals"]      = all_signals'
)
if '"analytic_signals"' not in src:
    assert old_result in src, "result dict not found"
    src = src.replace(old_result, new_result)
    print("OK: result dict updated")
else:
    print("· result dict already updated")

cde.write_text(src, encoding="utf-8")
print("collaborative_decision_engine.py saved")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Wire RL Q-advantage → collab weight in autonomous_trading_loop
# ─────────────────────────────────────────────────────────────────────────────

atl = Path("trading/autonomous_trading_loop.py")
src2 = atl.read_text(encoding="utf-8")

old_rl = (
    "            await self.rl_trainer.train_from_replay(batch_size=32)\n"
    "            logger.info("
)
new_rl = (
    "            await self.rl_trainer.train_from_replay(batch_size=32)\n"
    "            try:\n"
    "                ta = getattr(self.paper_executor, 'trading_agent', None)\n"
    "                ce = getattr(ta, 'collab_engine', None) if ta else None\n"
    "                if ce and hasattr(self.rl_trainer, 'q_values'):\n"
    "                    qvals = self.rl_trainer.q_values(\n"
    "                        context['state'], ['BUY', 'SELL', 'HOLD']\n"
    "                    )\n"
    "                    q_taken  = float(qvals.get(context['action'], 0.0))\n"
    "                    others   = [v for k, v in qvals.items() if k != context['action']]\n"
    "                    q_adv    = q_taken - (sum(others) / len(others)) if others else 0.0\n"
    "                    ce.update_rl_weight(q_adv)\n"
    "            except Exception:\n"
    "                pass\n"
    "            logger.info("
)

if "ce.update_rl_weight" not in src2:
    count = src2.count(old_rl)
    if count == 1:
        src2 = src2.replace(old_rl, new_rl)
        print("OK: RL dynamic weight wiring added")
    else:
        print(f"WARNING: RL block found {count}x — skipping")
else:
    print("· RL weight wiring already present")

atl.write_text(src2, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Risk gates → soft confidence penalties in trading_agent.py
# ─────────────────────────────────────────────────────────────────────────────

ta = Path("trading/trading_agent.py")
src3 = ta.read_text(encoding="utf-8")

old_gates = (
    "        if risk_gate_reason:\n"
    "            logger.info(f'Risk gate forced HOLD for {symbol}: {risk_gate_reason}')\n"
    "            final_decision = \"HOLD\""
)
new_gates = (
    "        if risk_gate_reason:\n"
    "            if confidence < 0.45:\n"
    "                logger.info(f'Risk gate HOLD for {symbol}: {risk_gate_reason} '\n"
    "                            f'(conf={confidence:.3f} < 0.45)')\n"
    "                final_decision = \"HOLD\"\n"
    "            else:\n"
    "                logger.info(f'Risk gate PENALTY for {symbol}: {risk_gate_reason} '\n"
    "                            f'(conf={confidence:.3f} >= 0.45 — 20% haircut)')\n"
    "                confidence = confidence * 0.80"
)

if "Risk gate PENALTY" not in src3:
    count = src3.count(old_gates)
    if count == 1:
        src3 = src3.replace(old_gates, new_gates)
        ta.write_text(src3, encoding="utf-8")
        print("OK: risk gates → soft penalties")
    else:
        print(f"WARNING: risk gate block found {count}x — skipping")
else:
    print("· risk gates already softened")

print("\nAll done. Verify:")
print("  python -c \"from trading.collaborative_decision_engine import CollaborativeDecisionEngine; print('OK')\"")
print("  python -c \"from trading.trading_agent import TradingAgent; print('OK')\"")
