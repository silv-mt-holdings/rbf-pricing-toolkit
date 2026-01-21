"""
RBF Pricing Calculator

Calculates factor rates, advance amounts, and terms based on letter grade.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from decimal import Decimal


# Grade to factor rate mapping
GRADE_TO_FACTOR = {
    "A+": (1.10, 1.12),
    "A": (1.12, 1.15),
    "A-": (1.15, 1.18),
    "B+": (1.18, 1.22),
    "B": (1.22, 1.26),
    "B-": (1.26, 1.30),
    "C+": (1.30, 1.35),
    "C": (1.35, 1.40),
    "C-": (1.40, 1.45),
    "D+": (1.45, 1.50),
    "D": (1.50, 1.55),
    "D-": (1.55, 1.60),
    "F": (1.60, 1.65),
}

# Grade to max advance percentage
GRADE_TO_MAX_ADVANCE_PCT = {
    "A+": 0.18,
    "A": 0.16,
    "A-": 0.14,
    "B+": 0.12,
    "B": 0.10,
    "B-": 0.08,
    "C+": 0.08,
    "C": 0.08,
    "C-": 0.08,
    "D+": 0.06,
    "D": 0.06,
    "D-": 0.06,
    "F": 0.00,  # Not approvable
}

# Deal tier thresholds
DEAL_TIERS = {
    "Micro": (0, 10000),
    "Small": (10000, 50000),
    "Mid": (50000, 150000),
    "Large": (150000, 500000),
    "Jumbo": (500000, float('inf')),
}


@dataclass
class PricingRecommendation:
    """RBF pricing recommendation"""
    letter_grade: str
    recommended_factor: float
    factor_range: Tuple[float, float]
    max_advance: Decimal
    max_advance_pct: float
    term_months_range: Tuple[int, int]
    deal_tier: str
    suggested_holdback_pct: float
    payment_structure: str


class PricingCalculator:
    """
    Calculates RBF pricing based on letter grade.
    """

    def calculate(
        self,
        grade: str,
        monthly_revenue: float
    ) -> PricingRecommendation:
        """
        Calculate pricing recommendation.

        Args:
            grade: Letter grade (A+ through F)
            monthly_revenue: Monthly true revenue

        Returns:
            PricingRecommendation object
        """
        # Get factor range
        factor_range = GRADE_TO_FACTOR.get(grade, (1.60, 1.65))
        recommended_factor = sum(factor_range) / 2  # Midpoint

        # Get max advance percentage
        max_advance_pct = GRADE_TO_MAX_ADVANCE_PCT.get(grade, 0.0)

        # Calculate max advance
        max_advance = Decimal(monthly_revenue * max_advance_pct)

        # Determine deal tier
        deal_tier = self._classify_deal_tier(float(max_advance))

        # Term recommendations based on grade
        if grade.startswith("A"):
            term_range = (9, 12)
        elif grade.startswith("B"):
            term_range = (6, 9)
        elif grade.startswith("C"):
            term_range = (4, 6)
        else:
            term_range = (3, 4)

        # Holdback recommendation
        if grade in ["A+", "A", "A-"]:
            holdback_pct = 0.10
        elif grade in ["B+", "B", "B-"]:
            holdback_pct = 0.12
        elif grade in ["C+", "C", "C-"]:
            holdback_pct = 0.15
        else:
            holdback_pct = 0.18

        # Payment structure
        payment_structure = "daily" if float(max_advance) > 25000 else "weekly"

        return PricingRecommendation(
            letter_grade=grade,
            recommended_factor=recommended_factor,
            factor_range=factor_range,
            max_advance=max_advance,
            max_advance_pct=max_advance_pct,
            term_months_range=term_range,
            deal_tier=deal_tier,
            suggested_holdback_pct=holdback_pct,
            payment_structure=payment_structure
        )

    def _classify_deal_tier(self, advance_amount: float) -> str:
        """Classify deal tier by advance amount"""
        for tier_name, (min_amt, max_amt) in DEAL_TIERS.items():
            if min_amt <= advance_amount < max_amt:
                return tier_name
        return "Micro"
