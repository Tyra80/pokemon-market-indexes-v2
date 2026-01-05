"""
Pokemon Market Indexes v2 - Backfill History (Optimized)
========================================================
Récupère les prix historiques de manière incrémentale.

Features:
- Skip les dates déjà présentes en DB (économise les crédits API)
- Récupère tous les volumes par condition
- daily_volume = weighted volume
- Support jusqu'à 90 jours d'historique

Usage:
    python scripts/backfill_history_v2.py
    python scripts/backfill_history_v2.py --days 90
    python scripts/backfill_history_v2.py --days 90 --force  # Ignore le cache
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


def api_request(endpoint: str, params: dict = None, max_retries: int = 5) -> tuple:
    """
    Effectue une requête à l'API avec retry automatique.
    
    Returns: (data, credits_remaining) ou (None, 0) si erreur
    """
    url = f"{BASE_URL}{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=120)
            
            # Récupère les crédits restants depuis les headers
            credits_remaining = int(response.headers.get("X-RateLimit-Remaining", -1))
            
            if response.status_code == 429:
                # Crédits épuisés !
                print(f"\n   🛑 API CREDITS EXHAUSTED!")
                return None, 0
            
            response.raise_for_status()
            return response.json(), credits_remaining
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                return None, 0  # Crédits épuisés
            if attempt < max_retries - 1:
                print(f"   ⚠️ HTTP Error {response.status_code}, retry...")
                time.sleep(5)
                continue
            print(f"   ❌ Échec après {max_retries} tentatives: {e}")
            return None, -1
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Erreur: {e}, retry...")
                time.sleep(5)
                continue
            print(f"   ❌ Échec après {max_retries} tentatives: {e}")
            return None, -1
    
    return None, -1


def get_existing_dates_for_set(client, set_id: str) -> set:
    """
    Récupère les dates déjà présentes en DB pour un set.
    Retourne un set de dates (YYYY-MM-DD) où on a déjà des données.
    """
    try:
        # Récupère les card_ids du set
        response = client.from_("cards") \
            .select("card_id") \
            .eq("set_id", set_id) \
            .execute()
        
        if not response.data:
            return set()
        
        card_ids = [c["card_id"] for c in response.data]
        
        # Récupère les dates existantes pour ces cartes
        # On prend juste une carte représentative pour checker
        sample_card_id = card_ids[0]
        
        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .eq("card_id", sample_card_id) \
            .execute()
        
        if not response.data:
            return set()
        
        return {row["price_date"] for row in response.data}
        
    except Exception as e:
        print(f"   ⚠️ Error checking existing dates: {e}")
        return set()


def extract_historical_prices(card_data: dict, target_dates: set = None) -> list:
    """
    Extrait les prix historiques d'une carte.
    
    FIX INCLUS:
    - Récupère les volumes de TOUTES les conditions
    - daily_volume = weighted volume
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
                "daily_volume": daily_volume,
                "liquidity_score": None,
                "last_updated_api": None,
            })
            
        except Exception as e:
            continue
    
    return results


