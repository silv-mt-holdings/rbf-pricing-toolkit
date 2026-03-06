# rbf-pricing-toolkit

RBF pricing toolkit - Factor rate recommendations, advance calculations, term suggestions, and deal tier classification — with industry risk adjustment from [rbf-risk-engine](https://github.com/silv-mt-holdings/-RBF-Risk-Engine).

## Features

- Factor rate recommendation (1.10 - 1.65)
- Max advance calculation (% of monthly revenue)
- Term length recommendation (3-18 months)
- Deal tier classification (Micro/Small/Mid/Large/Jumbo)
- Holdback percentage calculation
- Payment structure recommendation (daily/weekly)
- **Industry risk adjustment** — applies per-industry `factor_mod` and tier-based advance caps from `industry_risk_db`

## Installation

```bash
pip install git+https://github.com/silv-mt-holdings/rbf-pricing-toolkit.git
```

## Quick Start

### Base pricing (grade only)

```python
from pricing.factor_calculator import PricingCalculator

pricer = PricingCalculator()
pricing = pricer.calculate(
    grade="A",
    monthly_revenue=50000
)

print(f"Recommended Factor: {pricing.recommended_factor}")
print(f"Max Advance: ${pricing.max_advance:,.2f}")
print(f"Term: {pricing.term_months_range[0]}-{pricing.term_months_range[1]} months")
```

### Industry-adjusted pricing

```python
from pricing.factor_calculator import PricingCalculator

pricer = PricingCalculator()
pricing, industry_adj = pricer.calculate_with_industry(
    grade="B",
    monthly_revenue=80000,
    industry="restaurant",
)

print(f"Adjusted Factor:  {pricing.recommended_factor}")   # Base + industry factor_mod
print(f"Max Advance:      ${pricing.max_advance:,.2f}")     # Reduced by tier cap
print(f"Industry Tier:    {pricing.industry_tier} — {industry_adj.tier_label}")
print(f"Note:             {industry_adj.note}")
```

### How industry data integrates with pricing

| Source | Field | Effect |
|--------|-------|--------|
| `industry_risk_db.json` | `factor_mod` | Added to base factor rate (e.g. +0.08 for restaurant) |
| `industry_risk_db.json` | `tier` | Controls advance cap: T1=100%, T2=95%, T3=85%, T4=70%, T5=50% |
| `industry_risk_db.json` | `adjustment` | Score delta — used upstream in rbf-risk-engine grading |

### Supported industries

Industry keys from `rbf-risk-engine/data/industry_risk_db.json` (46 industries across 5 tiers):

- **Tier 1 (Preferred):** `medical_practice`, `dental`, `healthcare`, `saas`, `legal_services`, `it_services`, ...
- **Tier 2 (Standard):** `manufacturing`, `wholesale`, `ecommerce`, `hvac`, `salon_spa`, ...
- **Tier 3 (Elevated):** `restaurant`, `retail`, `bar_nightclub`, `staffing`, `landscaping`, ...
- **Tier 4 (High Risk):** `trucking`, `construction`, `used_cars`, `auto_dealer`, `travel_agency`, ...
- **Tier 5 (Specialty):** `cannabis`, `gambling`, `crypto`, `check_cashing`, `adult_entertainment`, ...

