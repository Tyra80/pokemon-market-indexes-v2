# Pokemon Market Indexes - Methodology

A comprehensive guide to how we calculate and maintain the Pokemon TCG market indexes.

---

## What Are These Indexes?

Pokemon Market Indexes track the price performance of rare Pokemon Trading Card Game (TCG) cards. Like stock market indexes (S&P 500, NASDAQ), they provide a single number that represents how the overall market is performing.

**Base Value**: 100 (set on December 8th, 2025)

If the index reads **105**, the market has gained 5% since inception.
If it reads **95**, the market has declined 5%.

---

## The Three Indexes

| Index | Cards Tracked | Purpose |
|-------|---------------|---------|
| **RARE_100** | Top 100 | Blue-chip cards - the most valuable and liquid |
| **RARE_500** | Top 500 | Broader market view |
| **RARE_5000** | Top 5000 | Comprehensive market coverage |

---

## How We Select Cards

### 1. Eligibility Requirements

A card must meet ALL of these criteria:

| Requirement | Threshold | Why? |
|-------------|-----------|------|
| Rarity | Rare or higher | Excludes Commons/Uncommons with minimal collector value |
| Minimum price | $0.10 | Filters out bulk cards |
| Maximum price | $100,000 | Excludes extreme outliers |
| Set maturity | 30+ days old | Allows prices to stabilize after release |

### Eligible Rarities

- Standard Rares: Rare, Holo Rare, Shiny Holo Rare
- Ultra/Secret: Ultra Rare, Secret Rare, Hyper Rare
- Illustration: Illustration Rare, Special Illustration Rare, Double Rare
- Special: Amazing Rare, Radiant Rare, ACE SPEC Rare, Prism Rare
- And more (see full list in settings)

### 2. Liquidity Requirements

**Why liquidity matters**: A card that rarely sells can have a misleading price. If only one copy sells per month, that single sale creates noise in the index. We need cards that trade regularly to get reliable price signals.

#### Liquidity Score (0 to 1)

We calculate a liquidity score using actual sales data:

**Primary Method (Volume-Based)**:
- Uses the last 7 days of sales
- Recent sales count more (exponential decay)
- Score = Weighted sales / 50 (capped at 1.0)

```
Day weights: Today=1.0, -1d=0.7, -2d=0.5, -3d=0.35, -4d=0.25, -5d=0.15, -6d=0.10
```

**Fallback Method (Listings-Based)**:
- Used when sales data is unavailable
- Based on number of listings by condition
- Near Mint listings weighted highest

#### Condition Weighting

Sales and listings are weighted by card condition:

| Condition | Weight | Rationale |
|-----------|--------|-----------|
| Near Mint | 1.00 | Reference condition |
| Lightly Played | 0.80 | Minor wear |
| Moderately Played | 0.60 | Visible wear |
| Heavily Played | 0.40 | Significant wear |
| Damaged | 0.20 | Major damage |

#### 30-Day Trading Activity (Method D)

To be included in the index, a card must show **consistent** trading activity:

1. **Average volume** >= 0.5 sales/day (about 15 sales per month)
2. **Trading days** >= 10 days out of 30 with at least one sale

This dual requirement ensures cards aren't just liquid in bursts but trade regularly.

**No minimum liquidity threshold** - The ranking score (price × liquidity) naturally penalizes illiquid cards while allowing high-value cards with moderate liquidity to be included. This better reflects the "TOP 100/500" philosophy.

### 3. Ranking Score

Cards are ranked by:

```
Ranking Score = Price × Liquidity Score
```

This formula favors cards that are both valuable AND liquid. A $1,000 card with 0.8 liquidity (score: 800) ranks higher than a $2,000 card with 0.3 liquidity (score: 600).

---

## How We Calculate Weights

### Liquidity-Adjusted Price-Weighted

Each card's weight in the index is proportional to its **price × liquidity**:

```
Weight_i = (Price_i × Liquidity_i) / Sum(Price × Liquidity for all cards)
```

**Why liquidity-adjusted?**

Standard price-weighting would give expensive but illiquid cards too much influence. A $5,000 card that trades once a month could swing the index based on a single noisy sale. By multiplying by liquidity, we reduce the impact of illiquid cards.

**Example**:

| Card | Price | Liquidity | Adjusted Value | Weight |
|------|-------|-----------|----------------|--------|
| Card A | $1,000 | 0.90 | $900 | 47.4% |
| Card B | $800 | 0.80 | $640 | 33.7% |
| Card C | $500 | 0.72 | $360 | 18.9% |
| **Total** | | | **$1,900** | **100%** |

