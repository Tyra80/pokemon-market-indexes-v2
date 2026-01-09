"""
Pokemon Market Indexes v2 - Initialize Index (December 8th, 2025)
=================================================================
One-time script to initialize the indexes with base value 100.

This script:
1. Uses price data from 2025-12-08 (first day with complete daily data from PPT API)
2. Selects constituents using smart liquidity (B+C+D method)
3. Uses 8 weekly data points (Oct 13 - Dec 1) + Dec 8 daily for Method D
4. Sets base index value = 100 for all indexes
5. Saves constituents and initial index values

First publication: Dec 10, 2025 (J-2 strategy)

Run this ONCE after the backfill is complete.

Usage:
    python scripts_oneshot/initialize_index.py
"""

import sys
import os
from datetime import date, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification,
    print_header, print_step, print_success, print_error,
)
from config.settings import INDEX_CONFIG, RARE_RARITIES, OUTLIER_RULES, INCEPTION_DATE, MIN_AVG_VOLUME_30D

# =============================================================================
# CONFIGURATION
# =============================================================================

# First day of month for constituents (derived from INCEPTION_DATE)
INCEPTION_MONTH = INCEPTION_DATE[:8] + "01"  # "2025-12-01"

# Base index value
BASE_VALUE = 100.0

# Method D configuration for initialization
# We use 8 weekly data points (Oct 13 - Dec 1) + Dec 8 daily data
# This gives us 9 data points spanning ~57 days
# Criteria: avg_volume >= 0.5/day AND days_with_volume >= 3
WEEKLY_DATA_START = "2025-10-13"  # First weekly data point
WEEKLY_DATA_POINTS = 9            # 8 weekly + 1 daily (Dec 8)
WEEKLY_MIN_DAYS_WITH_VOLUME = 3   # Minimum data points with volume


# =============================================================================
# DATA LOADING (same as calculate_index.py)
# =============================================================================

def get_cards_with_prices(client, price_date: str) -> list:
    """Get all cards with their NM prices for the specified date."""
    all_prices = []
    offset = 0
    limit = 1000
    
    while True:
        response = client.from_("card_prices_daily") \
            .select("card_id, market_price, nm_price, nm_listings, lp_listings, mp_listings, hp_listings, dmg_listings, total_listings, daily_volume, liquidity_score") \
            .eq("price_date", price_date) \
            .not_.is_("nm_price", "null") \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_prices.extend(response.data)
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    prices_by_card = {p["card_id"]: p for p in all_prices}
    
    # Get ALL eligible cards
    all_cards = []
    offset = 0

    while True:
        response = client.from_("cards") \
            .select("card_id, name, set_id, rarity, is_eligible, release_date") \
            .eq("is_eligible", True) \
            .range(offset, offset + limit - 1) \
            .execute()

        if not response.data:
            break

        all_cards.extend(response.data)

        if len(response.data) < limit:
            break

        offset += limit

    # Get set release dates for cards without release_date
    set_ids = list(set(c.get("set_id") for c in all_cards if c.get("set_id")))
    sets_response = client.from_("sets") \
        .select("set_id, release_date") \
        .in_("set_id", set_ids) \
        .execute()

    sets_release_dates = {s["set_id"]: s.get("release_date") for s in (sets_response.data or [])}

    # Merge
    result = []
    for card in all_cards:
        card_id = card["card_id"]
        if card_id in prices_by_card:
            price_data = prices_by_card[card_id]
            ref_price = price_data.get("nm_price") or price_data.get("market_price")

            if ref_price and ref_price > 0:
                # Get release date: card's own date, or fallback to set's date
                card_release_date = card.get("release_date")
                if not card_release_date:
                    card_release_date = sets_release_dates.get(card.get("set_id"))

                result.append({
                    "card_id": card_id,
                    "name": card["name"],
                    "set_id": card["set_id"],
                    "rarity": card["rarity"],
                    "release_date": card_release_date,
                    "price": float(ref_price),
                    "market_price": float(price_data.get("market_price") or ref_price),
                    "liquidity_score": float(price_data.get("liquidity_score") or 0),
                    "daily_volume": price_data.get("daily_volume"),
                    "nm_listings": int(price_data.get("nm_listings") or 0),
                    "lp_listings": int(price_data.get("lp_listings") or 0),
                    "mp_listings": int(price_data.get("mp_listings") or 0),
                    "hp_listings": int(price_data.get("hp_listings") or 0),
                    "dmg_listings": int(price_data.get("dmg_listings") or 0),
                    "total_listings": int(price_data.get("total_listings") or 0),
                })

    return result


