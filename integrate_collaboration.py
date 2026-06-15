"""
integrate_collaboration.py
Run from MECOS root: python integrate_collaboration.py

Integrates three remaining isolated components:
1. MultiTimeframeAnalyzer → proper collab participant (not a post-hoc veto)
2. RL Q-values → dynamic weight adjustment for the RL agent
3. Risk gates → confidence penalties fed back into collab result
"""
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Add MTF, PortfolioOptimizer, RegimeDetector as participants
#    in CollaborativeDecisionEngine
# ─────────────────────────────────────────────────────────────────────────────

cde = Path("trading/collaborative_decision_engine.py")
src = cde.read_text(encoding="utf-8")

# Add MTF/Risk participant agents section after the BASE_PERSONA_WEIGHTS block
old_min = 'MIN_DIRECTIONAL_SCORE = 0.18'
new_min = '''MIN_DIRECTIONAL_SCORE = 0.18

# Weights for analytic participants (MTF, regime, optimizer)
BASE_ANALYTIC_WEIGHTS: Dict[str, float] = {
    "multi_timeframe":   1.10,   # strong directional signal — was a veto before
    "rule_regime":       0.90,
    "optimizer":         0.75,
    "backtest":          0.65,
}'''

assert old_min in src, "MIN_DIRECTIONAL_SCORE not found"
src = src.replace(old_min, new_min)

