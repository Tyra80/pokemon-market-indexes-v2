# 📈 Méthodologie - Pokemon Market Indexes v2

Documentation complète de la méthodologie de calcul des indices.

---

## Vue d'ensemble

Les Pokemon Market Indexes sont une famille d'indices conçus pour mesurer la performance du marché des cartes et produits scellés Pokémon TCG.

### Principes fondamentaux

1. **Transparence** - Méthodologie publique et reproductible
2. **Liquidité** - Focus sur les items réellement échangés
3. **Anti-manipulation** - Filtres contre les outliers et le hype court terme
4. **Global** - Prix composite US + EU

---

## Les 5 Indices

| Index | Univers | Taille | Description |
|-------|---------|--------|-------------|
| **RARE_100** | Cartes rares | 100 | Top 100 cartes par capitalisation |
| **RARE_500** | Cartes rares | 500 | Top 500 cartes par capitalisation |
| **RARE_ALL** | Cartes rares | Variable | Toutes les cartes liquides |
| **SEALED_100** | Scellés | 100 | Top 100 produits scellés |
| **SEALED_500** | Scellés | 500 | Top 500 produits scellés |

---

## Sources de données

### Prix

| Source | Marché | Devise | Utilisation |
|--------|--------|--------|-------------|
| TCGplayer | US | USD | Prix Near Mint, listings |
| Cardmarket | EU | EUR | Prix tendance, moyennes |
| eBay | Global | USD | Prix gradés (exclus) |

### Taux de change

- **Source** : BCE via Frankfurter API
- **Fréquence** : Quotidien
- **Conversion** : EUR → USD

---

## Critères d'éligibilité

### Cartes (RARE_100/500/ALL)

| Critère | Valeur |
|---------|--------|
| Rareté minimum | ≥ Rare |
| Maturité | ≥ 60 jours depuis sortie du set |
| Liquidité (entrée) | Score ≥ 0.45 - 0.60 selon index |
| Liquidité (maintien) | Score ≥ 0.35 - 0.50 selon index |
| Prix minimum | ≥ $0.10 |
| Prix maximum | ≤ $100,000 |

### Produits scellés (SEALED_100/500)

| Critère | Valeur |
|---------|--------|
| Types | Booster Box, ETB, Bundle, Collection |
| Maturité | ≥ 90 jours depuis sortie |
| Liquidité | Même seuils que les cartes |

### Exclusions

- ❌ Cartes gradées (PSA, BGS, CGC)
- ❌ Cartes de rareté < Rare (Common, Uncommon)
- ❌ Items sans prix sur au moins un marché
- ❌ Outliers (variation > ±80% hebdo)

---

## Calcul du prix composite

### Cartes

```
Si TCGplayer ET Cardmarket disponibles:
    Composite = 0.50 × TCG_NM_Price + 0.50 × (CM_Trend × FX_Rate)

Si seulement TCGplayer:
    Composite = TCG_NM_Price

Si seulement Cardmarket:
    Composite = CM_Trend × FX_Rate
```

### Produits scellés

```
Composite = TCG_Price  (USD uniquement, pas de données EU)
```

---

## Calcul du score de liquidité

### Signaux utilisés

| Signal | Poids | Source | Description |
|--------|-------|--------|-------------|
| NM Listings | 50% | TCGplayer | Nombre de listings Near Mint |
| Total Listings | 30% | TCGplayer | Profondeur du marché |
| Multi-condition | 20% | TCGplayer | Présence de plusieurs conditions |

### Formule

```python
# Normalisation (0-1)
nm_score = min(nm_listings / 20, 1.0)
total_score = min(total_listings / 50, 1.0)
multi_score = 1.0 if conditions >= 3 else (0.5 if conditions >= 2 else 0.0)

# Score composite
liquidity_score = 0.50 × nm_score + 0.30 × total_score + 0.20 × multi_score
```

### Interprétation

| Score | Interprétation |
|-------|----------------|
| ≥ 0.70 | Très liquide |
| 0.50 - 0.69 | Liquide |
| 0.35 - 0.49 | Borderline |
| < 0.35 | Illiquide |

---

## Calcul du ranking score

Le ranking score détermine la position dans l'index :

```
Ranking_Score = Composite_Price × Liquidity_Score
```

Ce score favorise les items à la fois chers ET liquides.

---

## Calcul des poids

Chaque constituant a un poids proportionnel à son ranking score :

```
Weight_i = Ranking_Score_i / Σ(Ranking_Scores)

Σ(Weights) = 1.0
```

---

## Calcul de la valeur de l'index

### Première valeur

```
Index_Value_0 = 100.0  (base)
```

### Valeurs suivantes (chain-linking)

```
Index_Value_t = Index_Value_{t-1} × (1 + Return_t)

où Return_t = Σ(Weight_i × Return_i)
   Return_i = (Price_i,t - Price_i,t-1) / Price_i,t-1
```

---

## Rebalancement

### Fréquence

- **Calcul de l'index** : Hebdomadaire (dimanche)
- **Rebalancement** : Mensuel (1er du mois)

### Processus de rebalancement

1. Calcul des scores pour toutes les cartes éligibles
2. Tri par ranking score décroissant
3. Sélection du top N (selon index)
4. Calcul des nouveaux poids
5. Chain-linking pour préserver la continuité

### Tolérance de continuité

Pour éviter le turnover excessif :
- **Seuil d'entrée** : Liquidity ≥ 0.60 (RARE_100)
- **Seuil de maintien** : Liquidity ≥ 0.45 (constituants existants)

---

## Détection des outliers

### Règles appliquées

| Règle | Seuil | Action |
|-------|-------|--------|
| Prix trop bas | < $0.10 | Exclusion |
| Prix trop haut | > $100,000 | Exclusion |
| Variation extrême | > ±80% hebdo | Flag / Exclusion |
| Divergence US/EU | > 100% | Investigation |

---

## Gouvernance

### Versioning

- **Méthodologie actuelle** : v2.0
- **Calibration liquidité** : v1.0 (frozen)

### Modifications

- Aucune modification rétroactive des valeurs publiées
- Changements documentés et datés
- Période de notification avant changements majeurs

---

## Limites connues

1. **Liquidité estimée** - Basée sur les listings, pas les ventes réelles
2. **Sealed USD only** - Pas de prix EU pour les produits scellés
3. **Latence** - Prix mis à jour quotidiennement, pas en temps réel
4. **Variants** - Traitement simplifié des variantes holo/reverse

---

## Disclaimer

Les Pokemon Market Indexes sont fournis à titre informatif uniquement. Ils ne constituent pas un conseil d'investissement. Les performances passées ne garantissent pas les résultats futurs.
