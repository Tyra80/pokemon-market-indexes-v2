# 📈 Methodology - Pokemon Market Indexes v2

Complete methodology documentation for index calculation.

---

## Overview

Pokemon Market Indexes are a family of indexes designed to measure the performance of the Pokemon TCG rare cards market.

### Core Principles

1. **Transparency** - Public and reproducible methodology
2. **Liquidity** - Focus on items that are actually traded
3. **Anti-manipulation** - Filters against outliers and short-term hype
4. **Real Volume** - Liquidity based on actual sales, not just listings

---

## The 3 Indexes

| Index | Universe | Size | Description |
|-------|----------|------|-------------|
| **RARE_100** | Rare cards | 100 | Top 100 cards by ranking score |
| **RARE_500** | Rare cards | 500 | Top 500 cards by ranking score |
| **RARE_ALL** | Rare cards | Variable | All liquid rare cards |

---

## Data Sources

### Prices

| Source | Market | Currency | Data |
|--------|--------|----------|------|
| TCGplayer (via PokemonPriceTracker) | US | USD | NM price, listings, **sales volume** |

### Exchange Rates

- **Source**: ECB via Frankfurter API
- **Frequency**: Daily
- **Conversion**: EUR → USD (reserved for future Cardmarket integration)

---

## Eligibility Criteria

### Cards (RARE_100/500/ALL)

| Criterion | Value |
|-----------|-------|
| Minimum rarity | ≥ Rare |
| Maturity | ≥ 60 days since set release |
| Liquidity (entry) | Score ≥ 0.40 - 0.60 depending on index |
| Liquidity (maintenance) | Score ≥ 0.30 - 0.45 for existing constituents |
| Minimum price | ≥ $0.10 |
| Maximum price | ≤ $100,000 |

### Eligible Rarities

```
Rare, Rare Holo, Rare Holo EX, Rare Holo GX, Rare Holo V, 
Rare VMAX, Rare VSTAR, Rare Ultra, Rare Secret, Rare Rainbow, 
Rare Shiny, Double Rare, Ultra Rare, Illustration Rare, 
Special Illustration Rare, Hyper Rare, Shiny Rare, 
Shiny Ultra Rare, ACE SPEC Rare
```

### Exclusions

- ❌ Graded cards (PSA, BGS, CGC)
- ❌ Cards with rarity < Rare (Common, Uncommon)
- ❌ Items without price data
- ❌ Outliers (price < $0.10 or > $100,000)

---

## Liquidity Calculation (B + C + D System)

### Overview

The system uses a sophisticated 3-layer approach to calculate liquidity:

| Method | Layer | Usage |
|--------|-------|-------|
| **B** | Fallback | Listings-based when no volume data available |
| **C** | Primary | Volume-based with 7-day temporal decay |
| **D** | Rebalancing | 30-day average volume for monthly eligibility |

### Method B: Listings-Based (Fallback)

Used when volume data is not available:

```python
# Condition weights
CONDITION_WEIGHTS = {
    "Near Mint": 1.0,
    "Lightly Played": 0.8,
    "Moderately Played": 0.6,
    "Heavily Played": 0.4,
    "Damaged": 0.2,
}

# Weighted listings calculation
weighted_listings = (
    nm_listings × 1.0 +
    lp_listings × 0.8 +
    mp_listings × 0.6 +
    hp_listings × 0.4 +
    dmg_listings × 0.2
)

# Score (capped at 1.0)
liquidity_score = min(weighted_listings / 100, 1.0)
```

### Method C: Volume-Based with Temporal Decay (Primary)

Uses actual sales volume with exponential decay:

```python
# Decay weights (more recent = more weight)
VOLUME_DECAY_WEIGHTS = {
    0: 1.00,   # Today
    1: 0.70,   # Yesterday
    2: 0.50,   # 2 days ago
    3: 0.35,   # 3 days ago
    4: 0.25,   # 4 days ago
    5: 0.15,   # 5 days ago
    6: 0.10,   # 6 days ago
}

# Weighted volume calculation
weighted_volume = Σ(volume_day_i × weight_i)

# Normalized by sum of weights used
normalized_volume = weighted_volume / Σ(weights)

# Score (50 sales/day = max score)
liquidity_score = min(normalized_volume / 50, 1.0)
```

### Method D: 30-Day Average Volume (Rebalancing)

Used for monthly rebalancing eligibility:

```python
avg_volume_30d = sum(daily_volumes) / 30

# Minimum threshold for eligibility
MIN_AVG_VOLUME_30D = 0.5  # 0.5 sales/day ≈ 15 sales/month
```

### Smart Liquidity Logic

```
1. If volume history available (≥2 days):
   → Use Method C (volume decay)

2. Otherwise:
   → Use Method B (listings fallback)

3. For rebalancing:
   → Apply Method D filter (30-day avg ≥ 0.5)
```

### Score Interpretation

| Score | Interpretation |
|-------|----------------|
| ≥ 0.70 | Very liquid |
| 0.50 - 0.69 | Liquid |
| 0.35 - 0.49 | Borderline |
| < 0.35 | Illiquid |

---

## Ranking Score

The ranking score determines position in the index:

```
Ranking_Score = Price × Liquidity_Score
```

This score favors items that are both expensive AND liquid.

---

## Weight Calculation

Each constituent has a weight proportional to its price (price-weighted):

```
Weight_i = Price_i / Σ(Prices)

Σ(Weights) = 1.0
```

---

## Index Value Calculation (Laspeyres Chain-Linking)

### Base Value

```
Index_Value_0 = 100.0  (inception)
```

### Subsequent Values

```
Index_Value_t = Index_Value_{t-1} × Ratio_t

where:
  Ratio_t = Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)
  w_i = constituent weight (fixed during period)
  P_i,t = constituent price at time t
```

### Chain-Linking

When rebalancing occurs, the new weights are applied while preserving index continuity through chain-linking.

---

## Rebalancing

### Frequency

- **Index calculation**: Daily
- **Rebalancing**: Monthly (1st of month)

### Rebalancing Process

1. Calculate scores for all eligible cards
2. Apply Method D filter (30-day avg volume ≥ 0.5)
3. Sort by ranking score descending
4. Select top N (based on index)
5. Calculate new weights
6. Chain-link to preserve continuity

### Continuity Tolerance

To avoid excessive turnover:
- **Entry threshold**: Liquidity ≥ 0.60 (RARE_100)
- **Maintenance threshold**: Liquidity ≥ 0.45 (existing constituents)

---

## Outlier Detection

### Rules Applied

| Rule | Threshold | Action |
|------|-----------|--------|
| Price too low | < $0.10 | Exclusion |
| Price too high | > $100,000 | Exclusion |

---

## Calculation Schedule

| Operation | Frequency | Time |
|-----------|-----------|------|
| Price fetch | Daily | 06:00 UTC |
| Index calculation | Daily | 07:00 UTC |
| Rebalancing | Monthly | 1st of month |

---

## Governance

### Versioning

- **Current methodology**: v2.0
- **Liquidity calibration**: v1.0 (frozen)

### Changes

- No retroactive modification of published values
- Changes documented and dated
- Notification period before major changes

---

## Known Limitations

1. **US Market Only** - Currently TCGplayer data only (no Cardmarket/EU)
2. **Volume Data Coverage** - Not all cards have sales volume every day
3. **Latency** - Prices updated daily, not real-time
4. **Variants** - Simplified treatment of holo/reverse variants

---

## Disclaimer

Pokemon Market Indexes are provided for informational purposes only. They do not constitute investment advice. Past performance does not guarantee future results.
