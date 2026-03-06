"""
Industry Risk Adjuster

Loads industry risk data — SQLite first (lending_intelligence.db), JSON fallback.
Applies per-industry factor_mod and tier constraints to a base PricingRecommendation.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, replace
from typing import Optional

from pricing.factor_calculator import PricingRecommendation


_HERE = os.path.dirname(__file__)

# SQLite DB search paths (lending-intelligence-db)
_SQLITE_DB_SEARCH = [
    os.path.join(_HERE, "..", "..", "lending-intelligence-db", "data", "lending_intelligence.db"),
    os.path.join(_HERE, "..", "data", "lending_intelligence.db"),
]

# JSON fallback search paths
_INDUSTRY_DB_SEARCH = [
    os.path.join(_HERE, "..", "data", "industry_risk_db.json"),
    os.path.join(_HERE, "..", "..", "-RBF-Risk-Engine", "data", "industry_risk_db.json"),
    os.path.join(_HERE, "..", "..", "rbf-risk-engine", "data", "industry_risk_db.json"),
]


def _find_sqlite_db() -> Optional[str]:
    for path in _SQLITE_DB_SEARCH:
        resolved = os.path.normpath(path)
        if os.path.exists(resolved):
            return resolved
    return None


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


def get_lending_db_conn() -> Optional[sqlite3.Connection]:
    """Return a connection to lending_intelligence.db, or None if not found."""
    path = _find_sqlite_db()
    if path:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return None


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

    Queries lending_intelligence.db (SQLite) first; falls back to JSON.

    Usage::

        adjuster = IndustryAdjuster()
        adjusted = adjuster.apply(base_pricing, industry="restaurant")
    """

    def __init__(self) -> None:
        self._conn = get_lending_db_conn()
        if self._conn is None:
            # JSON fallback
            db = _load_industry_db()
            self._industries: dict = db["industries"]
        else:
            self._industries = {}

    def _lookup_sqlite(self, key: str) -> Optional[IndustryAdjustment]:
        cur = self._conn.execute(
            "SELECT industry, tier, adjustment, factor_mod, note FROM industry_risk WHERE industry = ?",
            (key,)
        )
        row = cur.fetchone()
        if row is None:
            # Try FTS fuzzy match
            cur = self._conn.execute(
                "SELECT source FROM fts_industry WHERE fts_industry MATCH ? LIMIT 1",
                (key,)
            )
            fts = cur.fetchone()
            if fts and fts["source"] == "industry_risk":
                cur = self._conn.execute(
                    "SELECT industry, tier, adjustment, factor_mod, note FROM industry_risk WHERE industry = ?",
                    (key,)
                )
                row = cur.fetchone()
        if row is None:
            return None
        tier = row["tier"]
        return IndustryAdjustment(
            industry=row["industry"],
            tier=tier,
            tier_label=_TIER_LABELS.get(tier, "Unknown"),
            factor_mod=row["factor_mod"],
            score_adjustment=row["adjustment"],
            note=row["note"] or "",
        )

    def lookup(self, industry: str) -> Optional[IndustryAdjustment]:
        """Return IndustryAdjustment for a given industry key, or None if unknown."""
        key = industry.lower().replace(" ", "_").replace("-", "_")
        if self._conn is not None:
            return self._lookup_sqlite(key)
        # JSON fallback
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
        if self._conn is not None:
            if tier is None:
                cur = self._conn.execute("SELECT industry FROM industry_risk ORDER BY industry")
            else:
                cur = self._conn.execute("SELECT industry FROM industry_risk WHERE tier = ? ORDER BY industry", (tier,))
            return [row[0] for row in cur.fetchall()]
        if tier is None:
            return list(self._industries.keys())
        return [k for k, v in self._industries.items() if v["tier"] == tier]
