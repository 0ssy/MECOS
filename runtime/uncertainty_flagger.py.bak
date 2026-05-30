from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBreakdown:
    signal_strength: float = 0.5
    market_regime: float = 0.5
    volatility_regime: float = 0.5
    data_freshness: float = 0.5
    historical_accuracy: float = 0.5
    edge_case_coverage: float = 0.5

    def average(self) -> float:
        values = [
            self.signal_strength,
            self.market_regime,
            self.volatility_regime,
            self.data_freshness,
            self.historical_accuracy,
            self.edge_case_coverage,
        ]
        return float(sum(values) / len(values))


@dataclass
class ExecutionApproval:
    plan: str
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    execution_approved: bool = False
    execution_notes: str = ""
    risk_level: str = "medium"
    suggested_position_size: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class UncertaintyFlagger:
    def __init__(
        self,
        confidence_threshold: float = 0.75,
        track_assumptions: bool = True,
        flag_limitations: bool = True,
    ):
        self.confidence_threshold = float(confidence_threshold)
        self.track_assumptions = bool(track_assumptions)
        self.flag_limitations = bool(flag_limitations)
        self.approval_history: List[ExecutionApproval] = []

    def score_plan(
        self,
        plan: str,
        signal_strength: float = 0.5,
        market_regime: float = 0.5,
        volatility_regime: float = 0.5,
        data_freshness: float = 0.5,
        historical_accuracy: float = 0.5,
        edge_case_coverage: float = 0.5,
        assumptions: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None,
        edge_cases: Optional[List[str]] = None,
    ) -> ExecutionApproval:
        breakdown = ConfidenceBreakdown(
            signal_strength=float(signal_strength),
            market_regime=float(market_regime),
            volatility_regime=float(volatility_regime),
            data_freshness=float(data_freshness),
            historical_accuracy=float(historical_accuracy),
            edge_case_coverage=float(edge_case_coverage),
        )
        confidence_score = breakdown.average()
        execution_approved = confidence_score >= self.confidence_threshold

        if confidence_score < 0.3:
            risk_level = "critical"
            size_multiplier = 0.0
        elif confidence_score < 0.5:
            risk_level = "high"
            size_multiplier = 0.25
        elif confidence_score < self.confidence_threshold:
            risk_level = "medium"
            size_multiplier = 0.5
        elif confidence_score < 0.9:
            risk_level = "low"
            size_multiplier = 0.75
        else:
            risk_level = "very_low"
            size_multiplier = 1.0

        if not execution_approved:
            notes = (
                f"Low confidence ({confidence_score:.1%}). "
                "Execution blocked pending higher-quality signal."
            )
        elif size_multiplier < 1.0:
            notes = (
                f"Moderate confidence ({confidence_score:.1%}). "
                f"Size scaled to {size_multiplier:.0%}."
            )
        else:
            notes = f"High confidence ({confidence_score:.1%}). Full size allowed."

        approval = ExecutionApproval(
            plan=str(plan),
            confidence_score=float(confidence_score),
            confidence_breakdown=breakdown,
            assumptions=list(assumptions or []),
            limitations=list(limitations or []),
            edge_cases=list(edge_cases or []),
            execution_approved=bool(execution_approved),
            execution_notes=notes,
            risk_level=risk_level,
            suggested_position_size=float(size_multiplier),
        )
        self.approval_history.append(approval)
        return approval

    def get_approval_statistics(self) -> Dict[str, Any]:
        if not self.approval_history:
            return {
                "total_plans_scored": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "approval_rate": 0.0,
                "avg_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0,
            }
        approved = sum(1 for item in self.approval_history if item.execution_approved)
        confidences = [item.confidence_score for item in self.approval_history]
        total = len(self.approval_history)
        return {
            "total_plans_scored": total,
            "approved_count": approved,
            "rejected_count": total - approved,
            "approval_rate": float(approved / total),
            "avg_confidence": float(sum(confidences) / total),
            "min_confidence": float(min(confidences)),
            "max_confidence": float(max(confidences)),
        }

    def get_confidence_distribution(self) -> Dict[str, int]:
        distribution = {
            "very_low": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "very_high": 0,
        }
        for item in self.approval_history:
            score = float(item.confidence_score)
            if score < 0.2:
                distribution["very_low"] += 1
            elif score < 0.4:
                distribution["low"] += 1
            elif score < 0.6:
                distribution["medium"] += 1
            elif score < 0.8:
                distribution["high"] += 1
            else:
                distribution["very_high"] += 1
        return distribution

    def export_approval_history(self, filepath: str) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "total_approvals": len(self.approval_history),
            "statistics": self.get_approval_statistics(),
            "confidence_distribution": self.get_confidence_distribution(),
            "approvals": [
                {
                    "plan": item.plan,
                    "confidence_score": item.confidence_score,
                    "execution_approved": item.execution_approved,
                    "risk_level": item.risk_level,
                    "suggested_position_size": item.suggested_position_size,
                    "assumptions": item.assumptions,
                    "limitations": item.limitations,
                    "edge_cases": item.edge_cases,
                    "timestamp": item.timestamp,
                }
                for item in self.approval_history
            ],
        }
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        logger.info(f"Uncertainty approval history exported to {filepath}")
