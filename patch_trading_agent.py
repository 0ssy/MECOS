"""
patch_trading_agent.py  (v2 — collaborative engine wiring)
Run from MECOS root: python patch_trading_agent.py
"""
from pathlib import Path

p = Path("trading/trading_agent.py")
src = p.read_text(encoding="utf-8")

# ── 1. Replace the four-layer decision chain ──────────────────────────────────
old_chain = (
    "        orchestrator_data = {symbol: valid_data}\n"
    "        orchestrated = await self.meta_orchestrator.orchestrate_signals(\n"
    "            orchestrator_data,\n"
    "            regime,\n"
    "            features,\n"
    "            physics,\n"
    "        )\n"
    "        # --- QuantSignalFusion: regime-aware Bayesian fusion ---\n"
    "        fused = self.quant_fusion.fuse(\n"
    "            orchestrated_signals=orchestrated,\n"
    "            features=features,\n"
    "            regime=regime,\n"
    "        )\n"
    "        # Kelly-fraction position sizing\n"
    "        _edge = float(fused.get(\"edge\", 0.0))\n"
    "        _conf = float(fused.get(\"confidence\", 0.0))\n"
    "        _vol = max(float(features.get(\"realized_volatility\", 0.02)), 0.01)\n"
    "        _kelly = float(np.clip(0.5 * (_edge * _conf) / _vol, 0.01, 0.20)) if _edge > 0 and _conf > 0 else 0.01\n"
    "        fused[\"kelly_fraction\"] = _kelly\n"
    "        fused[\"allocation\"] = _kelly\n"
    "        orchestrated = {**orchestrated, **fused}\n"
    "        # NOTE: second signal_fusion.fuse() call removed — it received\n"
    "        # already-fused output with no agent_signals key, so always\n"
    "        # returned HOLD/0.0 and overwrote the correct first-pass result.\n"
    "\n"
    "        orchestrator_decision = str(orchestrated.get(\"final_decision\", \"HOLD\")).upper()\n"
    "        final_decision = str(fused.get(\"decision\", orchestrator_decision)).upper()\n"
    "        confidence = float(fused.get(\"confidence\", orchestrated.get(\"confidence\", 0.0)))\n"
    "        edge = float(fused.get(\"edge\", 0.0))\n"
    "        if orchestrator_decision == \"HOLD\" and abs(edge) < 0.05:\n"
    "            final_decision = \"HOLD\"\n"
    "\n"
    "        consensus = self.consensus_engine.coordinate_debate(\n"
    "            topic=symbol,\n"
    "            context={\n"
    "                \"asset_type\": persona_asset_type,\n"
    "                \"regime\": regime,\n"
    "                \"base_decision\": final_decision,\n"
    "                \"base_confidence\": confidence,\n"
    "                \"features\": features,\n"
    "                \"edge\": edge,\n"
    "                \"active_personas\": active_personas,\n"
    "                \"external_market_context\": external_market_context,\n"
    "            },\n"
    "        )\n"
    "        consensus_decision = str(consensus.get(\"final_decision\", \"HOLD\")).upper()\n"
    "        if len(consensus.get(\"dissenting_opinions\", [])) > len(consensus.get(\"perspectives\", {}) or {}) // 2:\n"
    "            final_decision = \"HOLD\"\n"
    "            confidence = min(confidence, float(consensus.get(\"confidence_score\", confidence)))\n"
    "        elif consensus_decision == \"HOLD\":\n"
    "            final_decision = \"HOLD\"\n"
    "            confidence = min(confidence, float(consensus.get(\"confidence_score\", confidence)))\n"
    "        else:\n"
    "            final_decision = consensus_decision\n"
    "            confidence = max(confidence, float(consensus.get(\"confidence_score\", confidence)))"
)

new_chain = (
    "        # ── Unified collaborative decision — replaces four-layer chain ──────────\n"
    "        collab = await self.collab_engine.decide(\n"
    "            symbol=symbol,\n"
    "            data=valid_data,\n"
    "            features=features,\n"
    "            regime=regime,\n"
    "            physics=physics,\n"
    "            asset_type=persona_asset_type,\n"
    "            news_score=float(news_snapshot.get(\"sentiment_score\", 0.0) or 0.0),\n"
    "            macro_snapshot=macro_snapshot,\n"
    "            extra_context={\n"
    "                \"active_personas\": active_personas,\n"
    "                \"external_market_context\": external_market_context,\n"
    "            },\n"
    "        )\n"
    "        final_decision = str(collab.get(\"decision\", \"HOLD\")).upper()\n"
    "        confidence     = float(collab.get(\"confidence\", 0.0))\n"
    "        edge           = float(collab.get(\"edge\", 0.0))\n"
    "        orchestrated   = collab  # keep legacy key for downstream code\n"
    "\n"
    "        # Kelly-fraction position sizing\n"
    "        _vol   = max(float(features.get(\"realized_volatility\", 0.02)), 0.01)\n"
    "        _kelly = float(np.clip(0.5 * (abs(edge) * confidence) / _vol, 0.01, 0.20)) \\\n"
    "            if edge != 0 and confidence > 0 else 0.01\n"
    "        orchestrated[\"kelly_fraction\"] = _kelly\n"
    "        orchestrated[\"allocation\"]     = _kelly"
)

count = src.count(old_chain)
if count == 0:
    print("ERROR: chain block not found — printing context to help debug")
    # Find orchestrate_signals to show nearby text
    i = src.find("orchestrate_signals")
    print(repr(src[i:i+200]))
elif count > 1:
    print(f"ERROR: found {count} matches — ambiguous")
else:
    src = src.replace(old_chain, new_chain)
    print("Chain replacement OK")

# ── 2. Add collab_engine init after consensus_engine ─────────────────────────
old_init = (
    "        self.consensus_engine = ConsensusEngine(\n"
    "            self.persona_engine.get_personas(),\n"
    "            minimum_support_ratio=min_support,\n"
    "            require_unanimous=require_unanimous,\n"
    "        )"
)

new_init = (
    "        self.consensus_engine = ConsensusEngine(\n"
    "            self.persona_engine.get_personas(),\n"
    "            minimum_support_ratio=min_support,\n"
    "            require_unanimous=require_unanimous,\n"
    "        )\n"
    "        # Unified collaborative engine — replaces MetaOrchestrator + ConsensusEngine chain\n"
    "        from trading.collaborative_decision_engine import CollaborativeDecisionEngine\n"
    "        self.collab_engine = CollaborativeDecisionEngine(\n"
    "            agents=self.meta_orchestrator.agents,\n"
    "            personas={\n"
    "                name: self.consensus_engine._persona_analysis\n"
    "                for name in self.consensus_engine.personas\n"
    "            },\n"
    "        )"
)

count2 = src.count(old_init)
if count2 == 0:
    print("ERROR: consensus_engine init block not found")
elif count2 > 1:
    print(f"ERROR: found {count2} matches for init block — ambiguous")
else:
    src = src.replace(old_init, new_init)
    print("Init wiring OK")

# ── 3. Save ───────────────────────────────────────────────────────────────────
p.write_text(src, encoding="utf-8")
print("trading_agent.py saved")