---

## How We Calculate the Index Value

### Laspeyres Chain-Linking Method

This is the same method used by major financial indexes. It answers: "How much would yesterday's portfolio be worth at today's prices?"

**Formula**:

```
Index_t = Index_{t-1} × (Sum of weighted current prices / Sum of weighted previous prices)
```

Or more precisely:

```
Index_t = Index_{t-1} × [Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)]

Where:
- w_i = weight of card i (fixed during the month)
- P_i,t = price of card i today
- P_i,t-1 = price of card i yesterday
```

**Example**:

If yesterday's index was 100 and the weighted prices increased by 2%:
```
Index_today = 100 × 1.02 = 102
```

### Handling Missing Data

We require **at least 70%** of constituents to have valid prices for the calculation. This prevents a few missing cards from distorting the index.

---

## Rebalancing

### When

- **Monthly**: 3rd of each month (to use 1st of month prices with J-2 strategy)
- Weights are fixed for the entire month

### Why the 3rd?

With the J-2 strategy:
- **1st of month**: We have prices from 2 days ago (still previous month)
- **2nd of month**: We have prices from the last day of previous month
- **3rd of month**: We have prices from the **1st of the new month** → Rebalance!

This ensures the new month's constituents are selected based on the first prices of that month.

### Process

1. Recalculate liquidity scores for all eligible cards
2. Apply 30-day trading activity filter (Method D)
3. Rank by Ranking Score (Price × Liquidity)
4. Select top N cards (100, 500, or all eligible)
5. Calculate new weights
6. Apply chain-linking to maintain continuity

### Why Monthly?

- Too frequent = excessive trading costs if tracking the index
- Too infrequent = stale composition missing market changes
- Monthly balances responsiveness with stability

---

## Data Sources

| Data | Source | Frequency |
|------|--------|-----------|
| Card prices | TCGplayer (via PokemonPriceTracker API) | Daily |
| Sales volume | TCGplayer (via PokemonPriceTracker API) | Daily |
| Card metadata | TCGdex API | On-demand |
| Exchange rates | Frankfurter API (ECB) | Daily |

### Reference Price

We use **Near Mint (NM) price** as the reference. This is the standard condition for collectible cards and provides the most consistent pricing.

---

## Calculation Schedule

### J-2 Strategy (Guaranteed Volume Data)

We use a **J-2 strategy**: prices and volumes are fetched for **2 days ago** to ensure complete sales data.

**Why J-2?**
- TCGplayer consolidates sales at the end of US day (~08:00 UTC next day)
- Using J-2 gives 24-48 hours for volume data to fully consolidate
- This guarantees accurate sales volume for liquidity calculations

**Example**: On January 7th, the index is calculated using January 5th prices.

| Operation | Time (UTC) | Description |
|-----------|------------|-------------|
| Price fetch | 12:00 | Fetch J-2 prices and sales volume |
| Index calculation | 13:00 | Calculate daily index values |
| Rebalancing | 3rd of month | Monthly constituent refresh (uses 1st of month prices) |

**Important**: The index published on any given day reflects prices from **2 days prior**.

---

## Key Dates

- **Inception Date**: December 8th, 2025
- **Base Value**: 100
- **Methodology Version**: 2.0

---

## Summary of Anti-Noise Measures

| Problem | Our Solution |
|---------|--------------|
| Illiquid cards with unreliable prices | Liquidity score threshold + Method D filter |
| Sporadic trading | Require 10+ trading days per month |
| Expensive illiquid cards dominating | Liquidity-Adjusted Price-Weighted |
| Missing price data | 70% minimum match requirement |
| Extreme prices | Min $0.10 / Max $100,000 filters |
| New set volatility | 30-day maturity requirement |

---

## Limitations

1. **US Market Only**: Currently uses TCGplayer data (US). Cardmarket (EU) planned for future.
2. **Daily Updates**: Not real-time; prices are daily closing values.
3. **Volume Coverage**: Not all cards have sales data every day.
4. **Variants**: Holo/reverse variants treated as separate cards.

---

## Disclaimer

Pokemon Market Indexes are provided for informational and educational purposes only. They do not constitute investment advice. Past performance does not guarantee future results. The Pokemon TCG market is volatile and collectibles can lose value.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | Jan 2026 | J-2 strategy for guaranteed volume data, rebalancing moved to 3rd of month |
| 2.0 | Jan 2026 | Liquidity-Adjusted Price-Weighted, Method D double criteria (avg + days), 70% matching threshold |
| 1.0 | Dec 2025 | Initial methodology |
