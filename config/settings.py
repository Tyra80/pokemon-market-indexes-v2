"""
Pokemon Market Indexes v2 - Configuration
=========================================
Centralizes all project configuration.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# API Configuration
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

PPT_API_KEY = os.getenv("PPT_API_KEY")
PPT_BASE_URL = "https://www.pokemonpricetracker.com/api"

FRANKFURTER_URL = "https://api.frankfurter.dev/v1"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ============================================================
# Index Configuration
# ============================================================

INDEX_CONFIG = {
    "RARE_100": {
        "type": "card",
        "size": 100,
        "min_rarity": "Rare",
        "liquidity_threshold_entry": 0.60,
        "liquidity_threshold_maintain": 0.45,
        "maturity_days": 60,
    },
    "RARE_500": {
        "type": "card",
        "size": 500,
        "min_rarity": "Rare",
        "liquidity_threshold_entry": 0.45,
        "liquidity_threshold_maintain": 0.35,
        "maturity_days": 60,
    },
    "RARE_ALL": {
        "type": "card",
        "size": None,  # No limit
        "min_rarity": "Rare",
        "liquidity_threshold_entry": 0.50,
        "liquidity_threshold_maintain": 0.50,
        "maturity_days": 60,
    },
}

# ============================================================
# Rarity Configuration
# ============================================================

# Rarities considered as "Rare" or higher
# Based on actual data from PokemonPriceTracker API
RARE_RARITIES = [
    # Standard Rares
    "Rare",                         # 3164 cards
    "Holo Rare",                    # 1845 cards
    "Shiny Holo Rare",              # 246 cards
    
    # Ultra/Secret
    "Ultra Rare",                   # 2433 cards
    "Secret Rare",                  # 631 cards
    "Hyper Rare",                   # 74 cards
    "Mega Hyper Rare",              # 3 cards
    
    # Illustration
    "Illustration Rare",            # 432 cards
    "Special Illustration Rare",    # 181 cards
    "Double Rare",                  # 368 cards
    
    # Shiny
    "Shiny Rare",                   # 120 cards
    "Shiny Ultra Rare",             # 12 cards
    
    # Special
    "Amazing Rare",                 # 9 cards
    "Radiant Rare",                 # 32 cards
    "Prism Rare",                   # 33 cards
    "ACE SPEC Rare",                # 54 cards
    "Rare BREAK",                   # 28 cards
    "Rare Ace",                     # 14 cards
    "Black White Rare",             # 4 cards
    
    # Promos (included as they are often valuable cards)
    "Promo",                        # 3513 cards
    
    # Special Collections
    "Classic Collection",           # 129 cards
]

# EXCLUDED rarities (non-collectibles or low value):
# - Common (6257)
# - Uncommon (6005)
# - Code Card (462)
# - Unconfirmed (66)
# - (EMPTY) (93)

# ============================================================
# Liquidity Configuration
# ============================================================

# Weights for custom liquidity score calculation
# Old method (simple)
LIQUIDITY_WEIGHTS = {
    "nm_listings": 0.50,      # Number of Near Mint listings
    "total_listings": 0.30,   # Market depth
    "multi_condition": 0.20,  # Presence of multiple conditions
}

# New method: Weights by condition
# LP cards are less "ideal" but still liquid
CONDITION_WEIGHTS = {
    "Near Mint": 1.00,        # Reference
    "Lightly Played": 0.80,   # Slight discount
    "Moderately Played": 0.60, # Medium discount
    "Heavily Played": 0.40,   # Heavy discount
    "Damaged": 0.20,          # Very low
}

# Cap for liquidity normalization
LIQUIDITY_CAP = 100  # 100 weighted listings = max score (1.0)

# Volume cap for volume-based calculation
VOLUME_CAP = 50  # 50 sales/day = max score (1.0)

# Temporal decay for volume (B + C)
# More recent = more weight
VOLUME_DECAY_WEIGHTS = {
    0: 1.00,   # Today
    1: 0.70,   # Yesterday
    2: 0.50,   # Day -2
    3: 0.35,   # Day -3
    4: 0.25,   # Day -4
    5: 0.15,   # Day -5
    6: 0.10,   # Day -6
}
VOLUME_DECAY_SUM = sum(VOLUME_DECAY_WEIGHTS.values())  # 3.05

# Minimum threshold for rebalancing eligibility (D)
MIN_AVG_VOLUME_30D = 0.5  # 0.5 sales/day = ~15 sales/month

# Thresholds for normalization
LIQUIDITY_NORMALIZATION = {
    "nm_listings_cap": 20,    # 20+ NM listings = max score
    "total_listings_cap": 50, # 50+ total listings = max score
}

# ============================================================
# API Rate Limits
# ============================================================

# PokemonPriceTracker Business: 200,000 req/day
PPT_RATE_LIMIT = {
    "requests_per_day": 200000,
    "requests_per_minute": 60,
    "delay_between_requests": 0.05,  # 50ms
}

# ============================================================
# Composite Price Configuration
# ============================================================

# Weighting for composite price
PRICE_WEIGHTS = {
    "cards": {
        "us": 0.50,  # TCGplayer USD
        "eu": 0.50,  # Cardmarket EUR (converted to USD)
    },
}

# ============================================================
# Outlier Detection
# ============================================================

OUTLIER_RULES = {
    "min_price": 0.10,           # Minimum price to be eligible ($)
    "max_price": 100000,         # Maximum plausible price ($)
    "max_weekly_change": 0.80,   # ±80% max weekly variation
    "max_us_eu_divergence": 2.0, # Max US/EU gap (100%)
}

# ============================================================
# Validation
# ============================================================

def validate_config():
    """Verifies that all configuration is present."""
    errors = []
    
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL missing")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY missing")
    if not PPT_API_KEY:
        errors.append("PPT_API_KEY missing")
    
    if errors:
        raise ValueError(f"Incomplete configuration: {', '.join(errors)}")
    
    return True
