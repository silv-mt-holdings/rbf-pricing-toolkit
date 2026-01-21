# rbf-pricing-toolkit

RBF pricing toolkit - Factor rate recommendations, advance calculations, term suggestions, and deal tier classification.

## Features

- Factor rate recommendation (1.10 - 1.65)
- Max advance calculation (% of monthly revenue)
- Term length recommendation (3-18 months)
- Deal tier classification (Micro/Small/Mid/Large/Jumbo)
- Holdback percentage calculation
- Payment structure recommendation (daily/weekly)

## Installation

```bash
pip install git+https://github.com/silv-mt-holdings/rbf-pricing-toolkit.git
```

## Quick Start

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