def filter_rare_cards(cards: list) -> list:
    """Filter cards with rarity >= Rare."""
    return [c for c in cards if c.get("rarity") in RARE_RARITIES]


def filter_outliers(cards: list) -> list:
    """Filter outliers according to defined rules."""
    min_price = OUTLIER_RULES.get("min_price", 0.10)
    max_price = OUTLIER_RULES.get("max_price", 100000)
    return [c for c in cards if min_price <= c.get("price", 0) <= max_price]


def filter_immature_cards(cards: list, index_code: str, reference_date: str) -> list:
    """
    Filter cards from sets that are too recent (not yet mature).

    A set must be released at least `maturity_days` days before the reference_date
    to be eligible for the index.

    Args:
        cards: List of cards to filter
        index_code: Index code to get maturity_days from config
        reference_date: Date to check maturity against (YYYY-MM-DD)

    Returns:
        List of cards that meet the maturity requirement
    """
    config = INDEX_CONFIG.get(index_code, {})
    maturity_days = config.get("maturity_days", 30)

    if maturity_days <= 0:
        return cards

    ref_date = date.fromisoformat(reference_date)
    cutoff_date = ref_date - timedelta(days=maturity_days)

    mature_cards = []
    immature_count = 0

    for card in cards:
        release_date_str = card.get("release_date")
        if not release_date_str:
            # No release date = assume mature (conservative)
            mature_cards.append(card)
            continue

        try:
            release_date = date.fromisoformat(release_date_str)
            if release_date <= cutoff_date:
                mature_cards.append(card)
            else:
                immature_count += 1
        except (ValueError, TypeError):
            # Invalid date format = assume mature
            mature_cards.append(card)

    if immature_count > 0:
        print(f"   Filtered {immature_count} immature cards (released after {cutoff_date})")

    return mature_cards


def calculate_ranking_score(card: dict) -> float:
    """Calculate ranking score: price × liquidity_score."""
    return card.get("price", 0) * card.get("liquidity_score", 0)


def batch_get_volume_stats(client, card_ids: list, start_date: str, end_date: str,
                           min_days: int = 3, avg_divisor: int = 9) -> dict:
    """
    Batch fetch volume stats for all cards in one query.
    Much faster than individual queries for initialization.

    Returns:
        dict: {card_id: {'avg_volume': float, 'days_with_volume': int, 'is_liquid': bool, 'total_volume': float}}
    """
    from config.settings import CONDITION_WEIGHTS

    # Fetch ALL volume data for the period in one paginated query
    all_volumes = []
    offset = 0
    limit = 1000

    print(f"   📥 Fetching volume data from {start_date} to {end_date}...")

    while True:
        response = client.from_("card_prices_daily") \
            .select("card_id, nm_volume, lp_volume, mp_volume, hp_volume, dmg_volume") \
            .gte("price_date", start_date) \
            .lte("price_date", end_date) \
            .range(offset, offset + limit - 1) \
            .execute()

        if not response.data:
            break

        all_volumes.extend(response.data)

        if len(response.data) < limit:
            break

        offset += limit

    print(f"   📊 Processing {len(all_volumes)} volume records...")

    # Group by card_id and calculate stats
    card_volumes = {}
    for row in all_volumes:
        card_id = row["card_id"]
        if card_id not in card_volumes:
            card_volumes[card_id] = []

        # Calculate weighted volume for this day
        nm_vol = (row.get("nm_volume") or 0) * CONDITION_WEIGHTS["Near Mint"]
        lp_vol = (row.get("lp_volume") or 0) * CONDITION_WEIGHTS["Lightly Played"]
        mp_vol = (row.get("mp_volume") or 0) * CONDITION_WEIGHTS["Moderately Played"]
        hp_vol = (row.get("hp_volume") or 0) * CONDITION_WEIGHTS["Heavily Played"]
        dmg_vol = (row.get("dmg_volume") or 0) * CONDITION_WEIGHTS["Damaged"]
        weighted_vol = nm_vol + lp_vol + mp_vol + hp_vol + dmg_vol

        card_volumes[card_id].append(weighted_vol)

    # Calculate stats for each card
    results = {}
    for card_id in card_ids:
        volumes = card_volumes.get(card_id, [])
        total_volume = sum(volumes)
        days_with_volume = sum(1 for v in volumes if v > 0)
        avg_volume = total_volume / avg_divisor if avg_divisor > 0 else 0
        n_days = len(volumes) if volumes else avg_divisor

        results[card_id] = {
            'avg_volume': avg_volume,
            'days_with_volume': days_with_volume,
            'is_liquid': days_with_volume >= min_days,
            'total_volume': total_volume,
            'consistency': days_with_volume / n_days if n_days > 0 else 0,
        }

    return results


