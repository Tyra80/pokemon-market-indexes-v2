# 📊 Database Schema - Pokemon Market Indexes v2

Complete database schema documentation.

---

## Overview

```
┌─────────────┐     ┌─────────────────────┐     ┌───────────────────┐
│    sets     │────▶│       cards         │────▶│  card_prices_daily│
└─────────────┘     └─────────────────────┘     └───────────────────┘
                                                          │
┌─────────────────┐                          ┌────────────▼────────┐
│ fx_rates_daily  │                          │constituents_monthly │
└─────────────────┘                          └─────────────────────┘
                                                          │
                                             ┌────────────▼────────┐
                                             │ index_values_daily  │
                                             └─────────────────────┘

┌─────────────────┐
│    run_logs     │  (monitoring)
└─────────────────┘
```

---

## Reference Tables (Static)

### `sets` - Pokemon Sets/Expansions

| Column | Type | Description |
|--------|------|-------------|
| `set_id` | TEXT (PK) | Unique identifier (e.g., "sv08") |
| `name` | TEXT | Set name |
| `series` | TEXT | Series (e.g., "Scarlet & Violet") |
| `release_date` | DATE | Release date |
| `total_cards` | INTEGER | Number of cards in set |

### `cards` - Pokemon Cards

| Column | Type | Description |
|--------|------|-------------|
| `card_id` | TEXT (PK) | Unique identifier |
| `ppt_id` | TEXT | PokemonPriceTracker ID |
| `tcgplayer_id` | TEXT | TCGplayer ID |
| `name` | TEXT | Card name |
| `set_id` | TEXT (FK) | Reference to `sets` |
| `card_number` | TEXT | Number in set |
| `rarity` | TEXT | Rarity level |
| `variant` | TEXT | Variant (normal, holo, reverse) |
| `is_eligible` | BOOLEAN | Eligible for indexes |

**Eligible Rarities:** Rare, Rare Holo, Rare Holo EX, Rare Holo GX, Rare Holo V, Rare VMAX, Rare VSTAR, Rare Ultra, Rare Secret, Rare Rainbow, Rare Shiny, Double Rare, Ultra Rare, Illustration Rare, Special Illustration Rare, Hyper Rare, Shiny Rare, Shiny Ultra Rare, ACE SPEC Rare

---

## Data Tables (Dynamic)

### `fx_rates_daily` - Exchange Rates

| Column | Type | Description |
|--------|------|-------------|
| `rate_date` | DATE (PK) | Rate date |
| `eurusd` | NUMERIC | EUR → USD rate |
| `source` | TEXT | Source (ecb) |

### `card_prices_daily` - Card Prices

| Column | Type | Description |
|--------|------|-------------|
| `price_date` | DATE | Price date |
| `card_id` | TEXT (FK) | Card reference |
| **Main Prices** | | |
| `market_price` | NUMERIC | Market price (USD) |
| `low_price` | NUMERIC | Low price |
| `mid_price` | NUMERIC | Mid price |
| `high_price` | NUMERIC | High price |
| **By Condition** | | |
| `nm_price` | NUMERIC | Near Mint price |
| `nm_listings` | INTEGER | NM listings count |
| `lp_price` | NUMERIC | Lightly Played price |
| `lp_listings` | INTEGER | LP listings count |
| `mp_price` | NUMERIC | Moderately Played price |
| `mp_listings` | INTEGER | MP listings count |
| `hp_price` | NUMERIC | Heavily Played price |
| `hp_listings` | INTEGER | HP listings count |
| `dmg_price` | NUMERIC | Damaged price |
| `dmg_listings` | INTEGER | Damaged listings count |
| **Volume (NEW)** | | |
| `daily_volume` | INTEGER | Total sales volume for the day |
| `nm_volume` | INTEGER | Near Mint sales volume |
| `lp_volume` | INTEGER | Lightly Played sales volume |
| `mp_volume` | INTEGER | Moderately Played sales volume |
| `hp_volume` | INTEGER | Heavily Played sales volume |
| `dmg_volume` | INTEGER | Damaged sales volume |
| **Calculated** | | |
| `total_listings` | INTEGER | Total listings count |
| `liquidity_score` | NUMERIC | Liquidity score 0-1 |
| `last_updated_api` | TEXT | Last API update timestamp |

**Primary Key:** `(price_date, card_id)`

---

## Index Tables

### `constituents_monthly` - Index Composition

| Column | Type | Description |
|--------|------|-------------|
| `index_code` | TEXT | Index code (RARE_100, etc.) |
| `month` | DATE | First day of month |
| `item_type` | TEXT | 'card' |
| `item_id` | TEXT | card_id |
| `composite_price` | NUMERIC | Price at calculation time |
| `liquidity_score` | NUMERIC | Liquidity score |
| `ranking_score` | NUMERIC | price × liquidity |
| `rank` | INTEGER | Position in index |
| `weight` | NUMERIC | Weight (sum = 1) |
| `is_new` | BOOLEAN | New this month |

### `index_values_daily` - Daily Index Values

| Column | Type | Description |
|--------|------|-------------|
| `index_code` | TEXT | Index code |
| `value_date` | DATE | Calculation date |
| `index_value` | NUMERIC | Value (base 100) |
| `n_constituents` | INTEGER | Number of constituents |
| `total_market_cap` | NUMERIC | Total market cap |
| `change_1d` | NUMERIC | 1-day change (%) |
| `change_1w` | NUMERIC | 1-week change (%) |
| `change_1m` | NUMERIC | 1-month change (%) |

---

## Monitoring Table

### `run_logs` - Execution Log

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL (PK) | Auto-increment ID |
| `run_type` | TEXT | Job type |
| `started_at` | TIMESTAMP | Start time |
| `finished_at` | TIMESTAMP | End time |
| `status` | TEXT | running/success/failed |
| `records_processed` | INTEGER | Rows processed |
| `error_message` | TEXT | Error message |
| `details` | JSONB | Additional details |

---

## Utility Views

### `v_latest_card_prices`
Latest prices per card (avoids complex joins).

### `v_current_constituents`
Current month constituents with details.

---

## Performance Indexes

```sql
-- Search by set
CREATE INDEX idx_cards_set ON cards(set_id);

-- Search by rarity
CREATE INDEX idx_cards_rarity ON cards(rarity);

-- Search by eligibility
CREATE INDEX idx_cards_eligible ON cards(is_eligible) WHERE is_eligible = true;

-- Price search by date
CREATE INDEX idx_card_prices_date ON card_prices_daily(price_date);

-- Price search by card
CREATE INDEX idx_card_prices_card ON card_prices_daily(card_id);

-- Volume index (for liquidity queries)
CREATE INDEX idx_card_prices_volume ON card_prices_daily(daily_volume) 
    WHERE daily_volume IS NOT NULL;
```

---

## Volume Estimates

| Table | Estimated Rows | Growth |
|-------|----------------|--------|
| sets | ~220 | +10/year |
| cards | ~26,000 | +3,000/year |
| fx_rates_daily | ~365/year | +365/year |
| card_prices_daily | ~10,000/day | ~3.6M/year |
| constituents_monthly | ~1,100/month | ~13,200/year |
| index_values_daily | ~3/day | ~1,100/year |

**Year 1 Total Volume:** ~100 MB (well under Supabase free tier 500 MB limit)

---

## SQL Files

| File | Description |
|------|-------------|
| `001_schema.sql` | Main schema creation |
| `005_add_daily_volume.sql` | Add volume columns to card_prices_daily |
