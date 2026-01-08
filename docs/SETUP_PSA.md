# PSA Index Database Schema

Tables additionnelles pour l'index PSA 10.

## Tables SQL

Exécuter dans Supabase SQL Editor :

```sql
-- ============================================================
-- PSA 10 INDEX TABLES
-- ============================================================

-- PSA Cards table (cards eligible for PSA index)
-- Links to main cards table but tracks PSA-specific eligibility
CREATE TABLE IF NOT EXISTS psa_cards (
    card_id TEXT PRIMARY KEY REFERENCES cards(card_id),
    has_psa10_data BOOLEAN DEFAULT FALSE,
    last_psa_fetch TIMESTAMPTZ,
    psa_eligible BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PSA 10 Daily prices table
-- Stores eBay sales data for PSA 10 graded cards
CREATE TABLE IF NOT EXISTS psa10_prices_daily (
    price_date DATE NOT NULL,
    card_id TEXT NOT NULL REFERENCES cards(card_id),

    -- Price metrics (from eBay sales)
    avg_price NUMERIC(10,2),           -- averagePrice
    median_price NUMERIC(10,2),        -- medianPrice
    min_price NUMERIC(10,2),           -- minPrice
    max_price NUMERIC(10,2),           -- maxPrice

    -- Volume metrics
    total_sales INTEGER,               -- count (total sales in period)
    daily_volume_7d NUMERIC(8,4),      -- dailyVolume7Day

    -- Data quality
    confidence TEXT,                   -- 'high', 'medium', 'low'
    days_of_data INTEGER,              -- daysUsed in calculation

    -- Calculated fields
    liquidity_score NUMERIC(6,4),

    -- Metadata
    last_updated_api TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (price_date, card_id)
);

-- PSA Index values (separate from raw card index)
CREATE TABLE IF NOT EXISTS psa_index_values_daily (
    value_date DATE NOT NULL,
    index_code TEXT NOT NULL,          -- 'PSA_100', 'PSA_50'
    index_value NUMERIC(12,4) NOT NULL,
    change_1d NUMERIC(8,4),
    change_1w NUMERIC(8,4),
    change_1m NUMERIC(8,4),
    change_3m NUMERIC(8,4),
    change_ytd NUMERIC(8,4),
    n_constituents INTEGER,
    total_market_cap NUMERIC(16,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (value_date, index_code)
);

-- PSA Monthly constituents
CREATE TABLE IF NOT EXISTS psa_constituents_monthly (
    month DATE NOT NULL,
    index_code TEXT NOT NULL,
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    rank INTEGER,
    weight NUMERIC(8,6),
    psa10_price NUMERIC(10,2),         -- median or avg price used
    liquidity_score NUMERIC(6,4),
    ranking_score NUMERIC(12,4),
    is_new BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (month, index_code, card_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_psa_cards_eligible ON psa_cards(psa_eligible) WHERE psa_eligible = true;
CREATE INDEX IF NOT EXISTS idx_psa10_prices_date ON psa10_prices_daily(price_date);
CREATE INDEX IF NOT EXISTS idx_psa10_prices_card ON psa10_prices_daily(card_id);
CREATE INDEX IF NOT EXISTS idx_psa_index_code ON psa_index_values_daily(index_code);
CREATE INDEX IF NOT EXISTS idx_psa_constituents_month ON psa_constituents_monthly(month);
```

## Différences avec les tables raw

| Aspect | Raw Cards | PSA 10 |
|--------|-----------|--------|
| Source prix | TCGPlayer | eBay (via PPT) |
| Conditions | NM/LP/MP/HP/DMG | PSA 10 uniquement |
| Listings | Oui | Non (ventes uniquement) |
| Volume | Ventes TCGPlayer | Ventes eBay |
| Liquidité | 50/30/20 formula | Basée sur volume eBay |

## Notes

- `psa_cards` fait référence à `cards` pour éviter la duplication des métadonnées
- Les prix PSA 10 sont des prix de vente eBay, pas des listings
- `daily_volume_7d` est calculé par PPT sur 7 jours glissants
- `confidence` indique la fiabilité des données (high = beaucoup de ventes)
