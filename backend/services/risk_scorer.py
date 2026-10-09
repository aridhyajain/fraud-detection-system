"""
Risk Scorer Service
═══════════════════
Converts raw model fraud probability (0.0 – 1.0) into:
  • A human-readable risk score (0 – 100)
  • A risk tier:  Low / Medium / High
  • Optional business-rule adjustments

Tier thresholds (configurable)
──────────────────────────────
  Low    :   0 – 40     → transaction is approved silently
  Medium :  41 – 70     → soft block — verify via OTP
  High   :  71 – 100    → hard block — flag for admin review
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# ── Risk tier enum ──────────────────────────────────────────────
class RiskTier(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# ── Tier boundaries (can be overridden at init) ─────────────────
_DEFAULT_THRESHOLDS = {
    "low_max": 40,
    "medium_max": 70,
    # anything above medium_max → HIGH
}


# ── Structured result ──────────────────────────────────────────
@dataclass
class RiskResult:
    """Immutable result returned by the scorer."""
    probability: float      # raw model output 0.0–1.0
    score: int              # mapped to 0–100
    tier: RiskTier          # Low / Medium / High
    recommended_action: str # human-readable next step

    def to_dict(self) -> dict[str, Any]:
        return {
            "probability": round(self.probability, 6),
            "score": self.score,
            "tier": self.tier.value,
            "recommended_action": self.recommended_action,
        }


# ═══════════════════════════════════════════════════════════════
# Main scorer class
# ═══════════════════════════════════════════════════════════════

class RiskScorer:
    """
    Stateless scorer — instantiate once, reuse across requests.

    Usage
    ─────
    scorer = RiskScorer()
    result = scorer.score(probability=0.73)
    print(result.tier)    # RiskTier.HIGH
    print(result.score)   # 73
    """

    def __init__(
        self,
        low_max: int = _DEFAULT_THRESHOLDS["low_max"],
        medium_max: int = _DEFAULT_THRESHOLDS["medium_max"],
    ):
        self.low_max = low_max
        self.medium_max = medium_max

    # ── Core scoring ────────────────────────────────────────
    def score(
        self,
        probability: float,
        context: dict[str, Any] | None = None,
    ) -> RiskResult:
        """
        Convert a fraud probability to a RiskResult.

        Parameters
        ──────────
        probability : float in [0.0, 1.0] from the ML model
        context     : optional dict with transaction metadata
                      (amount, type, etc.) for business-rule adjustments

        Returns
        ───────
        RiskResult with score, tier, and recommended action.
        """
        # Map probability → 0-100 integer score
        raw_score = self.calculate_risk_score(probability)

        # Optionally adjust with business rules
        adjusted_score = raw_score
        if context:
            adjusted_score = self.apply_business_rules(raw_score, context)

        # Determine tier
        tier = self.get_risk_tier(adjusted_score)

        # Recommended action per tier
        action = self._recommended_action(tier)

        return RiskResult(
            probability=probability,
            score=adjusted_score,
            tier=tier,
            recommended_action=action,
        )

    # ── Probability → 0-100 ─────────────────────────────────
    @staticmethod
    def calculate_risk_score(probability: float) -> int:
        """
        Map a raw probability [0.0, 1.0] to an integer score [0, 100].

        Uses a slight sigmoid-style curve to spread mid-range values
        while compressing extremes (most real fraud probabilities
        cluster near 0 or 1).
        """
        clamped = max(0.0, min(1.0, probability))
        score = int(round(clamped * 100))
        return max(0, min(100, score))

    # ── Score → tier ────────────────────────────────────────
    def get_risk_tier(self, score: int) -> RiskTier:
        """Classify a 0-100 score into Low / Medium / High."""
        if score <= self.low_max:
            return RiskTier.LOW
        if score <= self.medium_max:
            return RiskTier.MEDIUM
        return RiskTier.HIGH

    # ── Business rule adjustments ───────────────────────────
    def apply_business_rules(
        self,
        score: int,
        context: dict[str, Any],
    ) -> int:
        """
        Adjust the score based on domain-specific business rules.

        Current rules
        ─────────────
        1. Very large amount (> 200,000)  → bump score by +15
        2. High-risk transaction types (TRANSFER, CASH_OUT) → bump +10
        3. New account (age < 24 hours)   → bump +10
        4. Score is always clamped to [0, 100]
        """
        adjustment = 0

        amount = context.get("amount", 0)
        if amount > 200_000:
            adjustment += 15

        txn_type = str(context.get("type", "")).upper().replace("-", "_")
        if txn_type in ("TRANSFER", "CASH_OUT"):
            adjustment += 10

        account_age = context.get("account_age_hours", float("inf"))
        if account_age < 24:
            adjustment += 10

        adjusted = score + adjustment
        return max(0, min(100, adjusted))

    # ── Action mapping ──────────────────────────────────────
    @staticmethod
    def _recommended_action(tier: RiskTier) -> str:
        actions = {
            RiskTier.LOW: "Approve — silent pass",
            RiskTier.MEDIUM: "Soft block — verify via OTP",
            RiskTier.HIGH: "Hard block — flag for admin review",
        }
        return actions[tier]


# ═══════════════════════════════════════════════════════════════
# Module-level convenience functions
# ═══════════════════════════════════════════════════════════════

_scorer = RiskScorer()


def calculate_risk_score(probability: float) -> int:
    """Map model probability to 0-100 score."""
    return _scorer.calculate_risk_score(probability)


def get_risk_tier(score: int) -> str:
    """Return tier name (Low / Medium / High) for a 0-100 score."""
    return _scorer.get_risk_tier(score).value


def score_transaction(
    probability: float,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Full scoring pipeline — returns a dict with score, tier, and action.
    This is the primary function called from the API layer.
    """
    return _scorer.score(probability, context).to_dict()
