# 🚀 Complete Setup Guide - Pokemon Market Indexes v2

This guide walks you through setting up the entire project **from scratch**.

---

## 📋 Prerequisites

Before starting, make sure you have:

- ✅ **Python 3.11+** installed ([Download](https://www.python.org/downloads/))
- ✅ **VS Code** installed ([Download](https://code.visualstudio.com/))
- ✅ **Git** installed ([Download](https://git-scm.com/downloads))
- ✅ A **GitHub** account ([Sign up](https://github.com/signup))
- ✅ A **Supabase** account ([Sign up](https://supabase.com/))
- ✅ A **PokemonPriceTracker** API key (Business plan - $99/month)

---

## 📁 Step 1: Create Project Folder

### 1.1 Create the folder
```powershell
# Open PowerShell
cd C:\Users\YOUR_USERNAME\Desktop
mkdir pokemon-market-indexes-v2
cd pokemon-market-indexes-v2
```

### 1.2 Open in VS Code
```powershell
code .
```

---

## 🗃️ Step 2: Create Supabase Project

### 2.1 Create a new project
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Click **New Project**
3. Fill in:
   - **Name**: `pokemon-market-indexes-v2`
   - **Database Password**: generate a strong password (save it!)
   - **Region**: `West EU (Ireland)` or closest to you
4. Click **Create new project**
5. ⏳ Wait 2-3 minutes for project creation

### 2.2 Get your credentials
1. Once created, go to **Settings** (gear icon) → **API**
2. Note these values (you'll need them):
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon public** key: `eyJhbGciOiJI...` (long string)

### 2.3 Create the tables
1. In Supabase, go to **SQL Editor** (code icon)
2. Click **New query**
3. Copy-paste the schema below and click **Run** (or Ctrl+Enter)

```sql
-- ============================================================
-- Pokemon Market Indexes v2 - Database Schema
-- ============================================================

-- Sets table
CREATE TABLE IF NOT EXISTS sets (
    set_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    release_date DATE,
    card_count INTEGER,
    tcgdex_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cards table
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    set_id TEXT REFERENCES sets(set_id),
    card_number TEXT,
    rarity TEXT,
    release_date DATE,
    tcgplayer_id TEXT,
    ppt_id TEXT,
    image_url TEXT,
    is_eligible BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily prices table
CREATE TABLE IF NOT EXISTS card_prices_daily (
    price_date DATE NOT NULL,
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    market_price NUMERIC(10,2),
    low_price NUMERIC(10,2),
    mid_price NUMERIC(10,2),
    high_price NUMERIC(10,2),
    nm_price NUMERIC(10,2),
    nm_listings INTEGER,
    lp_price NUMERIC(10,2),
    lp_listings INTEGER,
    mp_price NUMERIC(10,2),
    mp_listings INTEGER,
    hp_price NUMERIC(10,2),
    hp_listings INTEGER,
    dmg_price NUMERIC(10,2),
    dmg_listings INTEGER,
    total_listings INTEGER,
    daily_volume NUMERIC(10,2),
    nm_volume INTEGER,
    lp_volume INTEGER,
    mp_volume INTEGER,
    hp_volume INTEGER,
    dmg_volume INTEGER,
    liquidity_score NUMERIC(6,4),
    last_updated_api TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (price_date, card_id)
);

-- FX rates table
CREATE TABLE IF NOT EXISTS fx_rates_daily (
    rate_date DATE PRIMARY KEY,
    eur_usd NUMERIC(10,6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index values table
CREATE TABLE IF NOT EXISTS index_values_daily (
    value_date DATE NOT NULL,
    index_code TEXT NOT NULL,
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

-- Monthly constituents table
CREATE TABLE IF NOT EXISTS constituents_monthly (
    month DATE NOT NULL,
    index_code TEXT NOT NULL,
    item_id TEXT NOT NULL,
    rank INTEGER,
    weight NUMERIC(8,6),
    composite_price NUMERIC(10,2),
    liquidity_score NUMERIC(6,4),
    liquidity_method TEXT,
    ranking_score NUMERIC(12,4),
    is_new BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (month, index_code, item_id)
);

-- Run logs table
CREATE TABLE IF NOT EXISTS run_logs (
    run_id SERIAL PRIMARY KEY,
    script_name TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',
    records_processed INTEGER,
    error_message TEXT,
    details JSONB
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_cards_rarity ON cards(rarity);
CREATE INDEX IF NOT EXISTS idx_cards_eligible ON cards(is_eligible) WHERE is_eligible = true;
CREATE INDEX IF NOT EXISTS idx_prices_date ON card_prices_daily(price_date);
CREATE INDEX IF NOT EXISTS idx_prices_card ON card_prices_daily(card_id);
CREATE INDEX IF NOT EXISTS idx_index_values_code ON index_values_daily(index_code);
CREATE INDEX IF NOT EXISTS idx_constituents_month ON constituents_monthly(month);
CREATE INDEX IF NOT EXISTS idx_constituents_index ON constituents_monthly(index_code);
```

4. You should see the query execute successfully

**Verification:**
- Go to **Table Editor** (table icon)
- You should see tables: `sets`, `cards`, `card_prices_daily`, etc.

---

## 🐍 Step 3: Configure Python

### 3.1 Create virtual environment
In VS Code terminal (Ctrl+`):
```powershell
python -m venv venv
```

### 3.2 Activate the environment
```powershell
.\venv\Scripts\Activate
```
You should see `(venv)` at the beginning of the line.

### 3.3 Install dependencies
```powershell
pip install -r requirements.txt
```

---

## ⚙️ Step 4: Configure Environment Variables

### 4.1 Create .env file
In VS Code, create a `.env` file at the project root:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# PokemonPriceTracker API
PPT_API_KEY=pokeprice_business_your_api_key

# Discord (optional - for notifications)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
```

**⚠️ IMPORTANT:** Replace values with your actual credentials!

### 4.2 Verify .env is git-ignored
The `.gitignore` file already contains `.env`, so your secrets will never be pushed to GitHub.

---

## 🧪 Step 5: Test Connection

### 5.1 Test Supabase connection
Create a temporary `test_connection.py` file:

```python
from scripts.utils import get_db_client

try:
    client = get_db_client()
    result = client.from_("sets").select("*").limit(1).execute()
    print("✅ Supabase connection OK!")
except Exception as e:
    print(f"❌ Error: {e}")
```

Run:
```powershell
python test_connection.py
```

You should see: `✅ Supabase connection OK!`

Delete the test file afterwards.

---

## 📊 Step 6: Initial Data Load

### 6.1 Load exchange rates (~1 minute)
```powershell
python scripts/fetch_fx_rates.py
```

**Expected result:**
```
✅ 30 rates saved
📊 Latest rates:
   2026-01-03 : 1.0312
   ...
```

### 6.2 Load cards (~30-60 minutes)
```powershell
python scripts/fetch_cards.py
```

**⚠️ This script takes time!** You can let it run and do something else.

**Expected result:**
```
📦 Sets processed  : ~220
🃏 Total cards     : ~26,000
```

### 6.3 Load prices with volume (~45 minutes)
```powershell
python scripts/fetch_prices.py
```

**Expected result:**
```
📊 SUMMARY
   Sets processed       : 213
   Prices fetched       : ~9,500
   Cards with volume    : ~8,000
```

### 6.4 Calculate indexes (~2 minutes)
```powershell
python scripts/calculate_index.py --rebalance
```

**Expected result:**
```
📈 RARE_100 : 100.00 (100 constituents)
📈 RARE_500 : 100.00 (500 constituents)
📈 RARE_ALL : 100.00 (xxxx constituents)
📊 Liquidity: XX volume_decay | XX listings_fallback
```

---

## 📜 Step 7: Backfill Historical Data (Optional)

If you want historical index values:

### 7.1 Backfill historical prices
```powershell
python scripts/fetch_historical_backfill.py --days 30
```

### 7.2 Backfill index values
```powershell
# Dry run first (simulation)
python scripts/backfill_index.py --dry-run

# If OK, run for real
python scripts/backfill_index.py
```

---

## 🐙 Step 8: Configure GitHub

### 8.1 Initialize Git
```powershell
git init
git add .
git commit -m "Initial commit - Pokemon Market Indexes v2"
```

### 8.2 Create GitHub repo
1. Go to [GitHub](https://github.com/new)
2. **Repository name**: `pokemon-market-indexes`
3. **Private** (recommended)
4. Do NOT check "Add README"
5. Click **Create repository**

### 8.3 Connect local repo
GitHub shows the commands. Run:
```powershell
git remote add origin https://github.com/YOUR_USERNAME/pokemon-market-indexes.git
git branch -M main
git push -u origin main
```

### 8.4 Configure GitHub secrets
1. On GitHub, go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:

| Name | Value |
|------|-------|
| `SUPABASE_URL` | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | `eyJhbGciOiJI...` |
| `PPT_API_KEY` | `pokeprice_business_...` |
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` |

---

## 🤖 Step 9: Enable Automation

### 9.1 Verify workflows are present
In your GitHub repo, go to **Actions**. You should see:
- Daily FX Rates
- Daily Prices
- Daily Index Calculation
- Weekly Cards Update
- Keepalive

### 9.2 Test a workflow manually
1. Click on **Daily FX Rates**
2. Click **Run workflow** → **Run workflow**
3. Wait 1-2 minutes
4. ✅ Workflow should turn green

### 9.3 Automatic schedule
Workflows will run automatically:

| Workflow | Frequency | Time (UTC) |
|----------|-----------|------------|
| FX Rates | Daily | 16:00 |
| Prices | Daily | 12:00 |
| Index Calculation | Daily | 13:00 |
| Cards Update | Weekly (Sunday) | 03:00 |
| Keepalive | Every 5 days | 12:00 |

---

## 🔔 Step 10: Configure Discord (Optional)

If you want to receive notifications:

### 10.1 Create a Discord webhook
1. In Discord, go to your server settings
2. **Integrations** → **Webhooks** → **New Webhook**
3. Name it "Pokemon Indexes"
4. Copy the webhook URL

### 10.2 Add to GitHub secrets
- Go back to GitHub → Settings → Secrets
- Add `DISCORD_WEBHOOK_URL` with the copied URL

---

## ✅ Step 11: Final Verification

### Checklist

- [ ] Supabase: All tables created
- [ ] Supabase: fx_rates_daily contains data
- [ ] Supabase: cards contains ~26,000 rows
- [ ] Supabase: card_prices_daily contains data with volume
- [ ] Supabase: index_values_daily contains RARE_100, RARE_500, RARE_ALL
- [ ] GitHub: Repo created and code pushed
- [ ] GitHub: 4 secrets configured
- [ ] GitHub Actions: FX workflow tested manually ✅

---

## 🎉 Setup Complete!

Your system is now operational:

1. **Every day** at 6:00 UTC: Prices are updated (with volume)
2. **Every day** at 7:00 UTC: Index values are calculated
3. **Every day** at 16:00 UTC: FX rates are updated
4. **Every Sunday**: Card database is refreshed

You can view data in:
- **Supabase** → Table Editor → `index_values_daily`
- **GitHub** → Actions (see execution logs)
- **Discord** (if configured) → automatic notifications

---

## 🆘 Troubleshooting

### "Module not found"
```powershell
# Make sure virtual environment is activated
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### "Connection refused" / "Invalid API key"
- Check your credentials in `.env`
- Check GitHub secrets

### "Rate limit exceeded"
- PokemonPriceTracker API has a 200k req/day limit
- Wait until midnight UTC for reset

### GitHub workflow fails
1. Go to Actions → click on failed workflow
2. Click on job → view logs
3. Error is usually visible in last lines

### "liquidity_score is None"
- This is normal for cards without enough data
- Method B (listings fallback) will be used

---

## 📚 Further Reading

- [Methodology Documentation](METHODOLOGY.md)
- [Database Schema](DATABASE.md)
- [PokemonPriceTracker API](https://www.pokemonpricetracker.com/docs)

---

## Scripts Reference

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `fetch_fx_rates.py` | Get EUR/USD exchange rates | Daily |
| `fetch_cards.py` | Update card database | Weekly |
| `fetch_prices.py` | Get daily prices with volume | Daily |
| `calculate_index.py` | Calculate index values | Daily |
| `backfill_index.py` | Backfill historical index values | One-time |
| `fetch_historical_backfill.py` | Backfill historical prices | One-time |