def fetch_history_for_set(set_name: str, days: int, target_dates: set = None) -> tuple:
    """
    Récupère l'historique des prix d'un set.
    
    Returns: (all_prices, stats, credits_remaining)
    """
    try:
        data, credits_remaining = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
            "includeHistory": "true",
            "days": days,
        })
        
        if data is None:
            return [], {"total": 0, "with_history": 0, "prices": 0, "skipped": 0}, credits_remaining
        
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
        
        return all_prices, stats, credits_remaining
        
    except Exception as e:
        print(f"   ⚠️ Erreur: {e}")
        return [], {"total": 0, "with_history": 0, "prices": 0, "skipped": 0}, -1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Nombre de jours d'historique (max 90)")
    parser.add_argument("--force", action="store_true", help="Ignore le cache, récupère tout")
    args = parser.parse_args()
    
    days = min(args.days, 90)  # API limite à 90 jours
    
    # Calcule les dates cibles (de J-1 à J-days)
    # On commence à J-1 car les prix du jour ne sont pas encore consolidés
    today = date.today()
    yesterday = today - timedelta(days=1)
    start_date = yesterday - timedelta(days=days-1)
    
    target_dates = set()
    current = start_date
    while current <= yesterday:
        target_dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    print_header(f"📜 Backfill History (Optimized)")
    print(f"📅 Target range: {start_date} → {yesterday}")
    print(f"📊 {len(target_dates)} days to backfill")
    print(f"🔄 Force mode: {'Yes' if args.force else 'No (incremental)'}")
    print()
    
    # Connexion
    print_step(1, "Connecting to Supabase")
    client = get_db_client()
    print_success("Connected to Supabase")
    
    # Log du run
    run_id = log_run_start(client, "backfill_history_v2")
    
    total_prices = 0
    total_sets = 0
    skipped_sets = 0
    api_calls = 0
    
    try:
        # Récupère la liste des sets
        print_step(2, "Loading sets")
        
        response = client.from_("sets").select("set_id, name").execute()
        sets = response.data
        
        print_success(f"{len(sets)} sets to process")
        
        # Récupère l'historique par set
        print_step(3, f"Fetching history ({days} days)")
        
        all_prices = []
        
        for i, set_data in enumerate(sets, 1):
            set_id = set_data.get("set_id")
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            # ============================================================
            # OPTIMISATION: Skip si on a déjà toutes les dates
            # ============================================================
            if not args.force:
                existing_dates = get_existing_dates_for_set(client, set_id)
                missing_dates = target_dates - existing_dates
                
                if not missing_dates:
                    skipped_sets += 1
                    if i % 50 == 0:  # Log tous les 50 sets
                        print(f"   [{i}/{len(sets)}] ⏭️ {set_name} - already complete")
                    continue
                
                # Utilise seulement les dates manquantes
                dates_to_fetch = missing_dates
                print(f"\n   [{i}/{len(sets)}] 📦 {set_name} ({len(missing_dates)} missing dates)")
            else:
                dates_to_fetch = target_dates
                print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            # Fetch from API
            prices, stats, credits_remaining = fetch_history_for_set(set_name, days, dates_to_fetch)
            api_calls += 1
            
            # ============================================================
            # ARRÊT AUTOMATIQUE SI CRÉDITS ÉPUISÉS
            # ============================================================
            if credits_remaining == 0:
                print(f"\n   🛑 API CREDITS EXHAUSTED!")
                print(f"   💾 Saving current progress...")
                
                # Sauvegarde ce qu'on a
                if all_prices:
                    result = batch_upsert(client, "card_prices_daily", all_prices,
                                          on_conflict="price_date,card_id")
                    total_prices += result['saved']
                    print(f"   ✅ Saved {result['saved']} records before stopping")
                
                # Log et notification
                log_run_end(client, run_id, "stopped_credits_exhausted",
                            records_processed=total_prices,
                            details={
                                "days": days,
                                "sets_processed": total_sets,
                                "sets_skipped": skipped_sets,
                                "sets_remaining": len(sets) - i,
                                "api_calls": api_calls,
                                "prices_saved": total_prices,
                                "stopped_at_set": set_name,
                                "last_set_index": i
                            })
                
                print()
                print_header("🛑 STOPPED - CREDITS EXHAUSTED")
                print(f"   Days requested     : {days}")
                print(f"   Date range         : {start_date} → {yesterday}")
                print(f"   Sets processed     : {total_sets}")
                print(f"   Sets remaining     : {len(sets) - i}")
                print(f"   API calls made     : {api_calls}")
                print(f"   Prices saved       : {total_prices}")
                print(f"   Stopped at set     : {set_name} (#{i})")
                print()
                print("   ℹ️ Run the script again tomorrow to continue from where you left off.")
                print("   ℹ️ Already-fetched data will be skipped automatically.")
                
                # Discord notification
                send_discord_notification(
                    "🛑 Backfill History - Credits Exhausted",
                    f"**Stopped due to API credit limit**\n\n"
                    f"Range: {start_date} → {yesterday}\n"
                    f"Progress: {total_sets}/{len(sets)} sets ({total_sets*100//len(sets)}%)\n"
                    f"Prices saved: {total_prices}\n"
                    f"Stopped at: {set_name}\n\n"
                    f"Run again tomorrow to continue."
                )
                
                return  # Exit cleanly
            
            if credits_remaining > 0 and credits_remaining < 1000:
                print(f"   ⚠️ Low credits: {credits_remaining} remaining")
            
            if prices:
                all_prices.extend(prices)
                print(f"   ✅ {stats['prices']} price records")
            else:
                print(f"   ⚠️ No prices")
            
            total_sets += 1
            
            # Sauvegarde par batch
            if len(all_prices) >= 5000:
                result = batch_upsert(client, "card_prices_daily", all_prices,
                                      on_conflict="price_date,card_id")
                print(f"\n   💾 Batch saved: {result['saved']} records")
                total_prices += result['saved']
                all_prices = []
            
            # Pause pour rate limit
            time.sleep(0.5)
        
        # Dernier batch
        if all_prices:
            result = batch_upsert(client, "card_prices_daily", all_prices,
                                  on_conflict="price_date,card_id")
            print(f"\n   💾 Final batch: {result['saved']} records")
            total_prices += result['saved']
        
        # Vérification
        print_step(4, "Verification")
        
        # Compte par date
        sample_dates = sorted(target_dates)[:5] + sorted(target_dates)[-5:]
        for d in sample_dates:
            response = client.from_("card_prices_daily") \
                .select("card_id", count="exact") \
                .eq("price_date", d) \
                .execute()
            print(f"   {d}: {response.count} cards")
        
        # Log succès
        log_run_end(client, run_id, "success",
                    records_processed=total_prices,
                    details={
                        "days": days,
                        "sets_processed": total_sets,
                        "sets_skipped": skipped_sets,
                        "api_calls": api_calls,
                        "prices_saved": total_prices
                    })
        
        print()
        print_header("📊 SUMMARY")
        print(f"   Days requested     : {days}")
        print(f"   Date range         : {start_date} → {yesterday}")
        print(f"   Sets processed     : {total_sets}")
        print(f"   Sets skipped (cached): {skipped_sets}")
        print(f"   API calls made     : {api_calls}")
        print(f"   Prices saved       : {total_prices}")
        print()
        print_success("Backfill complete!")
        
        # Discord notification
        send_discord_notification(
            "✅ Backfill History - Complete",
            f"Range: {start_date} → {yesterday}\n"
            f"Sets: {total_sets} processed, {skipped_sets} skipped\n"
            f"Prices: {total_prices} saved"
        )
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted (Ctrl+C)")
        log_run_end(client, run_id, "interrupted", records_processed=total_prices)
        
        # Sauvegarde ce qu'on a
        if all_prices:
            result = batch_upsert(client, "card_prices_daily", all_prices,
                                  on_conflict="price_date,card_id")
            print(f"   💾 Saved before exit: {result['saved']} records")
        
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        log_run_end(client, run_id, "failed", error_message=str(e))
        raise


if __name__ == "__main__":
    main()