def calculate_liquidity_batch(cards: list, volume_stats: dict) -> None:
    """
    Calculate liquidity scores for all cards using pre-fetched volume data.
    Much faster than individual queries.

    Modifies cards in place, adding 'liquidity_score' and 'liquidity_method'.
    """
    from config.settings import CONDITION_WEIGHTS, LIQUIDITY_CAP, VOLUME_CAP, LIQUIDITY_WEIGHTS

    W_VOL = LIQUIDITY_WEIGHTS.get("volume", 0.50)
    W_LIST = LIQUIDITY_WEIGHTS.get("listings", 0.30)
    W_CONS = LIQUIDITY_WEIGHTS.get("consistency", 0.20)

    for card in cards:
        card_id = card["card_id"]
        vol_stats = volume_stats.get(card_id, {})

        # Calculate listings score (always available)
        weighted_listings = (
            (card.get("nm_listings") or 0) * CONDITION_WEIGHTS["Near Mint"] +
            (card.get("lp_listings") or 0) * CONDITION_WEIGHTS["Lightly Played"] +
            (card.get("mp_listings") or 0) * CONDITION_WEIGHTS["Moderately Played"] +
            (card.get("hp_listings") or 0) * CONDITION_WEIGHTS["Heavily Played"] +
            (card.get("dmg_listings") or 0) * CONDITION_WEIGHTS["Damaged"]
        )
        listings_score = min(weighted_listings / LIQUIDITY_CAP, 1.0)

        # Check if we have volume data
        avg_volume = vol_stats.get('avg_volume', 0)
        consistency = vol_stats.get('consistency', 0)

        if avg_volume > 0 or consistency > 0:
            # Combined method
            volume_score = min(avg_volume / VOLUME_CAP, 1.0)
            liquidity_score = (W_VOL * volume_score) + (W_LIST * listings_score) + (W_CONS * consistency)
            method = "combined"
        else:
            # Listings only fallback
            liquidity_score = listings_score
            method = "listings_only"

        card["liquidity_score"] = round(liquidity_score, 4)
        card["liquidity_method"] = method


def select_constituents(cards: list, index_code: str, client=None, price_date: str = None) -> list:
    """
    Select constituents for index initialization.

    Selection methodology:
    1. Batch fetch all volume data (much faster than individual queries)
    2. Calculate liquidity score for each card (B+C method)
    3. Filter by Method D
    4. Calculate ranking_score = price × liquidity
    5. Sort by ranking_score and take top N

    Args:
        cards: List of cards to select from
        index_code: Index code (RARE_100, RARE_500, RARE_5000)
        client: Supabase client
        price_date: Date for price data
    """
    config = INDEX_CONFIG.get(index_code, {})

    # Batch fetch all volume stats at once (much faster than individual queries)
    volume_stats = {}
    if client and price_date:
        card_ids = [c["card_id"] for c in cards]
        volume_stats = batch_get_volume_stats(
            client,
            card_ids,
            start_date=WEEKLY_DATA_START,
            end_date=price_date,
            min_days=WEEKLY_MIN_DAYS_WITH_VOLUME,
            avg_divisor=WEEKLY_DATA_POINTS
        )

        # Calculate liquidity using batch data (no individual queries)
        print(f"   🔢 Calculating liquidity scores for {len(cards)} cards...")
        calculate_liquidity_batch(cards, volume_stats)

    # Calculate ranking score for all cards
    for card in cards:
        card["ranking_score"] = calculate_ranking_score(card)

    # Filter by Method D using pre-fetched volume stats
    eligible = []
    if client and price_date:
        for card in cards:
            vol_stats = volume_stats.get(card["card_id"], {
                'avg_volume': 0, 'days_with_volume': 0, 'is_liquid': False
            })
            card["avg_volume_30d"] = vol_stats['avg_volume']
            card["days_with_volume"] = vol_stats['days_with_volume']

            no_volume_data = vol_stats['days_with_volume'] == 0
            has_sufficient_volume = vol_stats['avg_volume'] >= MIN_AVG_VOLUME_30D
            has_regular_trading = vol_stats['is_liquid']  # >= WEEKLY_MIN_DAYS_WITH_VOLUME

            if no_volume_data:
                # No volume data - keep only if using listings fallback
                if card.get("liquidity_method") == "listings_only":
                    eligible.append(card)
            elif has_sufficient_volume and has_regular_trading:
                # Passes Method D
                eligible.append(card)
    else:
        # No client - use all cards with positive liquidity
        eligible = [c for c in cards if c.get("liquidity_score", 0) > 0]

    # Sort by ranking score (price × liquidity)
    eligible.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)

    # Select top N
    size = config.get("size")
    if size:
        return eligible[:size]
    else:
        return eligible


