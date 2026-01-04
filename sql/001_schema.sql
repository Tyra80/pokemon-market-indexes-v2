-- ============================================================
-- Pokemon Market Indexes v2 - Database Schema
-- ============================================================
-- Exécuter ce script dans Supabase SQL Editor
-- ============================================================

-- ============================================================
-- 1. TABLE: sets (Référentiel des extensions)
-- ============================================================
CREATE TABLE sets (
    set_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    release_date DATE,
    total_cards INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE sets IS 'Référentiel des extensions Pokémon TCG';

-- ============================================================
-- 2. TABLE: cards (Référentiel des cartes)
-- ============================================================
CREATE TABLE cards (
    card_id TEXT PRIMARY KEY,              -- Ex: "base1-4" ou "base1-4-holo"
    ppt_id TEXT,                           -- ID PokemonPriceTracker
    tcgplayer_id TEXT,                     -- ID TCGplayer
    name TEXT NOT NULL,
    set_id TEXT REFERENCES sets(set_id),
    card_number TEXT,
    rarity TEXT,
    variant TEXT DEFAULT 'normal',         -- normal, holo, reverse, etc.
    card_type TEXT,                        -- Pokemon, Trainer, Energy
    hp INTEGER,
    artist TEXT,
    release_date DATE,
    is_eligible BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cards_set ON cards(set_id);
CREATE INDEX idx_cards_rarity ON cards(rarity);
CREATE INDEX idx_cards_eligible ON cards(is_eligible);

COMMENT ON TABLE cards IS 'Référentiel des cartes Pokémon (une ligne par variante)';

-- ============================================================
-- 3. TABLE: sealed_products (Produits scellés)
-- ============================================================
CREATE TABLE sealed_products (
    product_id TEXT PRIMARY KEY,
    ppt_id TEXT,
    tcgplayer_id TEXT,
    name TEXT NOT NULL,
    set_id TEXT REFERENCES sets(set_id),
    product_type TEXT,                     -- Booster Box, ETB, Bundle, etc.
    release_date DATE,
    is_eligible BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sealed_set ON sealed_products(set_id);
CREATE INDEX idx_sealed_type ON sealed_products(product_type);
CREATE INDEX idx_sealed_eligible ON sealed_products(is_eligible);

COMMENT ON TABLE sealed_products IS 'Référentiel des produits scellés';

-- ============================================================
-- 4. TABLE: fx_rates_daily (Taux de change EUR/USD)
-- ============================================================
CREATE TABLE fx_rates_daily (
    rate_date DATE PRIMARY KEY,
    eurusd NUMERIC(10, 6) NOT NULL,
    source TEXT DEFAULT 'ecb',
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE fx_rates_daily IS 'Taux de change quotidiens EUR/USD (source BCE)';

-- ============================================================
-- 5. TABLE: card_prices_daily (Prix des cartes)
-- ============================================================
CREATE TABLE card_prices_daily (
    id BIGSERIAL PRIMARY KEY,
    price_date DATE NOT NULL,
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    
    -- TCGplayer (USD)
    tcg_market_price NUMERIC(12, 2),
    tcg_low_price NUMERIC(12, 2),
    tcg_mid_price NUMERIC(12, 2),
    tcg_high_price NUMERIC(12, 2),
    
    -- TCGplayer par condition (Near Mint focus)
    tcg_nm_price NUMERIC(12, 2),
    tcg_nm_listings INTEGER,
    tcg_lp_price NUMERIC(12, 2),
    tcg_lp_listings INTEGER,
    tcg_total_listings INTEGER,
    
    -- Cardmarket (EUR)
    cm_trend_price NUMERIC(12, 2),
    cm_avg_price NUMERIC(12, 2),
    cm_low_price NUMERIC(12, 2),
    cm_avg7 NUMERIC(12, 2),
    cm_avg30 NUMERIC(12, 2),
    
    -- Prix composite calculé (USD)
    composite_price NUMERIC(12, 2),
    
    -- Liquidité
    liquidity_score_api NUMERIC(5, 2),     -- Score API PokemonPriceTracker (si dispo)
    liquidity_score_custom NUMERIC(5, 2),  -- Notre score calculé
    
    -- Métadonnées
    source_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(price_date, card_id)
);

CREATE INDEX idx_card_prices_date ON card_prices_daily(price_date);
CREATE INDEX idx_card_prices_card ON card_prices_daily(card_id);
CREATE INDEX idx_card_prices_composite ON card_prices_daily(composite_price);

COMMENT ON TABLE card_prices_daily IS 'Prix quotidiens des cartes avec tous les détails';

-- ============================================================
-- 6. TABLE: sealed_prices_daily (Prix des produits scellés)
-- ============================================================
CREATE TABLE sealed_prices_daily (
    id BIGSERIAL PRIMARY KEY,
    price_date DATE NOT NULL,
    product_id TEXT NOT NULL REFERENCES sealed_products(product_id),
    
    -- TCGplayer (USD) - Source principale pour sealed
    tcg_price NUMERIC(12, 2),
    tcg_low_price NUMERIC(12, 2),
    tcg_high_price NUMERIC(12, 2),
    
    -- Prix composite = tcg_price (USD seul pour sealed)
    composite_price NUMERIC(12, 2),
    
    -- Métadonnées
    source_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(price_date, product_id)
);

CREATE INDEX idx_sealed_prices_date ON sealed_prices_daily(price_date);
CREATE INDEX idx_sealed_prices_product ON sealed_prices_daily(product_id);

COMMENT ON TABLE sealed_prices_daily IS 'Prix quotidiens des produits scellés (USD)';

-- ============================================================
-- 7. TABLE: constituents_monthly (Composition des indices)
-- ============================================================
CREATE TABLE constituents_monthly (
    id BIGSERIAL PRIMARY KEY,
    index_code TEXT NOT NULL,              -- RARE_100, RARE_500, RARE_ALL, SEALED_100, SEALED_500
    month DATE NOT NULL,                   -- Premier jour du mois
    item_type TEXT NOT NULL,               -- 'card' ou 'sealed'
    item_id TEXT NOT NULL,                 -- card_id ou product_id
    
    -- Scores
    composite_price NUMERIC(12, 2),
    liquidity_score NUMERIC(5, 2),
    ranking_score NUMERIC(16, 4),          -- price × liquidity
    
    -- Position dans l'index
    rank INTEGER,
    weight NUMERIC(10, 6),                 -- Poids dans l'index
    
    -- Flags
    is_new BOOLEAN DEFAULT false,          -- Nouveau dans l'index ce mois
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(index_code, month, item_id)
);

CREATE INDEX idx_constituents_index ON constituents_monthly(index_code);
CREATE INDEX idx_constituents_month ON constituents_monthly(month);
CREATE INDEX idx_constituents_rank ON constituents_monthly(rank);

COMMENT ON TABLE constituents_monthly IS 'Composition mensuelle des indices';

-- ============================================================
-- 8. TABLE: index_values_weekly (Valeurs des indices)
-- ============================================================
CREATE TABLE index_values_weekly (
    id BIGSERIAL PRIMARY KEY,
    index_code TEXT NOT NULL,
    week_date DATE NOT NULL,               -- Date du dimanche
    
    -- Valeur de l'index
    index_value NUMERIC(12, 4) NOT NULL,   -- Base 100 à l'inception
    
    -- Statistiques
    n_constituents INTEGER,
    total_market_cap NUMERIC(16, 2),
    
    -- Variations
    change_1w NUMERIC(8, 4),               -- % change vs semaine précédente
    change_1m NUMERIC(8, 4),               -- % change vs mois précédent
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(index_code, week_date)
);

CREATE INDEX idx_index_values_code ON index_values_weekly(index_code);
CREATE INDEX idx_index_values_date ON index_values_weekly(week_date);

COMMENT ON TABLE index_values_weekly IS 'Valeurs hebdomadaires des indices';

-- ============================================================
-- 9. TABLE: run_logs (Journal d'exécution)
-- ============================================================
CREATE TABLE run_logs (
    id BIGSERIAL PRIMARY KEY,
    run_type TEXT NOT NULL,                -- fetch_fx, fetch_cards, fetch_prices, calculate_index
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',         -- running, success, failed
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    details JSONB
);

CREATE INDEX idx_run_logs_type ON run_logs(run_type);
CREATE INDEX idx_run_logs_status ON run_logs(status);

COMMENT ON TABLE run_logs IS 'Journal des exécutions pour monitoring';

-- ============================================================
-- 10. VIEWS (Vues utilitaires)
-- ============================================================

-- Vue: Derniers prix par carte
CREATE OR REPLACE VIEW v_latest_card_prices AS
SELECT DISTINCT ON (card_id)
    card_id,
    price_date,
    tcg_market_price,
    tcg_nm_price,
    tcg_nm_listings,
    cm_trend_price,
    cm_avg7,
    composite_price,
    liquidity_score_custom
FROM card_prices_daily
ORDER BY card_id, price_date DESC;

-- Vue: Constituants actuels avec détails
CREATE OR REPLACE VIEW v_current_constituents AS
SELECT 
    c.index_code,
    c.month,
    c.item_type,
    c.item_id,
    c.rank,
    c.weight,
    c.composite_price,
    c.liquidity_score,
    c.ranking_score,
    CASE 
        WHEN c.item_type = 'card' THEN cards.name
        WHEN c.item_type = 'sealed' THEN sp.name
    END as item_name,
    CASE 
        WHEN c.item_type = 'card' THEN cards.set_id
        WHEN c.item_type = 'sealed' THEN sp.set_id
    END as set_id
FROM constituents_monthly c
LEFT JOIN cards ON c.item_type = 'card' AND c.item_id = cards.card_id
LEFT JOIN sealed_products sp ON c.item_type = 'sealed' AND c.item_id = sp.product_id
WHERE c.month = (SELECT MAX(month) FROM constituents_monthly WHERE index_code = c.index_code);

-- ============================================================
-- 11. Vérification finale
-- ============================================================
SELECT 'Schema v2 créé avec succès!' as status,
       (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public') as tables_count;
