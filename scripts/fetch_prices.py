"""
Pokemon Market Indexes v2 - Fetch Prices
========================================
Fetches card prices from PokemonPriceTracker.

Optimized strategy:
- Uses /cards?set={name}&fetchAllInSet=true to fetch all cards from a set with prices
- Uses includeHistory=true to get sales volume data
- Cost: 2 credits per card (with history)
- ~13k rare cards = ~26k credits (well under 200k/day Business plan limit)

Usage:
    python scripts/fetch_prices.py
"""

import sys
import os
import time
import requests
from datetime import datetime, date

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert, fetch_all_paginated,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import PPT_API_KEY, CONDITION_WEIGHTS, LIQUIDITY_CAP, VOLUME_CAP, RARE_RARITIES

# API Base URL (v2)
BASE_URL = "https://www.pokemonpricetracker.com/api/v2"

# Authentication headers
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}



def api_request(endpoint: str, params: dict = None, max_retries: int = 5) -> dict:
    """
    Makes a request to the API with automatic retry.
    """
    url = f"{BASE_URL}{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)
            
            if response.status_code == 429:
                wait_time = 10 * (attempt + 1)  # 10s, 20s, 30s, 40s, 50s
                print(f"   ⏳ Rate limit, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            if attempt < max_retries - 1:
                print(f"   ⚠️ HTTP Error {response.status_code}, retrying...")
                time.sleep(5)
                continue
            print(f"   ❌ Failed after {max_retries} attempts: {e}")
            return None
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Error: {e}, retrying...")
                time.sleep(5)
                continue
            print(f"   ❌ Failed after {max_retries} attempts: {e}")
            return None
    
    return None


def calculate_liquidity_score(prices_data: dict) -> tuple:
    """
    Calculates liquidity score with condition weighting.
    
    Formula:
    weighted_listings = Σ(listings_condition × weight_condition)
    liquidity_score = min(weighted_listings / LIQUIDITY_CAP, 1.0)
    
    Example:
    - 10 NM (×1.0) + 20 LP (×0.8) + 5 MP (×0.6) = 10 + 16 + 3 = 29
    - Score = 29 / 100 = 0.29
    
    Returns: (liquidity_score, weighted_listings, conditions_count)
    """
    if not prices_data:
        return 0.0, 0, 0
    
    conditions = prices_data.get("conditions", {})
    
    if not conditions:
        # Fallback to global listings (treated as NM)
        total = prices_data.get("listings", 0) or 0
        weighted = total * CONDITION_WEIGHTS.get("Near Mint", 1.0)
        return min(weighted / LIQUIDITY_CAP, 1.0), weighted, 1 if total > 0 else 0
    
    # Weighted calculation by condition
    weighted_listings = 0
    conditions_with_listings = 0
    
    for cond_name, cond_data in conditions.items():
        if isinstance(cond_data, dict):
            listings = cond_data.get("listings", 0) or 0
            
            if listings > 0:
                weight = CONDITION_WEIGHTS.get(cond_name, 0.5)  # Default 0.5 for unknown condition
                weighted_listings += listings * weight
                conditions_with_listings += 1
    
    # Normalization
    liquidity_score = min(weighted_listings / LIQUIDITY_CAP, 1.0)
    
    return round(liquidity_score, 4), round(weighted_listings, 2), conditions_with_listings


def extract_price_data(card_data: dict, price_date: str) -> dict:
    """
    Extracts price data from a card, including sales volume.

    Volume is only available if includeHistory=true in the request.
    Structure: priceHistory.conditions.{condition}.history[-1].volume
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
    
    # Main prices
    market_price = prices.get("market")
    
    # Skip if no price at all
    if not market_price:
        return None
    
    # Price by condition (current data)
    nm_data = conditions.get("Near Mint", {}) if conditions else {}
    lp_data = conditions.get("Lightly Played", {}) if conditions else {}
    mp_data = conditions.get("Moderately Played", {}) if conditions else {}
    hp_data = conditions.get("Heavily Played", {}) if conditions else {}
    dmg_data = conditions.get("Damaged", {}) if conditions else {}
    
    # Total listings (raw, unweighted)
    total_listings = 0
    for cond_data in conditions.values():
        if isinstance(cond_data, dict):
            total_listings += cond_data.get("listings", 0) or 0
    
    # Fallback to global listings if no conditions
    if total_listings == 0:
        total_listings = prices.get("listings", 0) or 0
    
    # =========================================================================
    # NEW: Extract sales volume from priceHistory (J-1 for consolidated data)
    # =========================================================================
    nm_volume = None
    lp_volume = None
    mp_volume = None
    hp_volume = None
    dmg_volume = None
    
    price_history = card_data.get("priceHistory", {})
    if price_history and isinstance(price_history, dict):
        conditions_history = price_history.get("conditions", {})
        
        # For each condition, get the volume from YESTERDAY (J-1)
        # because today's volume may not be consolidated yet
        for cond_name, cond_history in conditions_history.items():
            if not isinstance(cond_history, dict):
                continue
            
            history_list = cond_history.get("history", [])
            if history_list and len(history_list) >= 2:
                # Take J-1 (yesterday) for consolidated volume
                yesterday = history_list[-2]
                if isinstance(yesterday, dict):
                    vol = yesterday.get("volume")
                    if vol is not None:
                        # Assign to correct field
                        if cond_name == "Near Mint":
                            nm_volume = vol
                        elif cond_name == "Lightly Played":
                            lp_volume = vol
                        elif cond_name == "Moderately Played":
                            mp_volume = vol
                        elif cond_name == "Heavily Played":
                            hp_volume = vol
                        elif cond_name == "Damaged":
                            dmg_volume = vol
    
    # =========================================================================
    # Liquidity calculation - Based on weighted volume
    # =========================================================================
    # Calculate weighted volume (condition-adjusted)
    weighted_volume = (
        (nm_volume or 0) * CONDITION_WEIGHTS.get("Near Mint", 1.0) +
        (lp_volume or 0) * CONDITION_WEIGHTS.get("Lightly Played", 0.8) +
        (mp_volume or 0) * CONDITION_WEIGHTS.get("Moderately Played", 0.6) +
        (hp_volume or 0) * CONDITION_WEIGHTS.get("Heavily Played", 0.4) +
        (dmg_volume or 0) * CONDITION_WEIGHTS.get("Damaged", 0.2)
    )
    
    # daily_volume = weighted volume (Option B)
    daily_volume = weighted_volume if weighted_volume > 0 else None
    
    if weighted_volume > 0:
        # Score = weighted volume / cap (e.g., 50 sales/day = max score)
        liquidity_score = min(weighted_volume / VOLUME_CAP, 1.0)
    else:
        # Fallback to listings method if no volume
        liquidity_score, _, _ = calculate_liquidity_score(prices)
    
    # Last updated
    last_updated = prices.get("lastUpdated")
    
    return {
        "price_date": price_date,
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
        "daily_volume": daily_volume,  # Now = weighted volume
        "nm_volume": nm_volume,
        "lp_volume": lp_volume,
        "mp_volume": mp_volume,
        "hp_volume": hp_volume,
        "dmg_volume": dmg_volume,
        "liquidity_score": round(liquidity_score, 4),
        "last_updated_api": last_updated,
    }


def fetch_prices_for_set(set_name: str, price_date: str, filter_rarity: bool = True) -> tuple:
    """
    Fetches all prices for a set with sales volume.

    Uses includeHistory=true + days=1 to get today's volume.
    Cost: 2 credits per card (instead of 1).

    Args:
        set_name: Set name
        price_date: Date string (YYYY-MM-DD) to use for price records
        filter_rarity: If True, only keep cards with rarity >= Rare

    Returns:
        tuple: (prices_list, stats_dict)
    """
    try:
        data = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
            "includeHistory": "true",  # NEW: enables history
            "days": 1,                  # NEW: just the last day (for volume)
        })

        if data is None:
            return [], {"total": 0, "filtered": 0, "skipped": 0, "with_volume": 0}

        cards = data.get("data", [])

        if isinstance(cards, dict):
            cards = [cards]

        # Stats
        stats = {
            "total": len(cards),
            "filtered": 0,
            "skipped": 0,
            "skipped_rarities": {},
            "with_volume": 0,
            "total_volume": 0,
        }

        # Extract prices from each card
        prices = []
        for card in cards:
            if card and isinstance(card, dict):
                # Filter by rarity if requested
                if filter_rarity:
                    rarity = card.get("rarity", "")
                    if rarity not in RARE_RARITIES:
                        stats["skipped"] += 1
                        stats["skipped_rarities"][rarity] = stats["skipped_rarities"].get(rarity, 0) + 1
                        continue

                price_data = extract_price_data(card, price_date)
                if price_data:
                    prices.append(price_data)
                    stats["filtered"] += 1

                    # Volume stats
                    if price_data.get("daily_volume"):
                        stats["with_volume"] += 1
                        stats["total_volume"] += price_data["daily_volume"]

        return prices, stats

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return [], {"total": 0, "filtered": 0, "skipped": 0, "with_volume": 0}


def main():
    from datetime import date, timedelta
    # Prices fetched at 06:00 UTC are yesterday's closing (US time)
    today = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    print_header("💰 Pokemon Market Indexes - Fetch Prices (with Volume)")
    print(f"📅 Date: {today}")
    print(f"🔍 Rarity filter: Enabled (>= Rare)")
    print(f"📊 Sales volume: Enabled (includeHistory=true)")
    print(f"💰 API cost: 2 credits/card")
    print()

    # Connection
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # Log run
    run_id = log_run_start(client, "fetch_prices")
    
    total_prices = 0
    total_sets = 0
    total_skipped = 0
    total_with_volume = 0
    total_volume = 0
    skipped_by_rarity = {}
    
    try:
        # Get list of sets from database
        print_step(2, "Loading sets from Supabase")
        
        response = client.from_("sets").select("set_id, name").execute()
        sets = response.data
        
        print_success(f"{len(sets)} sets in database")
        
        if not sets:
            print_error("No sets in database! Run fetch_cards.py first")
            return
        
        # Fetch prices by set
        print_step(3, "Fetching prices by set (with volume)")
        
        all_prices = []
        
        for i, set_data in enumerate(sets, 1):
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            prices, stats = fetch_prices_for_set(set_name, today, filter_rarity=True)
            
            if prices:
                all_prices.extend(prices)
                vol_info = f" | 📈 {stats.get('with_volume', 0)} with volume" if stats.get('with_volume', 0) > 0 else ""
                print(f"   ✅ {stats['filtered']}/{stats['total']} cards{vol_info}")
            else:
                print(f"   ⚠️ No prices (total: {stats['total']}, skipped: {stats['skipped']})")
            
            total_sets += 1
            total_skipped += stats.get("skipped", 0)
            total_with_volume += stats.get("with_volume", 0)
            total_volume += stats.get("total_volume", 0)
            
            # Aggregate skipped rarity stats
            for rarity, count in stats.get("skipped_rarities", {}).items():
                skipped_by_rarity[rarity] = skipped_by_rarity.get(rarity, 0) + count
            
            # Save in batches of 2000
            if len(all_prices) >= 2000:
                result = batch_upsert(client, "card_prices_daily", all_prices, 
                                      on_conflict="price_date,card_id")
                print(f"\n   💾 Batch saved: {result['saved']} prices")
                total_prices += result['saved']
                all_prices = []
            
            # Pause for rate limit
            time.sleep(0.5)
        
        # Last batch
        if all_prices:
            result = batch_upsert(client, "card_prices_daily", all_prices,
                                  on_conflict="price_date,card_id")
            print(f"\n   💾 Last batch: {result['saved']} prices")
            total_prices += result['saved']
        
        # Verification
        print_step(4, "Verification")
        
        response = client.from_("card_prices_daily") \
            .select("*", count="exact") \
            .eq("price_date", today) \
            .execute()
        print(f"   Prices today: {response.count}")

        # Top 5 by volume (NEW)
        response = client.from_("card_prices_daily") \
            .select("card_id, market_price, daily_volume, liquidity_score") \
            .eq("price_date", today) \
            .not_.is_("daily_volume", "null") \
            .order("daily_volume", desc=True) \
            .limit(5) \
            .execute()
        
        if response.data:
            print("\n   📈 Top 5 by sales volume:")
            for row in response.data:
                # Get card name
                card_resp = client.from_("cards").select("name").eq("card_id", row["card_id"]).execute()
                name = card_resp.data[0]["name"][:25] if card_resp.data else row["card_id"][:25]
                print(f"      {name:<25} | ${row['market_price']:>8.2f} | vol={row['daily_volume']:>3} | liq={row['liquidity_score']:.2f}")
        
        # Display skipped rarities
        if skipped_by_rarity:
            print("\n   📊 Excluded rarities:")
            for rarity, count in sorted(skipped_by_rarity.items(), key=lambda x: -x[1])[:5]:
                rarity_display = rarity if rarity else "(Empty)"
                print(f"      {rarity_display:<25} : {count:>5} cards")
        
        # Log success
        log_run_end(client, run_id, "success",
                    records_processed=total_prices,
                    details={
                        "sets": total_sets, 
                        "prices": total_prices,
                        "skipped": total_skipped,
                        "with_volume": total_with_volume,
                        "total_volume": total_volume,
                    })
        
        # Discord notification
        send_discord_notification(
            "✅ Fetch Prices - Success",
            f"{total_prices} prices fetched for {total_sets} sets.\n"
            f"📈 {total_with_volume} cards with volume ({total_volume} total sales)"
        )
        
        print()
        print_header("📊 SUMMARY")
        print(f"   Sets processed      : {total_sets}")
        print(f"   Prices fetched      : {total_prices}")
        print(f"   Cards with volume   : {total_with_volume}")
        print(f"   Total sales volume  : {total_volume}")
        print(f"   Cards excluded      : {total_skipped}")
        print()
        print_success("Script completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupt detected (Ctrl+C)")
        log_run_end(client, run_id, "interrupted", records_processed=total_prices)
        
    except Exception as e:
        print_error(f"Error: {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Fetch Prices - Failed",
            f"Error: {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()
