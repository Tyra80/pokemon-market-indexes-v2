# 🎴 Pokemon Market Indexes v2

Système automatisé de calcul d'indices de marché pour les cartes et produits scellés Pokémon TCG.

## 📊 Indices calculés

| Index | Description | Univers |
|-------|-------------|---------|
| **RARE_100** | Top 100 cartes rares | Cartes rarity ≥ Rare |
| **RARE_500** | Top 500 cartes rares | Cartes rarity ≥ Rare |
| **RARE_ALL** | Toutes cartes rares liquides | Cartes rarity ≥ Rare |
| **SEALED_100** | Top 100 produits scellés | Booster boxes, ETB, etc. |
| **SEALED_500** | Top 500 produits scellés | Booster boxes, ETB, etc. |

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ PokemonPrice    │────▶│    Supabase     │────▶│  Index Values   │
│ Tracker API     │     │   (PostgreSQL)  │     │  (Weekly)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       │
┌───────▼───────┐       ┌───────▼───────┐
│ Frankfurter   │       │ GitHub Actions │
│ (FX Rates)    │       │ (Automation)   │
└───────────────┘       └───────────────┘
```

## 📁 Structure du projet

```
pokemon-market-indexes-v2/
├── .github/workflows/     # Automatisation GitHub Actions
│   ├── daily_fx.yml
│   ├── daily_prices.yml
│   ├── weekly_index.yml
│   └── weekly_cards_update.yml
├── config/                # Configuration
│   └── settings.py
├── docs/                  # Documentation
│   ├── METHODOLOGY.md
│   ├── DATABASE.md
│   └── SETUP.md
├── scripts/               # Scripts Python
│   ├── fetch_fx_rates.py
│   ├── fetch_cards.py
│   ├── fetch_prices.py
│   ├── calculate_index.py
│   └── utils.py
├── sql/                   # Schémas SQL
│   └── 001_schema.sql
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### 1. Prérequis

- Python 3.11+
- Compte Supabase (gratuit)
- Clé API PokemonPriceTracker (Business plan)
- Compte GitHub

### 2. Installation

```bash
# Clone le repo
git clone https://github.com/YOUR_USERNAME/pokemon-market-indexes.git
cd pokemon-market-indexes

# Crée l'environnement virtuel
python -m venv venv
venv\Scripts\activate  # Windows

# Installe les dépendances
pip install -r requirements.txt

# Configure les variables d'environnement
cp .env.example .env
# Édite .env avec tes credentials
```

### 3. Setup base de données

1. Crée un projet Supabase
2. Exécute `sql/001_schema.sql` dans l'éditeur SQL
3. Configure les secrets GitHub

### 4. Premier run

```bash
# 1. Charge les taux de change
python scripts/fetch_fx_rates.py

# 2. Charge les cartes (~ 30 min)
python scripts/fetch_cards.py

# 3. Charge les prix (~ 45 min)
python scripts/fetch_prices.py

# 4. Calcule les indices
python scripts/calculate_index.py
```

## 📅 Automatisation

| Workflow | Fréquence | Heure (UTC) |
|----------|-----------|-------------|
| FX Rates | Quotidien | 16:00 |
| Prices | Quotidien | 06:00 |
| Index Calculation | Hebdo (dimanche) | 00:00 |
| Cards Update | Hebdo (dimanche) | 03:00 |

## 💰 Coûts mensuels

| Service | Coût |
|---------|------|
| Supabase | Gratuit |
| GitHub Actions | Gratuit |
| PokemonPriceTracker API | $99/mois |
| **Total** | **~$99/mois** |

## 📖 Documentation

- [Méthodologie complète](docs/METHODOLOGY.md)
- [Schéma base de données](docs/DATABASE.md)
- [Guide de setup](docs/SETUP.md)

## 📄 License

MIT License - Voir LICENSE
