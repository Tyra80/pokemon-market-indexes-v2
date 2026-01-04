"""
Pokemon Market Indexes v2 - Fetch Prices
========================================
Récupère les prix des cartes depuis PokemonPriceTracker.

Stratégie optimisée:
- Utilise /cards?set={name}&fetchAllInSet=true pour récupérer toutes les cartes d'un set avec prix
- Coût: 1 crédit par carte (vs 1 crédit par requête individuelle)
- ~26k cartes = ~26k crédits (bien sous les 200k/jour du plan Business)

Usage:
    python scripts/fetch_prices.py
"""

import sys
import os
import time
import requests
from datetime import datetime, date

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert, fetch_all_paginated,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import PPT_API_KEY, PPT_BASE_URL, LIQUIDITY_WEIGHTS, LIQUIDITY_NORMALIZATION

# Headers d'authentification
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}

# Date du jour
TODAY = get_today()

# Maximum backoff time in seconds to prevent excessive waits
MAX_BACKOFF_SECONDS = 60


def api_request(endpoint: str, params: dict = None, max_retries: int = 5) -> dict:
    """
    Effectue une requête à l'API avec retry automatique.
    Uses exponential backoff with a cap to prevent excessive wait times.
    """
    url = f"{PPT_BASE_URL}{endpoint}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)

            if response.status_code == 429:
                # Exponential backoff: 10s, 20s, 40s... capped at MAX_BACKOFF_SECONDS
                wait_time = min(10 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⏳ Rate limit, pause {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            if attempt < max_retries - 1:
                wait_time = min(10 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⚠️ HTTP Error {response.status_code}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"   ❌ Failed after {max_retries} attempts: {e}")
            return None

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = min(10 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⚠️ Request error: {str(e)[:100]}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"   ❌ Failed after {max_retries} attempts: {e}")
            return None

    return None


def calculate_liquidity_score(prices_data: dict) -> float:
    """
    Calcule le score de liquidité custom basé sur les listings.
    
    Formule:
    - 50% : NM listings (normalisé sur 20)
    - 30% : Total listings (normalisé sur 50)
    - 20% : Multi-condition (1 si >= 3 conditions avec listings)
    """
    if not prices_data:
        return 0.0
    
    conditions = prices_data.get("conditions", {})
    
    if not conditions:
        # Fallback sur listings global
        total = prices_data.get("listings", 0) or 0
        return min(total / 50, 1.0) * 0.5
    
    # Signal 1: Listings Near Mint
    nm_data = conditions.get("Near Mint", {})
    nm_listings = nm_data.get("listings", 0) if isinstance(nm_data, dict) else 0
    nm_listings = nm_listings or 0
    nm_score = min(nm_listings / LIQUIDITY_NORMALIZATION.get("nm_listings_cap", 20), 1.0)
    
    # Signal 2: Total listings
    total_listings = 0
    conditions_with_listings = 0
    
    for cond_name, cond_data in conditions.items():
        if isinstance(cond_data, dict):
            listings = cond_data.get("listings", 0) or 0
            total_listings += listings
            if listings > 0:
                conditions_with_listings += 1
    
    total_score = min(total_listings / LIQUIDITY_NORMALIZATION.get("total_listings_cap", 50), 1.0)
    
    # Signal 3: Multi-condition
    multi_score = 1.0 if conditions_with_listings >= 3 else (0.5 if conditions_with_listings >= 2 else 0.0)
    
    # Score composite
    liquidity_score = (
        LIQUIDITY_WEIGHTS.get("nm_listings", 0.5) * nm_score +
        LIQUIDITY_WEIGHTS.get("total_listings", 0.3) * total_score +
        LIQUIDITY_WEIGHTS.get("multi_condition", 0.2) * multi_score
    )
    
    return round(liquidity_score, 4)


def extract_price_data(card_data: dict) -> dict:
    """
    Extrait les données de prix d'une carte.
    """
    if not card_data:
        return None
    
    card_id = card_data.get("id")
    if not card_id:
        return None
    
    prices = card_data.get("prices", {})
    if not prices:
        return None
    
    conditions = prices.get("conditions", {})
    
    # Prix principaux
    market_price = prices.get("market")
    
    # Si pas de prix du tout, skip
    if not market_price:
        return None
    
    # Prix par condition
    nm_data = conditions.get("Near Mint", {}) if conditions else {}
    lp_data = conditions.get("Lightly Played", {}) if conditions else {}
    mp_data = conditions.get("Moderately Played", {}) if conditions else {}
    hp_data = conditions.get("Heavily Played", {}) if conditions else {}
    dmg_data = conditions.get("Damaged", {}) if conditions else {}
    
    # Total listings
    total_listings = 0
    for cond_data in conditions.values():
        if isinstance(cond_data, dict):
            total_listings += cond_data.get("listings", 0) or 0
    
    # Fallback sur listings global si pas de conditions
    if total_listings == 0:
        total_listings = prices.get("listings", 0) or 0
    
    # Calcul liquidité
    liquidity_score = calculate_liquidity_score(prices)
    
    # Last updated
    last_updated = prices.get("lastUpdated")
    
    return {
        "price_date": TODAY,
        "card_id": card_id,
        "market_price": market_price,
        "low_price": prices.get("low"),
        "mid_price": prices.get("mid"),
        "high_price": prices.get("high"),
        "nm_price": nm_data.get("price") if isinstance(nm_data, dict) else None,
        "nm_listings": nm_data.get("listings") if isinstance(nm_data, dict) else None,
        "lp_price": lp_data.get("price") if isinstance(lp_data, dict) else None,
        "lp_listings": lp_data.get("listings") if isinstance(lp_data, dict) else None,
        "mp_price": mp_data.get("price") if isinstance(mp_data, dict) else None,
        "mp_listings": mp_data.get("listings") if isinstance(mp_data, dict) else None,
        "hp_price": hp_data.get("price") if isinstance(hp_data, dict) else None,
        "hp_listings": hp_data.get("listings") if isinstance(hp_data, dict) else None,
        "dmg_price": dmg_data.get("price") if isinstance(dmg_data, dict) else None,
        "dmg_listings": dmg_data.get("listings") if isinstance(dmg_data, dict) else None,
        "total_listings": total_listings,
        "liquidity_score": liquidity_score,
        "last_updated_api": last_updated,
    }


def fetch_prices_for_set(set_name: str) -> list:
    """
    Récupère tous les prix d'un set en une seule requête.
    """
    try:
        data = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
        })
        
        if data is None:
            return []
        
        cards = data.get("data", [])
        
        if isinstance(cards, dict):
            cards = [cards]
        
        # Extrait les prix de chaque carte
        prices = []
        for card in cards:
            if card and isinstance(card, dict):
                price_data = extract_price_data(card)
                if price_data:
                    prices.append(price_data)
        
        return prices
        
    except Exception as e:
        print(f"   ⚠️ Erreur: {e}")
        return []


