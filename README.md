# 🎴 Pokemon Market Indexes v2

Automated market index calculation system for Pokemon TCG rare cards.

## 📊 Indexes

| Index | Description | Universe |
|-------|-------------|----------|
| **RARE_100** | Top 100 rare cards | Cards with rarity ≥ Rare |
| **RARE_500** | Top 500 rare cards | Cards with rarity ≥ Rare |
| **RARE_5000** | Top 5000 rare cards | Cards with rarity ≥ Rare |

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ PokemonPrice    │────▶│    Supabase     │────▶│  Index Values   │
│ Tracker API     │     │   (PostgreSQL)  │     │  (Daily)        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       │
┌───────▼───────┐       ┌───────▼───────┐
│ Frankfurter   │       │ GitHub Actions │
│ (FX Rates)    │       │ (Automation)   │
└───────────────┘       └───────────────┘
```

## 📁 Project Structure

```
pokemon-market-indexes-v2/
├── .github/workflows/      # GitHub Actions automation
│   ├── daily_fx.yml
│   ├── daily_prices.yml
│   ├── daily_index.yml
│   └── weekly_cards_update.yml
├── config/                 # Configuration
│   └── settings.py
├── docs/                   # Documentation
│   ├── METHODOLOGY.md
│   ├── DATABASE.md
│   └── SETUP.md
├── scripts/                # Python scripts
│   ├── fetch_fx_rates.py
│   ├── fetch_cards.py
│   ├── fetch_prices.py
│   ├── calculate_index.py
│   ├── backfill_index.py
│   └── utils.py
├── sql/                    # SQL schemas
│   ├── 001_schema.sql
│   └── 005_add_daily_volume.sql
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- Supabase account (free tier)
- PokemonPriceTracker API key (Business plan - $99/month)
- GitHub account

### 2. Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/pokemon-market-indexes.git
cd pokemon-market-indexes

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### 3. Database Setup

1. Create a Supabase project
2. Execute `sql/001_schema.sql` in the SQL Editor
3. Execute `sql/005_add_daily_volume.sql` for volume tracking
4. Configure GitHub secrets

### 4. Initial Data Load

```bash
# 1. Load FX rates (~1 min)
python scripts/fetch_fx_rates.py

# 2. Load cards (~30 min)
python scripts/fetch_cards.py

# 3. Load prices with volume (~45 min)
python scripts/fetch_prices.py

# 4. Calculate indexes
python scripts/calculate_index.py --rebalance
```

## 📅 Automation Schedule

| Workflow | Frequency | Time (UTC) |
|----------|-----------|------------|
| FX Rates | Daily | 16:00 |
| Prices | Daily | 06:00 |
| Index Calculation | Daily | 07:00 |
| Cards Update | Weekly (Sunday) | 03:00 |

## 🔬 Key Features

### Smart Liquidity Calculation (B + C + D)

The system uses a sophisticated 3-layer liquidity calculation:

| Method | Usage | Description |
|--------|-------|-------------|
| **B** | Fallback | Listings-based liquidity when no volume data |
| **C** | Primary | Volume-based with 7-day temporal decay |
| **D** | Rebalancing | 30-day average volume for eligibility |

### Volume Decay Weights (Method C)

```python
Day 0 (today):     1.00
Day 1 (yesterday): 0.70
Day 2:             0.50
Day 3:             0.35
Day 4:             0.25
Day 5:             0.15
Day 6:             0.10
```

### Index Calculation (Laspeyres Chain-Linking)

```
Index_t = Index_{t-1} × Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)
```

## 💰 Monthly Costs

| Service | Cost |
|---------|------|
| Supabase | Free |
| GitHub Actions | Free |
| PokemonPriceTracker API | $99/month |
| **Total** | **~$99/month** |

## 📖 Documentation

- [Complete Methodology](docs/METHODOLOGY.md)
- [Database Schema](docs/DATABASE.md)
- [Setup Guide](docs/SETUP.md)

## 📊 Current Data

As of January 2026:
- **Cards tracked**: ~26,000
- **Rare cards (≥ Rare)**: ~13,000
- **Daily prices**: ~9,500 per day
- **Historical data**: 30+ days

## 📄 License

MIT License - See LICENSE