def calculate_weights(constituents: list) -> list:
    """
    Calculate weights for each constituent.
    Method: Liquidity-Adjusted Price-Weighted
    weight_i = (price_i × liquidity_i) / Σ(price × liquidity)

    This reduces the impact of expensive but illiquid cards,
    making the index more robust to noise.
    """
    # Calculate adjusted values (price × liquidity)
    for c in constituents:
        liquidity = c.get("liquidity_score", 0) or 0.1  # Floor at 0.1 to avoid zero
        c["adjusted_value"] = c.get("price", 0) * liquidity

    total_adjusted = sum(c.get("adjusted_value", 0) for c in constituents)

    if total_adjusted == 0:
        equal_weight = 1.0 / len(constituents) if constituents else 0
        for c in constituents:
            c["weight"] = equal_weight
        return constituents

    for c in constituents:
        c["weight"] = c.get("adjusted_value", 0) / total_adjusted

    return constituents


def save_constituents(client, index_code: str, month: str, constituents: list) -> int:
    """Save monthly constituents."""
    if not constituents:
        return 0
    
    rows = []
    for i, c in enumerate(constituents, 1):
        rows.append({
            "index_code": index_code,
            "month": month,
            "item_type": "card",
            "item_id": c["card_id"],
            "composite_price": round(c.get("price", 0), 2),
            "liquidity_score": round(c.get("liquidity_score", 0), 4),
            "ranking_score": round(c.get("ranking_score", 0), 4),
            "rank": i,
            "weight": round(c.get("weight", 0), 8),
            "is_new": True,
        })
    
    result = batch_upsert(
        client,
        "constituents_monthly",
        rows,
        on_conflict="index_code,month,item_id"
    )
    
    return result["saved"]


