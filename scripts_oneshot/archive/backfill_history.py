"""
Pokemon Market Indexes v2 - Backfill November Prices
====================================================
Récupère les prix historiques pour couvrir novembre 2025.

Utilise days=45 pour remonter jusqu'à mi-novembre.

Usage:
    python scripts/backfill_november.py
    python scripts/backfill_november.py --days 60  # Pour remonter plus loin
"""

import sys
import os
import time
import argparse
import requests
from datetime import datetime, date, timedelta

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import PPT_API_KEY, CONDITION_WEIGHTS, LIQUIDITY_CAP, RARE_RARITIES

# Base URL de l'API (v2)
BASE_URL = "https://www.pokemonpricetracker.com/api/v2"

# Headers d'authentification
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}


def api_request(endpoint: str, params: dict = None, max_retries: int = 5) -> dict:
    """Effectue une requête à l'API avec retry automatique."""
    url = f"{BASE_URL}{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=120)
            
            if response.status_code == 429:
                wait_time = 15 * (attempt + 1)
                print(f"   ⏳ Rate limit, pause {wait_time}s... (tentative {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            if attempt < max_retries - 1:
                print(f"   ⚠️ HTTP Error {response.status_code}, retry...")
                time.sleep(5)
                continue
            print(f"   ❌ Échec après {max_retries} tentatives: {e}")
            return None
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Erreur: {e}, retry...")
                time.sleep(5)
                continue
            print(f"   ❌ Échec après {max_retries} tentatives: {e}")
            return None
    
    return None


def extract_historical_prices(card_data: dict, target_dates: set = None) -> list:
    """
    Extrait les prix historiques d'une carte.
    
    Args:
        card_data: Données de la carte depuis l'API
        target_dates: Set de dates (YYYY-MM-DD) à extraire. Si None, extrait tout.
    
    Returns: Liste de dicts avec price_date, card_id, market_price, etc.
    """
    if not card_data:
        return []
    
    card_id = card_data.get("id")
    if not card_id:
        return []
    
    # Vérifie la rareté - FILTRE RARE ET PLUS
    rarity = card_data.get("rarity", "")
    if rarity not in RARE_RARITIES:
        return []
    
    # Prix actuels (pour les listings)
    prices = card_data.get("prices", {})
    conditions_current = prices.get("conditions", {})
    
    # Listings actuels
    nm_current = conditions_current.get("Near Mint", {})
    lp_current = conditions_current.get("Lightly Played", {})
    mp_current = conditions_current.get("Moderately Played", {})
    hp_current = conditions_current.get("Heavily Played", {})
    dmg_current = conditions_current.get("Damaged", {})
    
    # Historique
    price_history = card_data.get("priceHistory", {})
    if not price_history or not isinstance(price_history, dict):
        return []
    
    conditions_history = price_history.get("conditions", {})
    if not conditions_history:
        return []
    
    # On prend l'historique Near Mint comme référence principale
    nm_history_data = conditions_history.get("Near Mint", {})
    nm_history = nm_history_data.get("history", [])
    
    if not nm_history:
        return []
    
    # Récupère aussi les historiques des autres conditions
    lp_history = conditions_history.get("Lightly Played", {}).get("history", [])
    mp_history = conditions_history.get("Moderately Played", {}).get("history", [])
    hp_history = conditions_history.get("Heavily Played", {}).get("history", [])
    dmg_history = conditions_history.get("Damaged", {}).get("history", [])
    
    # Indexe par date pour fusion (prix ET volume)
    lp_by_date = {h.get("date", "")[:10]: h for h in lp_history if isinstance(h, dict)}
    mp_by_date = {h.get("date", "")[:10]: h for h in mp_history if isinstance(h, dict)}
    hp_by_date = {h.get("date", "")[:10]: h for h in hp_history if isinstance(h, dict)}
    dmg_by_date = {h.get("date", "")[:10]: h for h in dmg_history if isinstance(h, dict)}
    
    results = []
    
    for history_entry in nm_history:
        try:
            if not isinstance(history_entry, dict):
                continue
            
            history_date = history_entry.get("date", "")
            if not history_date:
                continue
            
            # Extrait juste la date (YYYY-MM-DD)
            price_date = history_date[:10] if "T" in history_date else history_date
            
            # Filtre par dates cibles si spécifié
            if target_dates and price_date not in target_dates:
                continue
            
            nm_price = history_entry.get("market")
            if not nm_price:
                continue
            
            # Récupère les données des autres conditions pour cette date
            lp_entry = lp_by_date.get(price_date, {})
            mp_entry = mp_by_date.get(price_date, {})
            hp_entry = hp_by_date.get(price_date, {})
            dmg_entry = dmg_by_date.get(price_date, {})
            
            # ============================================================
            # FIX: Récupère les volumes de TOUTES les conditions
            # ============================================================
            nm_volume = history_entry.get("volume")
            lp_volume = lp_entry.get("volume") if lp_entry else None
            mp_volume = mp_entry.get("volume") if mp_entry else None
            hp_volume = hp_entry.get("volume") if hp_entry else None
            dmg_volume = dmg_entry.get("volume") if dmg_entry else None
            
            # ============================================================
            # FIX: daily_volume = weighted volume (pondéré par condition)
            # ============================================================
            weighted_volume = (
                (nm_volume or 0) * CONDITION_WEIGHTS.get("Near Mint", 1.0) +
                (lp_volume or 0) * CONDITION_WEIGHTS.get("Lightly Played", 0.8) +
                (mp_volume or 0) * CONDITION_WEIGHTS.get("Moderately Played", 0.6) +
                (hp_volume or 0) * CONDITION_WEIGHTS.get("Heavily Played", 0.4) +
                (dmg_volume or 0) * CONDITION_WEIGHTS.get("Damaged", 0.2)
            )
            
            daily_volume = weighted_volume if weighted_volume > 0 else None
            
            results.append({
                "price_date": price_date,
                "card_id": card_id,
                "market_price": float(nm_price),
                "low_price": None,
                "mid_price": None,
                "high_price": None,
                "nm_price": float(nm_price),
                "nm_listings": nm_current.get("listings") if isinstance(nm_current, dict) else None,
                "nm_volume": nm_volume,
                "lp_price": float(lp_entry.get("market")) if lp_entry.get("market") else None,
                "lp_listings": lp_current.get("listings") if isinstance(lp_current, dict) else None,
                "lp_volume": lp_volume,
                "mp_price": float(mp_entry.get("market")) if mp_entry.get("market") else None,
                "mp_listings": mp_current.get("listings") if isinstance(mp_current, dict) else None,
                "mp_volume": mp_volume,
                "hp_price": float(hp_entry.get("market")) if hp_entry.get("market") else None,
                "hp_listings": hp_current.get("listings") if isinstance(hp_current, dict) else None,
                "hp_volume": hp_volume,
                "dmg_price": float(dmg_entry.get("market")) if dmg_entry.get("market") else None,
                "dmg_listings": dmg_current.get("listings") if isinstance(dmg_current, dict) else None,
                "dmg_volume": dmg_volume,
                "total_listings": None,
                "daily_volume": daily_volume,  # NOW = weighted volume
                "liquidity_score": None,  # Will be calculated by calculate_index.py
                "last_updated_api": None,
            })
            
        except Exception as e:
            continue
    
    return results


def fetch_history_for_set(set_name: str, days: int, target_dates: set = None) -> tuple:
    """
    Récupère l'historique des prix d'un set.
    
    Returns: (all_prices, stats)
    """
    try:
        data = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
            "includeHistory": "true",
            "days": days,
        })
        
        if data is None:
            return [], {"total": 0, "with_history": 0, "prices": 0, "skipped": 0}
        
        cards = data.get("data", [])
        
        if isinstance(cards, dict):
            cards = [cards]
        
        stats = {
            "total": len(cards),
            "with_history": 0,
            "prices": 0,
            "skipped": 0,
        }
        
        all_prices = []
        
        for card in cards:
            if not card or not isinstance(card, dict):
                continue
            
            # Filtre par rareté
            rarity = card.get("rarity", "")
            if rarity not in RARE_RARITIES:
                stats["skipped"] += 1
                continue
            
            historical_prices = extract_historical_prices(card, target_dates)
            
            if historical_prices:
                all_prices.extend(historical_prices)
                stats["prices"] += len(historical_prices)
                stats["with_history"] += 1
        
        return all_prices, stats
        
    except Exception as e:
        print(f"   ⚠️ Erreur: {e}")
        return [], {"total": 0, "with_history": 0, "prices": 0, "skipped": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=45, help="Nombre de jours d'historique")
    parser.add_argument("--target-start", type=str, default="2025-11-20", help="Date de début cible")
    parser.add_argument("--target-end", type=str, default="2025-12-05", help="Date de fin cible")
    args = parser.parse_args()
    
    days = args.days
    
    # Dates cibles (on veut surtout novembre et début décembre)
    start = datetime.strptime(args.target_start, "%Y-%m-%d").date()
    end = datetime.strptime(args.target_end, "%Y-%m-%d").date()
    target_dates = set()
    current = start
    while current <= end:
        target_dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    print_header(f"📜 Backfill November Prices ({days} jours d'historique)")
    print(f"📅 Dates cibles : {args.target_start} → {args.target_end}")
    print(f"📊 {len(target_dates)} jours à récupérer")
    print()
    
    # Connexion
    print_step(1, "Connexion à Supabase")
    client = get_db_client()
    print_success("Connecté à Supabase")
    
    # Log du run
    run_id = log_run_start(client, "backfill_november")
    
    total_prices = 0
    total_sets = 0
    
    try:
        # Récupère la liste des sets
        print_step(2, "Chargement des sets")
        
        response = client.from_("sets").select("set_id, name").execute()
        sets = response.data
        
        print_success(f"{len(sets)} sets à traiter")
        
        # Récupère l'historique par set
        print_step(3, f"Récupération de l'historique ({days} jours)")
        
        all_prices = []
        
        for i, set_data in enumerate(sets, 1):
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            prices, stats = fetch_history_for_set(set_name, days, target_dates)
            
            if prices:
                all_prices.extend(prices)
                print(f"   ✅ {stats['prices']} prix historiques")
            else:
                print(f"   ⚠️ Aucun prix")
            
            total_sets += 1
            
            # Sauvegarde par batch
            if len(all_prices) >= 5000:
                result = batch_upsert(client, "card_prices_daily", all_prices,
                                      on_conflict="price_date,card_id")
                print(f"\n   💾 Batch sauvegardé : {result['saved']} prix")
                total_prices += result['saved']
                all_prices = []
            
            # Pause pour rate limit
            time.sleep(1)
        
        # Dernier batch
        if all_prices:
            result = batch_upsert(client, "card_prices_daily", all_prices,
                                  on_conflict="price_date,card_id")
            print(f"\n   💾 Dernier batch : {result['saved']} prix")
            total_prices += result['saved']
        
        # Vérification
        print_step(4, "Vérification des dates cibles")
        
        for d in sorted(target_dates)[:10]:  # Affiche les 10 premières
            response = client.from_("card_prices_daily") \
                .select("card_id", count="exact") \
                .eq("price_date", d) \
                .execute()
            print(f"   {d}: {response.count} cartes")
        
        print("   ...")
        
        # Log succès
        log_run_end(client, run_id, "success",
                    records_processed=total_prices,
                    details={"days": days, "sets": total_sets, "prices": total_prices})
        
        print()
        print_header("📊 RÉSUMÉ")
        print(f"   Jours d'historique : {days}")
        print(f"   Sets traités       : {total_sets}")
        print(f"   Prix récupérés     : {total_prices}")
        print()
        print_success("Backfill terminé avec succès !")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption détectée (Ctrl+C)")
        log_run_end(client, run_id, "interrupted", records_processed=total_prices)
        
    except Exception as e:
        print_error(f"Erreur : {e}")
        import traceback
        traceback.print_exc()
        log_run_end(client, run_id, "failed", error_message=str(e))
        raise


if __name__ == "__main__":
    main()