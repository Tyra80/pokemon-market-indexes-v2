"""
Pokemon Market Indexes v2 - Initialize Index (December 6th, 2025)
=================================================================
One-time script to initialize the indexes with base value 100.

This script:
1. Uses price data from 2025-12-06 (first daily data date)
2. Selects constituents using smart liquidity (B+C+D method)
3. Uses full history from 2025-10-13 for volume calculation (8 weeks of weekly data)
4. Sets base index value = 100 for all indexes
5. Saves constituents and initial index values

Run this ONCE after the backfill is complete.

Usage:
    python scripts_oneshot/initialize_index.py
"""

import sys
import os
from datetime import date

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification,
    print_header, print_step, print_success, print_error,
    calculate_liquidity_smart
)
from config.settings import INDEX_CONFIG, RARE_RARITIES, OUTLIER_RULES

# =============================================================================
# CONFIGURATION
# =============================================================================

# Index inception date (first date with complete daily data ~10k cards)
INCEPTION_DATE = "2025-12-08"
INCEPTION_MONTH = "2025-12-01"  # First day of month for constituents

# Base index value
BASE_VALUE = 100.0


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
            .select("card_id, name, set_id, rarity, is_eligible") \
            .eq("is_eligible", True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_cards.extend(response.data)
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    # Merge
    result = []
    for card in all_cards:
        card_id = card["card_id"]
        if card_id in prices_by_card:
            price_data = prices_by_card[card_id]
            ref_price = price_data.get("nm_price") or price_data.get("market_price")
            
            if ref_price and ref_price > 0:
                result.append({
                    "card_id": card_id,
                    "name": card["name"],
                    "set_id": card["set_id"],
                    "rarity": card["rarity"],
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


def calculate_ranking_score(card: dict) -> float:
    """Calculate ranking score: price × liquidity_score."""
    return card.get("price", 0) * card.get("liquidity_score", 0)


def select_constituents(cards: list, index_code: str, client=None, price_date: str = None) -> list:
    """
    Select constituents using the 50/30/20 liquidity formula.

    The liquidity score already includes:
    - 50% Volume (market activity)
    - 30% Listings (market presence)
    - 20% Consistency (trading regularity)

    No additional Method D filter needed - it's integrated in the score.

    Args:
        cards: List of cards to select from
        index_code: Index code (RARE_100, RARE_500, RARE_ALL)
        client: Supabase client
        price_date: Date for price data
    """
    config = INDEX_CONFIG.get(index_code, {})

    # Calculate liquidity for each card
    for card in cards:
        if client and price_date:
            smart_score, method = calculate_liquidity_smart(
                client,
                card["card_id"],
                price_date,
                nm_listings=card.get("nm_listings", 0),
                lp_listings=card.get("lp_listings", 0),
                mp_listings=card.get("mp_listings", 0),
                hp_listings=card.get("hp_listings", 0),
                dmg_listings=card.get("dmg_listings", 0),
            )
            card["liquidity_score"] = smart_score
            card["liquidity_method"] = method

        card["ranking_score"] = calculate_ranking_score(card)

    # Filter by liquidity threshold
    threshold = config.get("liquidity_threshold_entry", 0.40)
    eligible = [c for c in cards if c.get("liquidity_score", 0) >= threshold]

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
    print_header("🚀 Pokemon Market Indexes - INITIALIZATION")
    print(f"📅 Inception date: {INCEPTION_DATE}")
    print(f"📊 Liquidity formula: 50% Volume + 30% Listings + 20% Consistency")
    print(f"💯 Base value: {BASE_VALUE}")
    print()
    print("⚠️  This script should be run ONCE after backfill is complete!")
    print()
    
    # Confirmation
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
        # Check if prices exist for inception date
        print_step(2, "Checking price data")
        response = client.from_("card_prices_daily") \
            .select("card_id", count="exact") \
            .eq("price_date", INCEPTION_DATE) \
            .execute()
        
        if response.count == 0:
            print_error(f"No prices found for {INCEPTION_DATE}!")
            print("   Run the backfill first.")
            return
        
        print_success(f"{response.count} prices found for {INCEPTION_DATE}")
        
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
        
        for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
            print(f"\n   {'='*50}")
            print(f"   📈 {index_code}")
            print(f"   {'='*50}")
            
            # Select constituents
            print(f"   🔄 Selecting constituents (50/30/20 liquidity formula)...")
            constituents = select_constituents(
                rare_cards.copy(),
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
