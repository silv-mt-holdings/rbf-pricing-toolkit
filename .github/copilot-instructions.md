# RBF Pricing Toolkit - AI Coding Guidelines

## Project Overview

**rbf-pricing-toolkit** is a pure functional library for calculating factor rates, max advance amounts, and term recommendations.

**Core Purpose**: Convert letter grades to pricing (factor, advance %, terms).

**Architecture Pattern**: **Functional Core** (Pure Functions, No I/O)

---

## Functional Core Principles

### ✅ What This Toolkit SHOULD Do
- Accept letter grade and revenue as input
- Calculate factor rates from grade thresholds
- Determine max advance percentages
- Return pricing recommendations

### ❌ What This Toolkit MUST NOT Do
- File I/O operations
- Database connections
- HTTP requests
- State mutations

---

## Architecture

```
rbf-pricing-toolkit/
├── pricing/
│   ├── factor_calculator.py    # Factor rate calculation
│   ├── advance_calculator.py   # Max advance calculation
│   └── term_recommender.py     # Term range recommendation
├── models/
│   └── pricing.py              # PricingResult
├── data/
│   ├── factor_rate_table.json  # Grade-to-factor mapping
│   └── deal_tier_thresholds.json
└── tests/
    └── test_pricing.py
```

---

## Core Models

```python
@dataclass(frozen=True)
class PricingResult:
    letter_grade: str
    recommended_factor: float      # e.g., 1.15
    factor_range: Tuple[float, float]  # e.g., (1.10, 1.18)
    max_advance_pct: float         # e.g., 0.18 (18%)
    max_advance: Decimal           # Dollar amount
    term_months_range: Tuple[int, int]  # e.g., (6, 12)
    deal_tier: str                 # "Micro", "Small", "Mid", "Large", "Jumbo"
```

---

## Key Functional Patterns

### Factor Calculation

```python
# data/factor_rate_table.json
{
  "A+": {"factor_min": 1.10, "factor_max": 1.15, "recommended": 1.12, "max_advance_pct": 0.20},
  "A": {"factor_min": 1.12, "factor_max": 1.18, "recommended": 1.15, "max_advance_pct": 0.18},
  "A-": {"factor_min": 1.15, "factor_max": 1.20, "recommended": 1.17, "max_advance_pct": 0.16},
  // ... 13 grades
}

def calculate_pricing(
    letter_grade: str,
    monthly_revenue: Decimal
) -> PricingResult:
    """
    Calculate pricing based on letter grade.

    Args:
        letter_grade: Letter grade from scoring toolkit
        monthly_revenue: Monthly true revenue

    Returns:
        Complete pricing recommendation
    """
    pricing_table = load_pricing_table()
    grade_pricing = pricing_table[letter_grade]

    max_advance = monthly_revenue * Decimal(str(grade_pricing['max_advance_pct']))

    return PricingResult(
        letter_grade=letter_grade,
        recommended_factor=grade_pricing['recommended'],
        factor_range=(grade_pricing['factor_min'], grade_pricing['factor_max']),
        max_advance_pct=grade_pricing['max_advance_pct'],
        max_advance=max_advance,
        term_months_range=determine_term_range(letter_grade),
        deal_tier=classify_deal_size(max_advance)
    )
```

---

## Deal Tier Classification

```python
def classify_deal_size(advance_amount: Decimal) -> str:
    """
    Classify deal by size tier.

    Tiers:
    - Micro: < $10k
    - Small: $10k - $50k
    - Mid: $50k - $150k
    - Large: $150k - $500k
    - Jumbo: > $500k
    """
    if advance_amount < 10000:
        return "Micro"
    elif advance_amount < 50000:
        return "Small"
    elif advance_amount < 150000:
        return "Mid"
    elif advance_amount < 500000:
        return "Large"
    else:
        return "Jumbo"
```

---

## Testing

```python
def test_pricing_a_grade():
    pricing = calculate_pricing(
        letter_grade="A",
        monthly_revenue=Decimal("50000")
    )

    assert pricing.recommended_factor == 1.15
    assert pricing.max_advance_pct == 0.18
    assert pricing.max_advance == Decimal("9000")  # 50k * 0.18
    assert pricing.deal_tier == "Micro"

def test_pricing_b_grade():
    pricing = calculate_pricing(
        letter_grade="B+",
        monthly_revenue=Decimal("100000")
    )

    assert 1.18 <= pricing.recommended_factor <= 1.25
    assert pricing.max_advance == Decimal("15000")  # 100k * 0.15
    assert pricing.deal_tier == "Small"
```

---

## Integration with Risk-Model-01

```python
# Risk-Model-01/api.py
from pricing.factor_calculator import PricingCalculator

pricer = PricingCalculator()
pricing = pricer.calculate(
    grade=score_result.letter_grade,
    monthly_revenue=cash_flow.monthly_true_revenue
)
```

---

## Version

**v1.0** - Functional Core Extraction (January 2026)

**Author**: IntensiveCapFi / Silv MT Holdings