def save_index_value(client, index_code: str, value_date: str, index_value: float,
                     n_constituents: int, market_cap: float) -> bool:
    """Save initial index value."""
    try:
        client.from_("index_values_daily").upsert({
            "index_code": index_code,
            "value_date": value_date,
            "index_value": round(index_value, 4),
            "n_constituents": n_constituents,
            "total_market_cap": round(market_cap, 2),
            "change_1w": None,
            "change_1m": None,
        }, on_conflict="index_code,value_date").execute()
        return True
    except Exception as e:
        print(f"   ❌ Save error: {e}")
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print_header("🚀 Pokemon Market Indexes - INITIALIZATION")
    print(f"📅 Inception date: {INCEPTION_DATE}")
    print(f"📊 Liquidity formula: 50% Volume + 30% Listings + 20% Consistency")
    print(f"💯 Base value: {BASE_VALUE}")
    print()
    print("⚠️  This script should be run ONCE after backfill is complete!")
    print()

    # Confirmation
    if not args.yes:
        confirm = input("Are you sure you want to initialize the indexes? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return
    
    # Connection
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # Log run
    run_id = log_run_start(client, "initialize_index")
    
    try:
        # Check if prices exist for inception date (quick check without count)
        print_step(2, "Checking price data")
        response = client.from_("card_prices_daily") \
            .select("card_id") \
            .eq("price_date", INCEPTION_DATE) \
            .limit(1) \
            .execute()

        if not response.data:
            print_error(f"No prices found for {INCEPTION_DATE}!")
            print("   Run the backfill first.")
            return

        print_success(f"Prices found for {INCEPTION_DATE}")
        
        # Load cards with prices
        print_step(3, "Loading card data")
        all_cards = get_cards_with_prices(client, INCEPTION_DATE)
        print_success(f"{len(all_cards)} cards with NM prices")
        
        # Filter
        rare_cards = filter_rare_cards(all_cards)
        print(f"   Rare cards (>= Rare): {len(rare_cards)}")
        
        rare_cards = filter_outliers(rare_cards)
        print(f"   After outlier filter: {len(rare_cards)}")
        
        if not rare_cards:
            print_error("No eligible cards!")
            return
        
        # Initialize each index
        print_step(4, "Initializing indexes")
        
        results = {}
        
        for index_code in ["RARE_100", "RARE_500", "RARE_5000"]:
            print(f"\n   {'='*50}")
            print(f"   📈 {index_code}")
            print(f"   {'='*50}")
            
            # Filter immature cards (sets released too recently)
            mature_cards = filter_immature_cards(rare_cards.copy(), index_code, INCEPTION_DATE)

            # Select constituents
            print(f"   🔄 Selecting constituents (50/30/20 liquidity formula)...")
            constituents = select_constituents(
                mature_cards,
                index_code,
                client=client,
                price_date=INCEPTION_DATE
            )

            if not constituents:
                print(f"   ⚠️ No constituents found!")
                continue

            # Stats
            combined_count = sum(1 for c in constituents if c.get("liquidity_method") == "combined")
            listings_only_count = sum(1 for c in constituents if c.get("liquidity_method") == "listings_only")
            print(f"   📊 Liquidity methods: {combined_count} combined | {listings_only_count} listings_only")
            
            # Calculate weights
            constituents = calculate_weights(constituents)
            
            # Save constituents
            saved = save_constituents(client, index_code, INCEPTION_MONTH, constituents)
            print(f"   ✅ {saved} constituents saved")
            
            # Calculate market cap
            market_cap = sum(c.get("price", 0) for c in constituents)
            
            # Save initial index value (BASE = 100)
            save_index_value(
                client, index_code, INCEPTION_DATE,
                BASE_VALUE, len(constituents), market_cap
            )
            print(f"   ✅ Index value: {BASE_VALUE} (base)")
            print(f"   💰 Market cap: ${market_cap:,.2f}")
            
            # Top 5
            print(f"\n   📋 Top 5 constituents:")
            for i, c in enumerate(constituents[:5], 1):
                name = c.get('name', 'Unknown')[:30]
                price = c.get('price', 0)
                liq = c.get('liquidity_score', 0)
                weight = c.get('weight', 0) * 100
                print(f"      {i}. {name:<30} ${price:>8.2f} | liq={liq:.2f} | w={weight:.2f}%")
            
            results[index_code] = {
                "value": BASE_VALUE,
                "constituents": len(constituents),
                "market_cap": market_cap,
            }
        
        # Verification
        print_step(5, "Verification")
        
        response = client.from_("index_values_daily") \
            .select("*") \
            .eq("value_date", INCEPTION_DATE) \
            .execute()
        
        print("\n   📊 Initial index values:")
        for row in response.data:
            print(f"      {row['index_code']:<10} | {row['value_date']} | {row['index_value']:>8.2f} | {row['n_constituents']} cards")
        
        # Log success
        log_run_end(client, run_id, "success", records_processed=len(results), details=results)
        
        # Discord notification
        summary_lines = []
        for code, data in results.items():
            summary_lines.append(f"• {code}: {data['constituents']} constituents, ${data['market_cap']:,.0f} market cap")
        
        send_discord_notification(
            "🚀 Index Initialization - Success",
            f"Indexes initialized at {INCEPTION_DATE} with base value {BASE_VALUE}:\n" + "\n".join(summary_lines)
        )
        
        # Final summary
        print()
        print_header("🎉 INITIALIZATION COMPLETE")
        print(f"   Inception date: {INCEPTION_DATE}")
        print(f"   Base value: {BASE_VALUE}")
        for code, data in results.items():
            print(f"   {code}: {data['constituents']} constituents | ${data['market_cap']:,.0f}")
        print()
        print_success("Indexes successfully initialized!")
        print()
        print("Next step: Run calculate_index_history.py to calculate daily values")
        
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        log_run_end(client, run_id, "failed", error_message=str(e))
        raise


if __name__ == "__main__":
    main()