def main():
    print_header("💰 Pokemon Market Indexes - Fetch Prices")
    print(f"📅 Date : {TODAY}")
    print()
    
    # Connexion
    print_step(1, "Connexion à Supabase")
    try:
        client = get_db_client()
        print_success("Connecté à Supabase")
    except Exception as e:
        print_error(f"Connexion échouée : {e}")
        return
    
    # Log du run
    run_id = log_run_start(client, "fetch_prices")
    
    total_prices = 0
    total_sets = 0
    
    try:
        # Récupère la liste des sets depuis la base
        print_step(2, "Chargement des sets depuis Supabase")
        
        response = client.from_("sets").select("set_id, name").execute()
        sets = response.data
        
        print_success(f"{len(sets)} sets en base")
        
        if not sets:
            print_error("Aucun set en base ! Lance d'abord fetch_cards.py")
            return
        
        # Récupère les prix par set
        print_step(3, "Récupération des prix par set")
        
        all_prices = []
        
        for i, set_data in enumerate(sets, 1):
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            prices = fetch_prices_for_set(set_name)
            
            if prices:
                all_prices.extend(prices)
                print(f"   ✅ {len(prices)} prix")
            else:
                print(f"   ⚠️ Aucun prix")
            
            total_sets += 1
            
            # Sauvegarde par batch de 2000
            if len(all_prices) >= 2000:
                result = batch_upsert(client, "card_prices_daily", all_prices, 
                                      on_conflict="price_date,card_id")
                print(f"\n   💾 Batch sauvegardé : {result['saved']} prix")
                total_prices += result['saved']
                all_prices = []
            
            # Pause pour rate limit (200 calls/min = 0.3s min, on met 0.5s pour être safe)
            time.sleep(0.5)
        
        # Dernier batch
        if all_prices:
            result = batch_upsert(client, "card_prices_daily", all_prices,
                                  on_conflict="price_date,card_id")
            print(f"\n   💾 Dernier batch : {result['saved']} prix")
            total_prices += result['saved']
        
        # Vérification
        print_step(4, "Vérification")
        
        response = client.from_("card_prices_daily") \
            .select("*", count="exact") \
            .eq("price_date", TODAY) \
            .execute()
        print(f"   Prix aujourd'hui : {response.count}")
        
        # Top 5 par prix
        response = client.from_("card_prices_daily") \
            .select("card_id, market_price, nm_listings, liquidity_score") \
            .eq("price_date", TODAY) \
            .order("market_price", desc=True) \
            .limit(5) \
            .execute()
        
        if response.data:
            print("\n   📋 Top 5 par prix :")
            for row in response.data:
                print(f"      {row['card_id'][:20]:<20} | ${row['market_price']:>10.2f} | {row['nm_listings'] or 0} NM | liq={row['liquidity_score'] or 0:.2f}")
        
        # Log succès
        log_run_end(client, run_id, "success",
                    records_processed=total_prices,
                    details={"sets": total_sets, "prices": total_prices})
        
        # Notification Discord
        send_discord_notification(
            "✅ Fetch Prices - Succès",
            f"{total_prices} prix récupérés pour {total_sets} sets."
        )
        
        print()
        print_header("📊 RÉSUMÉ")
        print(f"   Sets traités : {total_sets}")
        print(f"   Prix totaux  : {total_prices}")
        print()
        print_success("Script terminé avec succès !")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption détectée (Ctrl+C)")
        log_run_end(client, run_id, "interrupted", records_processed=total_prices)
        
    except Exception as e:
        print_error(f"Erreur : {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Fetch Prices - Échec",
            f"Erreur : {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()