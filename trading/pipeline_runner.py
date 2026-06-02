from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger


class PipelineRunner:
    """Runs a JSON-defined strategy pipeline over in-memory market bars."""

    def __init__(self):
        self.supported_nodes = {
            "data_source",
            "indicator",
            "macro_filter",
            "signal",
            "risk_manager",
            "executor",
        }

    @staticmethod
    def load(path: str) -> Dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Pipeline file must contain a JSON object.")
        return payload

    def validate(self, config: Dict[str, Any]) -> None:
        nodes = config.get("nodes", [])
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("Pipeline requires a non-empty 'nodes' list.")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Each pipeline node must be an object.")
            node_type = str(node.get("type", "")).strip()
            if node_type not in self.supported_nodes:
                raise ValueError(f"Unsupported node type: {node_type}")

    def run(self, config: Dict[str, Any], bars: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.validate(config)
        if not isinstance(bars, list) or not bars:
            raise ValueError("bars must be a non-empty list.")

        closes = [float(b.get("close", 0.0) or 0.0) for b in bars if "close" in b]
        if len(closes) < 20:
            return {
                "status": "SKIPPED",
                "decision": "HOLD",
                "reason": "insufficient_bars",
            }

        outputs: Dict[str, Any] = {"pipeline": config.get("pipeline", "unnamed")}
        for node in config.get("nodes", []):
            node_id = str(node.get("id", "unknown"))
            node_type = str(node.get("type", ""))
            params = node.get("params", {}) or {}

            if node_type == "data_source":
                outputs[node_id] = {"bars": len(bars), "latest_close": closes[-1]}
                continue

            if node_type == "indicator":
                period = int(params.get("period", 14))
                delta = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
                gains = [max(x, 0.0) for x in delta[-period:]]
                losses = [abs(min(x, 0.0)) for x in delta[-period:]]
                avg_gain = sum(gains) / max(len(gains), 1)
                avg_loss = sum(losses) / max(len(losses), 1)
                rsi = 100.0 if avg_loss == 0.0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
                outputs[node_id] = {"rsi": round(float(rsi), 2)}
                continue

            if node_type == "macro_filter":
                mode = str(params.get("mode", "neutral")).lower()
                roc20 = (closes[-1] / closes[-20]) - 1.0 if closes[-20] != 0 else 0.0
                macro_pass = roc20 >= 0 if mode == "risk_on" else roc20 <= 0 if mode == "risk_off" else True
                outputs[node_id] = {"macro_pass": bool(macro_pass), "proxy_roc20": float(roc20)}
                continue

            if node_type == "signal":
                buy_rsi = float(params.get("buy_rsi", 35))
                sell_rsi = float(params.get("sell_rsi", 65))
                rsi = self._latest_rsi(outputs)
                if rsi <= buy_rsi:
                    signal = "BUY"
                elif rsi >= sell_rsi:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                outputs[node_id] = {"signal": signal, "rsi": rsi}
                continue

            if node_type == "risk_manager":
                signal = self._latest_signal(outputs)
                max_position = float(params.get("max_position", 0.10))
                outputs[node_id] = {
                    "approved": signal in {"BUY", "SELL"},
                    "size": max(0.0, min(1.0, max_position)),
                }
                continue

            if node_type == "executor":
                signal = self._latest_signal(outputs)
                approved = self._latest_approval(outputs)
                decision = signal if approved else "HOLD"
                outputs[node_id] = {"decision": decision}
                outputs["decision"] = decision

        if "decision" not in outputs:
            outputs["decision"] = self._latest_signal(outputs) or "HOLD"
        logger.info(f"Pipeline '{outputs['pipeline']}' decision: {outputs['decision']}")
        outputs["status"] = "OK"
        return outputs

    @staticmethod
    def _latest_rsi(outputs: Dict[str, Any]) -> float:
        for key in reversed(list(outputs.keys())):
            row = outputs.get(key)
            if isinstance(row, dict) and "rsi" in row:
                return float(row["rsi"])
        return 50.0

    @staticmethod
    def _latest_signal(outputs: Dict[str, Any]) -> str:
        for key in reversed(list(outputs.keys())):
            row = outputs.get(key)
            if isinstance(row, dict) and "signal" in row:
                return str(row["signal"]).upper()
        return "HOLD"

    @staticmethod
    def _latest_approval(outputs: Dict[str, Any]) -> bool:
        for key in reversed(list(outputs.keys())):
            row = outputs.get(key)
            if isinstance(row, dict) and "approved" in row:
                return bool(row["approved"])
        return False
