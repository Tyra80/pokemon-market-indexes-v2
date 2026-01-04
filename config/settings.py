"""
Pokemon Market Indexes v2 - Configuration
=========================================
Centralise toute la configuration du projet.
"""

import os
from dotenv import load_dotenv

# Charge les variables d'environnement
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
    "SEALED_100": {
        "type": "sealed",
        "size": 100,
        "liquidity_threshold_entry": 0.60,
        "liquidity_threshold_maintain": 0.45,
        "maturity_days": 90,
    },
    "SEALED_500": {
        "type": "sealed",
        "size": 500,
        "liquidity_threshold_entry": 0.45,
        "liquidity_threshold_maintain": 0.35,
        "maturity_days": 90,
    },
}

# ============================================================
# Rarity Configuration
# ============================================================

# Rarités considérées comme "Rare" ou supérieur
# Basé sur les données réelles de PokemonPriceTracker API
RARE_RARITIES = [
    # Standard Rares
    "Rare",                         # 3164 cartes
    "Holo Rare",                    # 1845 cartes
    "Shiny Holo Rare",              # 246 cartes
    
    # Ultra/Secret
    "Ultra Rare",                   # 2433 cartes
    "Secret Rare",                  # 631 cartes
    "Hyper Rare",                   # 74 cartes
    "Mega Hyper Rare",              # 3 cartes
    
    # Illustration
    "Illustration Rare",            # 432 cartes
    "Special Illustration Rare",    # 181 cartes
    "Double Rare",                  # 368 cartes
    
    # Shiny
    "Shiny Rare",                   # 120 cartes
    "Shiny Ultra Rare",             # 12 cartes
    
    # Special
    "Amazing Rare",                 # 9 cartes
    "Radiant Rare",                 # 32 cartes
    "Prism Rare",                   # 33 cartes
    "ACE SPEC Rare",                # 54 cartes
    "Rare BREAK",                   # 28 cartes
    "Rare Ace",                     # 14 cartes
    "Black White Rare",             # 4 cartes
    
    # Promos (inclus car souvent des cartes de valeur)
    "Promo",                        # 3513 cartes
    
    # Collections spéciales
    "Classic Collection",           # 129 cartes
]

# Raretés EXCLUES (non-collectibles ou faible valeur):
# - Common (6257)
# - Uncommon (6005)
# - Code Card (462)
# - Unconfirmed (66)
# - (VIDE) (93)

# ============================================================
# Liquidity Configuration
# ============================================================

# Poids pour le calcul du score de liquidité custom
LIQUIDITY_WEIGHTS = {
    "nm_listings": 0.50,      # Nombre de listings Near Mint
    "total_listings": 0.30,   # Profondeur du marché
    "multi_condition": 0.20,  # Présence de plusieurs conditions
}

# Seuils pour normalisation
LIQUIDITY_NORMALIZATION = {
    "nm_listings_cap": 20,    # 20+ listings NM = score max
    "total_listings_cap": 50, # 50+ listings total = score max
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

# Pondération pour le prix composite
PRICE_WEIGHTS = {
    "cards": {
        "us": 0.50,  # TCGplayer USD
        "eu": 0.50,  # Cardmarket EUR (converti en USD)
    },
    "sealed": {
        "us": 1.00,  # TCGplayer USD uniquement
        "eu": 0.00,  # Pas de données EU pour sealed
    },
}

# ============================================================
# Outlier Detection
# ============================================================

OUTLIER_RULES = {
    "min_price": 0.10,           # Prix minimum pour être éligible ($)
    "max_price": 100000,         # Prix maximum plausible ($)
    "max_weekly_change": 0.80,   # ±80% max de variation hebdo
    "max_us_eu_divergence": 2.0, # Écart max US/EU (100%)
}

# ============================================================
# Validation
# ============================================================

def validate_config():
    """Vérifie que toute la configuration est présente."""
    errors = []
    
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL manquant")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY manquant")
    if not PPT_API_KEY:
        errors.append("PPT_API_KEY manquant")
    
    if errors:
        raise ValueError(f"Configuration incomplète: {', '.join(errors)}")
    
    return True