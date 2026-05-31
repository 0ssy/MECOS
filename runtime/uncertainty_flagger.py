"""
UncertaintyFlagger — Radical Honesty Layer (MECOS v3.0 Phase 3)

Implements Claude-inspired "radical honesty" by:
- Scoring confidence of each decision (0.0-1.0)
- Tracking assumptions made
- Flagging limitations and edge cases
- Preventing execution of low-confidence plans

Location: runtime/uncertainty_flagger.py
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level categories."""
    VERY_LOW = 0.0  # 0-20%
    LOW = 0.2       # 20-40%
    MEDIUM = 0.5    # 40-60%
    HIGH = 0.75     # 60-80%
    VERY_HIGH = 0.9 # 80-100%


@dataclass
class ConfidenceBreakdown:
    """Detailed confidence score breakdown."""
    signal_strength: float = 0.5
    market_regime: float = 0.5
    volatility_regime: float = 0.5
    data_freshness: float = 0.5
    historical_accuracy: float = 0.5
    edge_case_coverage: float = 0.5
    
    def average(self) -> float:
        """Calculate average confidence."""
        values = [
            self.signal_strength,
            self.market_regime,
            self.volatility_regime,
            self.data_freshness,
            self.historical_accuracy,
            self.edge_case_coverage,
        ]
        return sum(values) / len(values)


