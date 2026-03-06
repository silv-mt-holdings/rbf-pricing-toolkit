"""
Industry Risk Adjuster

Loads industry_risk_db from rbf-risk-engine and applies per-industry
factor_mod and tier constraints to a base PricingRecommendation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from typing import Optional

from pricing.factor_calculator import PricingRecommendation


# Path to industry_risk_db — supports local dev (sibling clone) and
# installed environments where the file is bundled under data/.
_HERE = os.path.dirname(__file__)
_INDUSTRY_DB_SEARCH = [
    # Bundled copy in this repo
    os.path.join(_HERE, "..", "data", "industry_risk_db.json"),
    # Sibling clone of rbf-risk-engine
    os.path.join(_HERE, "..", "..", "-RBF-Risk-Engine", "data", "industry_risk_db.json"),
    os.path.join(_HERE, "..", "..", "rbf-risk-engine", "data", "industry_risk_db.json"),
]


def _load_industry_db() -> dict:
    for path in _INDUSTRY_DB_SEARCH:
        resolved = os.path.normpath(path)
        if os.path.exists(resolved):
            with open(resolved, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "industry_risk_db.json not found. "
        "Copy it to data/industry_risk_db.json or place the rbf-risk-engine "
        "repo as a sibling directory."
    )


@dataclass
class IndustryAdjustment:
    """Resolved industry risk profile"""
    industry: str
    tier: int
    tier_label: str
    factor_mod: float
    score_adjustment: int
    note: str


# Tier labels matching industry_risk_db._tiers
_TIER_LABELS = {
    1: "Preferred (Low Risk)",
    2: "Standard (Average Risk)",
    3: "Elevated (Above Average Risk)",
    4: "High Risk",
    5: "Specialty / Extreme Risk",
}

# Max advance multiplier reduction by tier (applied on top of grade-based advance)
_TIER_ADVANCE_CAP: dict[int, float] = {
    1: 1.00,   # No reduction
    2: 0.95,   # 5% haircut
    3: 0.85,   # 15% haircut
    4: 0.70,   # 30% haircut
    5: 0.50,   # 50% haircut — specialty only
}


class IndustryAdjuster:
    """
    Applies industry risk data to a base PricingRecommendation.

    Usage::

        adjuster = IndustryAdjuster()
        adjusted = adjuster.apply(base_pricing, industry="restaurant")
    """

    def __init__(self) -> None:
        db = _load_industry_db()
        self._industries: dict = db["industries"]

    def lookup(self, industry: str) -> Optional[IndustryAdjustment]:
        """Return IndustryAdjustment for a given industry key, or None if unknown."""
        key = industry.lower().replace(" ", "_").replace("-", "_")
        entry = self._industries.get(key)
        if entry is None:
            return None
        tier = entry["tier"]
        return IndustryAdjustment(
            industry=key,
            tier=tier,
            tier_label=_TIER_LABELS.get(tier, "Unknown"),
            factor_mod=entry["factor_mod"],
            score_adjustment=entry["adjustment"],
            note=entry["note"],
        )

    def apply(
        self,
        pricing: PricingRecommendation,
        industry: str,
    ) -> tuple[PricingRecommendation, IndustryAdjustment | None]:
        """
        Apply industry risk adjustments to a PricingRecommendation.

        Adjustments applied:
        - ``factor_mod`` added to recommended_factor and both bounds of factor_range
        - Tier-based advance cap reduces max_advance
        - Tier 5 industries are flagged (max_advance set to 0 for decline)

        Args:
            pricing: Base PricingRecommendation from PricingCalculator.
            industry: Industry key (e.g. "restaurant", "medical_practice").

        Returns:
            Tuple of (adjusted PricingRecommendation, IndustryAdjustment or None).
            If industry is unknown, original pricing is returned unchanged with None.
        """
        adj = self.lookup(industry)
        if adj is None:
            return pricing, None

        # Apply factor modifier
        new_factor = round(pricing.recommended_factor + adj.factor_mod, 4)
        new_range = (
            round(pricing.factor_range[0] + adj.factor_mod, 4),
            round(pricing.factor_range[1] + adj.factor_mod, 4),
        )

        # Apply advance cap by tier
        cap = _TIER_ADVANCE_CAP[adj.tier]
        from decimal import Decimal
        new_advance = pricing.max_advance * Decimal(str(cap))

        adjusted = replace(
            pricing,
            recommended_factor=new_factor,
            factor_range=new_range,
            max_advance=new_advance,
        )

        return adjusted, adj

    def list_industries(self, tier: Optional[int] = None) -> list[str]:
        """Return all industry keys, optionally filtered by tier."""
        if tier is None:
            return list(self._industries.keys())
        return [k for k, v in self._industries.items() if v["tier"] == tier]
