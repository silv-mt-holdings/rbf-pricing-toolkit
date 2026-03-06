"""
Risk Pricing Engine

Primary integration bridge between rbf-scoring-toolkit and rbf-pricing-toolkit.
Risk score is the PRIMARY output; pricing (factor, advance, term) is derived from it.

Flow:
  bank analytics + application data
       ↓
  RBFScoringModel (rbf-scoring-toolkit)
       ↓ ScoringResult (0-100 score, letter grade, component breakdown)
       ↓
  IndustryAdjuster (industry factor_mod + advance cap)
       ↓
  RiskScoredPricing  ← score first, pricing second
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# PRIMARY OUTPUT MODEL
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskScoredPricing:
    """
    Unified risk score + pricing output.

    Risk score fields are PRIMARY. Pricing fields are derived from the score.

    Risk score section:
        risk_score          — composite 0–100
        letter_grade        — A+ through F
        risk_tier           — 1 (best) to 5 (specialty)
        is_approvable       — True if score ≥ 40
        score_breakdown     — per-component scores (11 components)

    Industry section:
        industry            — normalized industry key
        industry_tier       — 1–5
        industry_tier_label — human-readable tier label
        industry_note       — underwriter note from risk DB
        score_adjustment    — points added/subtracted from composite score
        factor_mod          — adjustment applied to factor rate

    Pricing section (derived from score + industry):
        recommended_factor  — factor rate to quote
        factor_range        — (min, max) factor range for grade
        max_advance         — max dollar advance
        max_advance_pct     — max advance as % of monthly revenue
        term_months_range   — (min, max) term in months
        holdback_pct        — suggested holdback percentage
        payment_structure   — "daily" or "weekly"

    Flags:
        warnings            — non-blocking caution flags
        blockers            — blocking pre-check failures
    """
    # ── PRIMARY: Risk Score ───────────────────────────────────────────────────
    risk_score: float
    letter_grade: str
    risk_tier: int
    is_approvable: bool
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    # ── Industry ──────────────────────────────────────────────────────────────
    industry: str = ""
    industry_tier: int = 0
    industry_tier_label: str = ""
    industry_note: str = ""
    score_adjustment: float = 0.0
    factor_mod: float = 0.0

    # ── Pricing (derived) ─────────────────────────────────────────────────────
    recommended_factor: float = 0.0
    factor_range: Tuple[float, float] = (0.0, 0.0)
    max_advance: float = 0.0
    max_advance_pct: float = 0.0
    term_months_range: Tuple[int, int] = (0, 0)
    holdback_pct: float = 0.0
    payment_structure: str = "daily"

    # ── Flags ─────────────────────────────────────────────────────────────────
    warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary for logging / CLI output."""
        status = "APPROVABLE" if self.is_approvable else "DECLINE"
        ind = f" | {self.industry} (T{self.industry_tier})" if self.industry else ""
        return (
            f"[{status}] {self.letter_grade} | Score: {self.risk_score:.1f}/100"
            f"{ind} | Factor: {self.recommended_factor:.2f}"
            f" | Max Advance: ${self.max_advance:,.0f}"
        )

    def to_dict(self) -> dict:
        """Serialize to dict for API responses / JSON output."""
        return {
            "risk_score": round(self.risk_score, 2),
            "letter_grade": self.letter_grade,
            "risk_tier": self.risk_tier,
            "is_approvable": self.is_approvable,
            "score_breakdown": {k: round(v, 2) for k, v in self.score_breakdown.items()},
            "industry": {
                "key": self.industry,
                "tier": self.industry_tier,
                "tier_label": self.industry_tier_label,
                "note": self.industry_note,
                "score_adjustment": self.score_adjustment,
                "factor_mod": self.factor_mod,
            },
            "pricing": {
                "recommended_factor": round(self.recommended_factor, 4),
                "factor_range": list(self.factor_range),
                "max_advance": round(self.max_advance, 2),
                "max_advance_pct": round(self.max_advance_pct, 4),
                "term_months_range": list(self.term_months_range),
                "holdback_pct": self.holdback_pct,
                "payment_structure": self.payment_structure,
            },
            "flags": {
                "warnings": self.warnings,
                "blockers": self.blockers,
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# HOLDBACK + PAYMENT STRUCTURE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _holdback_pct(grade: str) -> float:
    if grade.startswith("A"):
        return 0.10
    elif grade.startswith("B"):
        return 0.12
    elif grade.startswith("C"):
        return 0.15
    return 0.18


def _payment_structure(max_advance: float) -> str:
    return "daily" if max_advance > 25000 else "weekly"


# ──────────────────────────────────────────────────────────────────────────────
# ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class RiskPricingEngine:
    """
    Score-first pricing engine.

    Accepts either:
    1. A pre-computed ``ScoringResult`` from rbf-scoring-toolkit (preferred)
    2. Raw deal inputs — runs the scorer internally

    In both cases, ``RiskScoredPricing`` is returned with the risk score
    as the primary field and pricing as derived output.

    Usage — from ScoringResult::

        from scoring import RBFScoringModel
        from pricing import RiskPricingEngine

        model = RBFScoringModel()
        model.set_application(industry="restaurant", fico_score=640,
                              time_in_business_months=18)
        model.set_bank_analytics(monthly_true_revenue=80000,
                                 average_daily_balance=9000,
                                 nsf_count_90d=3)
        score_result = model.score(requested_amount=50000)

        engine = RiskPricingEngine()
        output = engine.from_score_result(score_result)
        print(output.summary())

    Usage — raw inputs (scorer runs internally)::

        output = engine.score_and_price(
            industry="restaurant",
            fico_score=640,
            time_in_business_months=18,
            monthly_true_revenue=80000,
            average_daily_balance=9000,
            nsf_count_90d=3,
            requested_amount=50000,
        )
        print(output.summary())
        print(output.to_dict())
    """

    def from_score_result(self, score_result: object) -> RiskScoredPricing:
        """
        Build RiskScoredPricing from a ScoringResult.

        Args:
            score_result: ScoringResult from rbf-scoring-toolkit

        Returns:
            RiskScoredPricing with risk score as primary output
        """
        from pricing.industry_adjuster import IndustryAdjuster, _TIER_LABELS

        # Resolve industry info
        industry_key = ""
        industry_tier = 0
        industry_tier_label = ""
        industry_note = score_result.industry_note or ""
        score_adj = score_result.component_scores.get("industry_adjustment", 0.0)
        factor_mod = 0.0

        app = getattr(score_result, "_application", None)
        industry_str = ""
        # ScoringResult doesn't store raw industry; pull from component scores note
        # Try to extract from metadata if present
        if hasattr(score_result, "metadata") and score_result.metadata:
            industry_str = score_result.metadata.get("industry", "")

        if industry_str:
            adjuster = IndustryAdjuster()
            adj = adjuster.lookup(industry_str)
            if adj:
                industry_key = adj.industry
                industry_tier = adj.tier
                industry_tier_label = adj.tier_label
                industry_note = adj.note
                score_adj = adj.score_adjustment
                factor_mod = adj.factor_mod

        # Factor range from grade
        factor_range = (
            score_result.recommended_factor - 0.03,
            score_result.recommended_factor + 0.03,
        )
        if hasattr(score_result, "_factor_range"):
            factor_range = score_result._factor_range

        holdback = _holdback_pct(score_result.letter_grade)
        max_adv = float(score_result.max_advance)
        payment = _payment_structure(max_adv)

        blockers: list = []
        warnings: list = list(score_result.warnings) if score_result.warnings else []
        if score_result.pre_check and not score_result.pre_check.passed:
            blockers = list(score_result.pre_check.blockers)

        return RiskScoredPricing(
            # PRIMARY
            risk_score=round(score_result.total_score, 2),
            letter_grade=score_result.letter_grade,
            risk_tier=score_result.tier,
            is_approvable=score_result.is_approvable,
            score_breakdown=dict(score_result.component_scores),
            # Industry
            industry=industry_key,
            industry_tier=industry_tier,
            industry_tier_label=industry_tier_label,
            industry_note=industry_note,
            score_adjustment=score_adj,
            factor_mod=factor_mod,
            # Pricing
            recommended_factor=round(score_result.recommended_factor, 4),
            factor_range=factor_range,
            max_advance=max_adv,
            max_advance_pct=score_result.max_advance_pct,
            term_months_range=tuple(score_result.term_months_range),
            holdback_pct=holdback,
            payment_structure=payment,
            # Flags
            warnings=warnings,
            blockers=blockers,
        )

    def score_and_price(
        self,
        industry: str = "",
        fico_score: int = 0,
        time_in_business_months: int = 0,
        monthly_true_revenue: float = 0.0,
        average_daily_balance: float = 0.0,
        nsf_count_90d: int = 0,
        negative_days_90d: int = 0,
        deposit_variance: float = 0.0,
        total_deposits_90d: float = 0.0,
        total_withdrawals_90d: float = 0.0,
        cash_flow_margin: Optional[float] = None,
        position_count: int = 0,
        monthly_merchant_volume: float = 0.0,
        merchant_tenure_months: int = 0,
        requested_amount: float = 0.0,
    ) -> RiskScoredPricing:
        """
        Run full scoring + pricing from raw deal inputs.

        Internally calls RBFScoringModel from rbf-scoring-toolkit, then
        builds a RiskScoredPricing with score as primary output.

        Args:
            industry: Industry key (e.g. "restaurant", "medical_practice")
            fico_score: Self-reported FICO
            time_in_business_months: TIB in months
            monthly_true_revenue: Average monthly true revenue
            average_daily_balance: ADB (90 days)
            nsf_count_90d: NSF count in 90 days
            negative_days_90d: Negative balance days in 90 days
            deposit_variance: Deposit consistency coefficient of variation
            total_deposits_90d: Total deposits over 90 days
            total_withdrawals_90d: Total withdrawals over 90 days
            cash_flow_margin: CFCR (calculated if not provided)
            position_count: Existing MCA positions
            monthly_merchant_volume: Card processing volume
            merchant_tenure_months: Time with processor
            requested_amount: Funding amount requested

        Returns:
            RiskScoredPricing — risk score is primary output
        """
        from scoring.rbf_scorecard import RBFScoringModel

        model = RBFScoringModel()

        model.set_application(
            industry=industry,
            fico_score=fico_score,
            time_in_business_months=time_in_business_months,
            monthly_merchant_volume=monthly_merchant_volume,
            merchant_tenure_months=merchant_tenure_months,
            requested_amount=requested_amount,
        )

        mca_positions = ["position"] * position_count  # placeholder list
        model.set_bank_analytics(
            monthly_true_revenue=monthly_true_revenue,
            average_daily_balance=average_daily_balance,
            nsf_count_90d=nsf_count_90d,
            negative_days_90d=negative_days_90d,
            deposit_variance=deposit_variance,
            total_deposits_90d=total_deposits_90d,
            total_withdrawals_90d=total_withdrawals_90d,
            cash_flow_margin=cash_flow_margin,
            mca_positions=mca_positions,
        )

        score_result = model.score(requested_amount=requested_amount)
        # Stash industry on metadata for from_score_result to read
        score_result.metadata["industry"] = industry

        return self.from_score_result(score_result)