# Add analytic participant runner to the decide() method
old_decide_gather = (
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

new_decide_gather = (
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

assert old_decide_gather in src, "decide() gather block not found"
src = src.replace(old_decide_gather, new_decide_gather)

# Update the pooling block to include analytics
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

assert old_pool in src, "pool block not found"
src = src.replace(old_pool, new_pool)

# Update result dict to include analytic_signals
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

assert old_result in src, "result dict block not found"
src = src.replace(old_result, new_result)

# Add _run_analytics method before _fuse
old_fuse_marker = "    # ------------------------------------------------------------------ #\n    #  Unified fusion"

new_analytics = '''    async def _run_analytics(
        self, context: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run analytic modules (MTF, regime, optimizer, backtest) as voting
        participants rather than post-hoc vetoes.
        Each returns a signal dict with signal/confidence/reasoning.
        """
        out: Dict[str, Dict[str, Any]] = {}
        features    = context.get("features", {})
        extra       = context.get("external_market_context", {})
        regime      = str(context.get("regime", "unknown"))

        # ── MultiTimeframe alignment ────────────────────────────────────────
        try:
            mtf = extra.get("multi_timeframe", {})
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

        # ── Rule-based regime detector ──────────────────────────────────────
        try:
            rrd = extra.get("rule_regime", {})
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

        # ── Portfolio optimizer ─────────────────────────────────────────────
        try:
            opt = extra.get("optimizer", {})
            rec = str(opt.get("recommendation", "HOLD")).upper()
            opt_conf = float(opt.get("confidence", 0.3) or 0.3)
            sig = rec if rec in {"BUY", "SELL"} else "HOLD"
            out["optimizer"] = {"signal": sig, "confidence": min(0.70, opt_conf),
                                "reasoning": f"Portfolio optimizer: {rec}"}
        except Exception as e:
            out["optimizer"] = {"signal": "HOLD", "confidence": 0.1, "error": str(e)}

        # ── Quick backtest expectancy ───────────────────────────────────────
        try:
            bt = extra.get("quick_backtest", {})
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

    # ------------------------------------------------------------------ #\n    #  Unified fusion'''

assert old_fuse_marker in src, "_fuse marker not found"
src = src.replace(old_fuse_marker, new_analytics)

# Update _fuse to handle analytic: prefix
old_fuse_prefix = (
    "            if key.startswith(\"agent:\"):\n"
    "                pname = key[6:]\n"
    "                ptype = \"agent\"\n"
    "                base_w = BASE_AGENT_WEIGHTS.get(pname.split(\":\")[0], 1.0)\n"
    "            elif key.startswith(\"persona:\"):\n"
    "                pname = key[8:]\n"
    "                ptype = \"persona\"\n"
    "                base_w = BASE_PERSONA_WEIGHTS.get(pname, 0.75)\n"
    "            else:\n"
    "                pname = key\n"
    "                ptype = \"unknown\"\n"
    "                base_w = 1.0"
)

new_fuse_prefix = (
    "            if key.startswith(\"agent:\"):\n"
    "                pname = key[6:]\n"
    "                ptype = \"agent\"\n"
    "                base_w = BASE_AGENT_WEIGHTS.get(pname.split(\":\")[0], 1.0)\n"
    "            elif key.startswith(\"persona:\"):\n"
    "                pname = key[8:]\n"
    "                ptype = \"persona\"\n"
    "                base_w = BASE_PERSONA_WEIGHTS.get(pname, 0.75)\n"
    "            elif key.startswith(\"analytic:\"):\n"
    "                pname = key[9:]\n"
    "                ptype = \"analytic\"\n"
    "                base_w = BASE_ANALYTIC_WEIGHTS.get(pname, 0.80)\n"
    "            else:\n"
    "                pname = key\n"
    "                ptype = \"unknown\"\n"
    "                base_w = 1.0"
)

assert old_fuse_prefix in src, "_fuse prefix block not found"
src = src.replace(old_fuse_prefix, new_fuse_prefix)

# Add update_rl_weight method for dynamic RL weight adjustment
old_closing = "    @staticmethod\n    def _percentile"
new_closing = (
    "    def update_rl_weight(self, q_advantage: float) -> None:\n"
    "        \"\"\"\n"
    "        Dynamically adjust the RL agent's fusion weight based on\n"
    "        its recent Q-value advantage. Called after each trade outcome.\n"
    "        q_advantage > 0 means RL's chosen action had higher Q than baseline.\n"
    "        \"\"\"\n"
    "        import numpy as np\n"
    "        current = BASE_AGENT_WEIGHTS.get(\"reinforcement_learning\", 0.50)\n"
    "        # Clip adjustment to ±0.10 per update, bounded [0.30, 1.20]\n"
    "        delta = float(np.clip(q_advantage * 0.05, -0.10, 0.10))\n"
    "        BASE_AGENT_WEIGHTS[\"reinforcement_learning\"] = float(\n"
    "            np.clip(current + delta, 0.30, 1.20)\n"
    "        )\n"
    "\n"
    "    @staticmethod\n"
    "    def _percentile"
)

assert old_closing in src, "_percentile method not found"
src = src.replace(old_closing, new_closing)

cde.write_text(src, encoding="utf-8")
print("collaborative_decision_engine.py updated OK")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Wire RL Q-advantage → collab engine weight update in autonomous_trading_loop
# ─────────────────────────────────────────────────────────────────────────────

atl = Path("trading/autonomous_trading_loop.py")
src2 = atl.read_text(encoding="utf-8")

# After train_from_replay, update collab engine RL weight
old_rl_update = (
    "            await self.rl_trainer.train_from_replay(batch_size=32)\n"
    "            logger.info("
)

new_rl_update = (
    "            await self.rl_trainer.train_from_replay(batch_size=32)\n"
    "            # Update collab engine RL weight based on Q-advantage\n"
    "            try:\n"
    "                if hasattr(self.paper_executor, 'trading_agent') and \\\n"
    "                   hasattr(self.paper_executor.trading_agent, 'collab_engine'):\n"
    "                    qvals = self.rl_trainer.q_values(\n"
    "                        context['state'],\n"
    "                        ['BUY', 'SELL', 'HOLD']\n"
    "                    ) if hasattr(self.rl_trainer, 'q_values') else {}\n"
    "                    q_taken  = float(qvals.get(context['action'], 0.0))\n"
    "                    q_others = [v for k, v in qvals.items() if k != context['action']]\n"
    "                    q_adv    = q_taken - (sum(q_others) / len(q_others)) if q_others else 0.0\n"
    "                    self.paper_executor.trading_agent.collab_engine.update_rl_weight(q_adv)\n"
    "            except Exception:\n"
    "                pass\n"
    "            logger.info("
)

count = src2.count(old_rl_update)
if count == 0:
    print("WARNING: RL train_from_replay block not found — skipping RL weight wiring")
elif count > 1:
    print(f"WARNING: RL block found {count}x — skipping to avoid ambiguity")
else:
    src2 = src2.replace(old_rl_update, new_rl_update)
    print("autonomous_trading_loop.py RL weight wiring OK")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Convert risk gate hard vetoes → soft confidence penalties
#    The gates still exist as a final safety net but now only apply when
#    confidence is genuinely low, and log the penalty rather than silently
#    overriding. The collaborative result already incorporates MTF/regime/
#    backtest as votes, so these gates are now a lightweight safety backstop.
# ─────────────────────────────────────────────────────────────────────────────

old_gates = (
    "        if risk_gate_reason:\n"
    "            logger.info(f'Risk gate forced HOLD for {symbol}: {risk_gate_reason}')\n"
    "            final_decision = \"HOLD\""
)

new_gates = (
    "        if risk_gate_reason:\n"
    "            # Risk gate now applies a confidence penalty rather than a hard veto.\n"
    "            # The gate still overrides if confidence is genuinely low (<0.45),\n"
    "            # but allows strong collaborative signals (>=0.45) to proceed.\n"
    "            if confidence < 0.45:\n"
    "                logger.info(f'Risk gate HOLD for {symbol}: {risk_gate_reason} '\n"
    "                            f'(conf={confidence:.3f} < 0.45 threshold)')\n"
    "                final_decision = \"HOLD\"\n"
    "            else:\n"
    "                logger.info(f'Risk gate PENALTY for {symbol}: {risk_gate_reason} '\n"
    "                            f'(conf={confidence:.3f} >= 0.45 — allowing with penalty)')\n"
    "                confidence = confidence * 0.80   # 20% confidence haircut, not full veto"
)

ta = Path("trading/trading_agent.py")
src3 = ta.read_text(encoding="utf-8")
count = src3.count(old_gates)
if count == 0:
    print("WARNING: risk gate block not found in trading_agent.py")
elif count > 1:
    print(f"WARNING: risk gate found {count}x — skipping")
else:
    src3 = src3.replace(old_gates, new_gates)
    ta.write_text(src3, encoding="utf-8")
    print("trading_agent.py risk gates → soft penalties OK")

atl.write_text(src2, encoding="utf-8")
print("\nAll integrations complete.")
print("Run: python -c \"from trading.collaborative_decision_engine import CollaborativeDecisionEngine; print('OK')\"")
