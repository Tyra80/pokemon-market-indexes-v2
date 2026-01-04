# 📊 Base de Données - Pokemon Market Indexes v2

Documentation du schéma de base de données.

---

## Vue d'ensemble

```
┌─────────────┐     ┌─────────────────────┐     ┌───────────────────┐
│    sets     │────▶│       cards         │────▶│  card_prices_daily│
└─────────────┘     └─────────────────────┘     └───────────────────┘
       │                                                  │
       │            ┌─────────────────────┐               │
       └───────────▶│  sealed_products    │               │
                    └─────────────────────┘               │
                              │                           │
                    ┌─────────▼─────────┐                 │
                    │sealed_prices_daily│                 │
                    └───────────────────┘                 │
                                                          │
┌─────────────────┐                          ┌────────────▼────────┐
│ fx_rates_daily  │                          │constituents_monthly │
└─────────────────┘                          └─────────────────────┘
                                                          │
                                             ┌────────────▼────────┐
                                             │index_values_weekly  │
                                             └─────────────────────┘

┌─────────────────┐
│    run_logs     │  (monitoring)
└─────────────────┘
```

---

## Tables de référentiel (statiques)

### `sets` - Extensions Pokémon

| Colonne | Type | Description |
|---------|------|-------------|
| `set_id` | TEXT (PK) | Identifiant unique (ex: "sv08") |
| `name` | TEXT | Nom de l'extension |
| `series` | TEXT | Série (ex: "Scarlet & Violet") |
| `release_date` | DATE | Date de sortie |
| `total_cards` | INTEGER | Nombre de cartes dans le set |

### `cards` - Cartes Pokémon

| Colonne | Type | Description |
|---------|------|-------------|
| `card_id` | TEXT (PK) | Identifiant unique |
| `ppt_id` | TEXT | ID PokemonPriceTracker |
| `tcgplayer_id` | TEXT | ID TCGplayer |
| `name` | TEXT | Nom de la carte |
| `set_id` | TEXT (FK) | Référence vers `sets` |
| `card_number` | TEXT | Numéro dans le set |
| `rarity` | TEXT | Rareté |
| `variant` | TEXT | Variante (normal, holo, reverse) |
| `is_eligible` | BOOLEAN | Éligible pour les indices |

### `sealed_products` - Produits scellés

| Colonne | Type | Description |
|---------|------|-------------|
| `product_id` | TEXT (PK) | Identifiant unique |
| `name` | TEXT | Nom du produit |
| `set_id` | TEXT (FK) | Set associé |
| `product_type` | TEXT | Type (Booster Box, ETB, etc.) |
| `release_date` | DATE | Date de sortie |

---

## Tables de données (dynamiques)

### `fx_rates_daily` - Taux de change

| Colonne | Type | Description |
|---------|------|-------------|
| `rate_date` | DATE (PK) | Date du taux |
| `eurusd` | NUMERIC | Taux EUR → USD |
| `source` | TEXT | Source (ecb) |

### `card_prices_daily` - Prix des cartes

| Colonne | Type | Description |
|---------|------|-------------|
| `price_date` | DATE | Date du prix |
| `card_id` | TEXT (FK) | Référence carte |
| **TCGplayer** | | |
| `tcg_market_price` | NUMERIC | Prix marché |
| `tcg_nm_price` | NUMERIC | Prix Near Mint |
| `tcg_nm_listings` | INTEGER | Nb listings NM |
| `tcg_total_listings` | INTEGER | Nb listings total |
| **Cardmarket** | | |
| `cm_trend_price` | NUMERIC | Prix tendance (EUR) |
| `cm_avg7` | NUMERIC | Moyenne 7 jours |
| `cm_avg30` | NUMERIC | Moyenne 30 jours |
| **Calculé** | | |
| `composite_price` | NUMERIC | Prix composite (USD) |
| `liquidity_score_custom` | NUMERIC | Score liquidité 0-1 |

**Clé unique :** `(price_date, card_id)`

### `sealed_prices_daily` - Prix des scellés

| Colonne | Type | Description |
|---------|------|-------------|
| `price_date` | DATE | Date du prix |
| `product_id` | TEXT (FK) | Référence produit |
| `tcg_price` | NUMERIC | Prix TCGplayer (USD) |
| `composite_price` | NUMERIC | = tcg_price (USD seul) |

---

## Tables d'index

### `constituents_monthly` - Composition des indices

| Colonne | Type | Description |
|---------|------|-------------|
| `index_code` | TEXT | Code index (RARE_100, etc.) |
| `month` | DATE | Premier jour du mois |
| `item_type` | TEXT | 'card' ou 'sealed' |
| `item_id` | TEXT | card_id ou product_id |
| `composite_price` | NUMERIC | Prix au moment du calcul |
| `liquidity_score` | NUMERIC | Score liquidité |
| `ranking_score` | NUMERIC | price × liquidity |
| `rank` | INTEGER | Position dans l'index |
| `weight` | NUMERIC | Poids (somme = 1) |
| `is_new` | BOOLEAN | Nouveau ce mois |

### `index_values_weekly` - Valeurs des indices

| Colonne | Type | Description |
|---------|------|-------------|
| `index_code` | TEXT | Code index |
| `week_date` | DATE | Date (dimanche) |
| `index_value` | NUMERIC | Valeur (base 100) |
| `n_constituents` | INTEGER | Nombre de constituants |
| `total_market_cap` | NUMERIC | Cap totale |
| `change_1w` | NUMERIC | Variation 1 semaine (%) |
| `change_1m` | NUMERIC | Variation 1 mois (%) |

---

## Table de monitoring

### `run_logs` - Journal d'exécution

| Colonne | Type | Description |
|---------|------|-------------|
| `run_type` | TEXT | Type de job |
| `started_at` | TIMESTAMP | Début |
| `finished_at` | TIMESTAMP | Fin |
| `status` | TEXT | running/success/failed |
| `records_processed` | INTEGER | Lignes traitées |
| `error_message` | TEXT | Message d'erreur |
| `details` | JSONB | Détails additionnels |

---

## Vues utilitaires

### `v_latest_card_prices`
Derniers prix par carte (évite les jointures complexes).

### `v_current_constituents`
Constituants du mois en cours avec détails.

---

## Index de performance

```sql
-- Recherche par set
CREATE INDEX idx_cards_set ON cards(set_id);

-- Recherche par rareté
CREATE INDEX idx_cards_rarity ON cards(rarity);

-- Recherche de prix par date
CREATE INDEX idx_card_prices_date ON card_prices_daily(price_date);

-- Recherche de prix par carte
CREATE INDEX idx_card_prices_card ON card_prices_daily(card_id);
```

---

## Estimation de volume

| Table | Lignes estimées | Croissance |
|-------|-----------------|------------|
| sets | ~200 | +10/an |
| cards | ~25,000 | +2,000/an |
| fx_rates_daily | ~365/an | +365/an |
| card_prices_daily | ~25,000/jour | +9M/an |
| constituents_monthly | ~1,100/mois | +13,200/an |
| index_values_weekly | ~5/semaine | +260/an |

**Volume total année 1 :** ~50 Mo (bien sous les 500 Mo du free tier Supabase)