@dataclass
class ExecutionApproval:
    """Execution approval with detailed reasoning."""
    plan: str
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    execution_approved: bool = False
    execution_notes: str = ""
    risk_level: str = "medium"  # low, medium, high, critical
    suggested_position_size: float = 1.0  # 0.0-1.0 multiplier
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class UncertaintyFlagger:
    """
    Implement radical honesty by flagging uncertainties and limitations.
    
    Responsibilities:
    - Score confidence of trading plans
    - Track assumptions and limitations
    - Prevent low-confidence execution
    - Provide transparent reasoning
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.60,
        track_assumptions: bool = True,
        flag_limitations: bool = True,
    ):
        """
        Initialize UncertaintyFlagger.
        
        Args:
            confidence_threshold: Min confidence to approve execution (0.0-1.0)
            track_assumptions: Whether to track assumptions
            flag_limitations: Whether to flag limitations
        """
        self.confidence_threshold = confidence_threshold
        self.track_assumptions = track_assumptions
        self.flag_limitations = flag_limitations
        
        # History of approvals for analysis
        self.approval_history = []
        
        logger.info(f"UncertaintyFlagger initialized")
        logger.info(f"  Confidence threshold: {confidence_threshold:.1%}")
        logger.info(f"  Track assumptions: {track_assumptions}")
        logger.info(f"  Flag limitations: {flag_limitations}")
    
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
        """
        Score a trading plan and determine if it should be executed.
        
        Args:
            plan: Description of the trading plan
            signal_strength: Strength of trading signal (0.0-1.0)
            market_regime: Confidence in market regime (0.0-1.0)
            volatility_regime: Confidence in volatility regime (0.0-1.0)
            data_freshness: Freshness of data used (0.0-1.0)
            historical_accuracy: Historical accuracy of strategy (0.0-1.0)
            edge_case_coverage: Coverage of edge cases (0.0-1.0)
            assumptions: List of assumptions made
            limitations: List of limitations
            edge_cases: List of edge cases
        
        Returns:
            ExecutionApproval object
        """
        # Calculate confidence breakdown
        breakdown = ConfidenceBreakdown(
            signal_strength=signal_strength,
            market_regime=market_regime,
            volatility_regime=volatility_regime,
            data_freshness=data_freshness,
            historical_accuracy=historical_accuracy,
            edge_case_coverage=edge_case_coverage,
        )
        
        confidence_score = breakdown.average()
        
        # Determine if execution is approved
        execution_approved = confidence_score >= self.confidence_threshold
        
        # Determine risk level
        if confidence_score < 0.3:
            risk_level = "critical"
            suggested_position_size = 0.0
        elif confidence_score < 0.5:
            risk_level = "high"
            suggested_position_size = 0.25
        elif confidence_score < 0.75:
            risk_level = "medium"
            suggested_position_size = 0.5
        elif confidence_score < 0.9:
            risk_level = "low"
            suggested_position_size = 0.75
        else:
            risk_level = "very_low"
            suggested_position_size = 1.0
        
        # Prepare execution notes
        execution_notes = self._prepare_execution_notes(
            confidence_score,
            execution_approved,
            risk_level,
            suggested_position_size,
        )
        
        # Create approval object
        approval = ExecutionApproval(
            plan=plan,
            confidence_score=confidence_score,
            confidence_breakdown=breakdown,
            assumptions=assumptions or [],
            limitations=limitations or [],
            edge_cases=edge_cases or [],
            execution_approved=execution_approved,
            execution_notes=execution_notes,
            risk_level=risk_level,
            suggested_position_size=suggested_position_size,
        )
        
        # Log approval
        self.approval_history.append(approval)
        
        # Log decision
        if execution_approved:
            logger.info(f"✓ Plan approved (confidence: {confidence_score:.1%}): {plan}")
        else:
            logger.warning(f"✗ Plan rejected (confidence: {confidence_score:.1%}): {plan}")
        
        return approval
    
    def _prepare_execution_notes(
        self,
        confidence_score: float,
        execution_approved: bool,
        risk_level: str,
        suggested_position_size: float,
    ) -> str:
        """Prepare human-readable execution notes."""
        if not execution_approved:
            return (
                f"Low confidence ({confidence_score:.1%}). "
                f"Execution blocked. Risk level: {risk_level}. "
                f"Suggested action: Wait for higher-confidence signal."
            )
        
        if suggested_position_size < 1.0:
            return (
                f"Moderate confidence ({confidence_score:.1%}). "
                f"Execute with {suggested_position_size:.0%} position size. "
                f"Risk level: {risk_level}."
            )
        
        return (
            f"High confidence ({confidence_score:.1%}). "
            f"Execute with full position size. "
            f"Risk level: {risk_level}."
        )
    
    def flag_assumption(self, assumption: str) -> None:
        """Log an assumption."""
        if self.track_assumptions:
            logger.debug(f"Assumption flagged: {assumption}")
    
    def flag_limitation(self, limitation: str) -> None:
        """Log a limitation."""
        if self.flag_limitations:
            logger.warning(f"Limitation flagged: {limitation}")
    
    def flag_edge_case(self, edge_case: str) -> None:
        """Log an edge case."""
        logger.info(f"Edge case flagged: {edge_case}")
    
    def get_approval_statistics(self) -> Dict[str, Any]:
        """Get statistics on approval decisions."""
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
        
        approved = sum(1 for a in self.approval_history if a.execution_approved)
        rejected = len(self.approval_history) - approved
        
        confidences = [a.confidence_score for a in self.approval_history]
        
        return {
            "total_plans_scored": len(self.approval_history),
            "approved_count": approved,
            "rejected_count": rejected,
            "approval_rate": approved / len(self.approval_history),
            "avg_confidence": sum(confidences) / len(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
        }
    
    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence levels."""
        distribution = {
            "very_low": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "very_high": 0,
        }
        
        for approval in self.approval_history:
            score = approval.confidence_score
            
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
        """Export approval history to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_approvals": len(self.approval_history),
            "statistics": self.get_approval_statistics(),
            "confidence_distribution": self.get_confidence_distribution(),
            "approvals": [
                {
                    "plan": a.plan,
                    "confidence_score": a.confidence_score,
                    "execution_approved": a.execution_approved,
                    "risk_level": a.risk_level,
                    "suggested_position_size": a.suggested_position_size,
                    "assumptions": a.assumptions,
                    "limitations": a.limitations,
                    "edge_cases": a.edge_cases,
                    "timestamp": a.timestamp,
                }
                for a in self.approval_history
            ],
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Approval history exported to {filepath}")
    
    def format_approval_report(self, approval: ExecutionApproval) -> str:
        """Format approval as human-readable report."""
        lines = []
        
        lines.append("═" * 70)
        lines.append("EXECUTION APPROVAL REPORT")
        lines.append("═" * 70)
        lines.append("")
        
        lines.append(f"Plan: {approval.plan}")
        lines.append(f"Timestamp: {approval.timestamp}")
        lines.append("")
        
        # Confidence
        lines.append("CONFIDENCE ANALYSIS")
        lines.append("-" * 70)
        lines.append(f"Overall Score: {approval.confidence_score:.1%}")
        lines.append(f"Status: {'✓ APPROVED' if approval.execution_approved else '✗ REJECTED'}")
        lines.append(f"Risk Level: {approval.risk_level.upper()}")
        lines.append(f"Suggested Position Size: {approval.suggested_position_size:.0%}")
        lines.append("")
        
        # Breakdown
        lines.append("CONFIDENCE BREAKDOWN")
        lines.append("-" * 70)
        breakdown = approval.confidence_breakdown
        lines.append(f"Signal Strength:        {breakdown.signal_strength:.1%}")
        lines.append(f"Market Regime:          {breakdown.market_regime:.1%}")
        lines.append(f"Volatility Regime:      {breakdown.volatility_regime:.1%}")
        lines.append(f"Data Freshness:         {breakdown.data_freshness:.1%}")
        lines.append(f"Historical Accuracy:    {breakdown.historical_accuracy:.1%}")
        lines.append(f"Edge Case Coverage:     {breakdown.edge_case_coverage:.1%}")
        lines.append("")
        
        # Assumptions
        if approval.assumptions:
            lines.append("ASSUMPTIONS")
            lines.append("-" * 70)
            for assumption in approval.assumptions:
                lines.append(f"• {assumption}")
            lines.append("")
        
        # Limitations
        if approval.limitations:
            lines.append("LIMITATIONS")
            lines.append("-" * 70)
            for limitation in approval.limitations:
                lines.append(f"⚠ {limitation}")
            lines.append("")
        
        # Edge Cases
        if approval.edge_cases:
            lines.append("EDGE CASES")
            lines.append("-" * 70)
            for edge_case in approval.edge_cases:
                lines.append(f"⚡ {edge_case}")
            lines.append("")
        
        # Execution Notes
        lines.append("EXECUTION NOTES")
        lines.append("-" * 70)
        lines.append(approval.execution_notes)
        lines.append("")
        
        lines.append("═" * 70)
        
        return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Example usage
    flagger = UncertaintyFlagger(confidence_threshold=0.60)
    
    # Score a trading plan
    approval = flagger.score_plan(
        plan="Execute BTC momentum trade",
        signal_strength=0.92,
        market_regime=0.85,
        volatility_regime=0.78,
        data_freshness=0.95,
        historical_accuracy=0.88,
        edge_case_coverage=0.70,
        assumptions=[
            "BTC will continue uptrend (based on 4-hour chart)",
            "Fed policy remains unchanged",
            "Market liquidity remains normal",
        ],
        limitations=[
            "Only 14 days of training data",
            "Strategy not tested in bear market",
            "No black swan event handling",
        ],
        edge_cases=[
            "Sudden Fed announcement",
            "Major exchange outage",
            "Regulatory news",
        ],
    )
    
    print(flagger.format_approval_report(approval))
    
    # Get statistics
    print("\n\nAPPROVAL STATISTICS")
    print("=" * 70)
    stats = flagger.get_approval_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.1%}")
        else:
            print(f"{key}: {value}")
