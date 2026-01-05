"""
Pokemon Market Indexes v2 - Calculate Index History
===================================================
Calculates index values for each day from inception to today.

This script:
1. Starts from the inception date (2025-12-01, base 100)
2. Uses Laspeyres chain-linking to calculate each subsequent day
3. Handles monthly rebalancing automatically (on 1st of each month)

Run this AFTER initialize_index.py to fill historical values.
Can also be used to catch up on missing days.

Usage:
    python scripts/calculate_index_history.py                    # From inception to today
    python scripts/calculate_index_history.py --start 2025-12-15 # From specific date
    python scripts/calculate_index_history.py --end 2025-12-31   # To specific date
"""

import sys
import os
import argparse
from datetime import date, datetime, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification,
    print_header, print_step, print_success, print_error,
    calculate_liquidity_smart, get_avg_volume_30d
)
from config.settings import INDEX_CONFIG, RARE_RARITIES, OUTLIER_RULES, MIN_AVG_VOLUME_30D

# =============================================================================
# CONFIGURATION
# =============================================================================

INCEPTION_DATE = "2025-12-01"
BASE_VALUE = 100.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_first_of_month(d: date) -> str:
    """Return first day of the month for given date."""
    return d.replace(day=1).strftime("%Y-%m-%d")


def get_dates_with_prices(client, start_date: str, end_date: str) -> list:
    """Get all dates that have price data in the given range (with pagination)."""
    all_dates = []
    offset = 0
    limit = 1000
    
    while True:
        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .gte("price_date", start_date) \
            .lte("price_date", end_date) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_dates.extend([row["price_date"] for row in response.data])
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    # Get unique dates and sort
    dates = sorted(set(all_dates))
    return dates


def get_prices_for_date(client, card_ids: list, price_date: str) -> dict:
    """Get NM prices for a list of cards at a given date."""
    if not card_ids:
        return {}
    
    prices = {}
    batch_size = 100
    
    for i in range(0, len(card_ids), batch_size):
        batch_ids = card_ids[i:i + batch_size]
        
        response = client.from_("card_prices_daily") \
            .select("card_id, nm_price, market_price") \
            .eq("price_date", price_date) \
            .in_("card_id", batch_ids) \
            .execute()
        
        for row in response.data:
            price = row.get("nm_price") or row.get("market_price")
            if price:
                prices[row["card_id"]] = float(price)
    
    return prices


def get_constituents_for_month(client, index_code: str, month: str) -> list:
    """Get constituents for a given index and month (with pagination)."""
    all_constituents = []
    offset = 0
    limit = 1000
    
    while True:
        response = client.from_("constituents_monthly") \
            .select("item_id, weight, composite_price") \
            .eq("index_code", index_code) \
            .eq("month", month) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_constituents.extend(response.data)
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    return [{
        "card_id": row["item_id"],
        "weight": float(row["weight"]) if row["weight"] else 0,
        "price": float(row["composite_price"]) if row["composite_price"] else 0,
    } for row in all_constituents]


def get_previous_index_value(client, index_code: str, before_date: str) -> tuple:
    """Get the most recent index value before the given date."""
    response = client.from_("index_values_daily") \
        .select("index_value, value_date") \
        .eq("index_code", index_code) \
        .lt("value_date", before_date) \
        .order("value_date", desc=True) \
        .limit(1) \
        .execute()
    
    if response.data:
        return float(response.data[0]["index_value"]), response.data[0]["value_date"]
    return None, None


def calculate_laspeyres_value(client, index_code: str, constituents: list,
                               prev_value: float, prev_date: str, current_date: str) -> tuple:
    """
    Calculate new index value using Laspeyres method.
    
    Returns: (new_value, details_dict)
    """
    if not constituents:
        return prev_value, {"method": "no_constituents"}
    
    # Get current prices
    card_ids = [c["card_id"] for c in constituents]
    current_prices = get_prices_for_date(client, card_ids, current_date)
    
    # Get previous prices (for the constituents)
    prev_prices = get_prices_for_date(client, card_ids, prev_date)
    
    # Calculate Laspeyres ratio
    numerator = 0.0    # Σ(w_i × P_i,t)
    denominator = 0.0  # Σ(w_i × P_i,t-1)
    matched_count = 0
    
    for c in constituents:
        card_id = c["card_id"]
        weight = c["weight"]
        
        if card_id in current_prices and card_id in prev_prices:
            current_price = current_prices[card_id]
            prev_price = prev_prices[card_id]
            
            if prev_price > 0:
                numerator += weight * current_price
                denominator += weight * prev_price
                matched_count += 1
    
    # Calculate
    if denominator > 0 and matched_count >= len(constituents) * 0.5:
        ratio = numerator / denominator
        new_value = prev_value * ratio
        change_pct = (ratio - 1) * 100
        
        return round(new_value, 4), {
            "method": "laspeyres",
            "matched": matched_count,
            "total": len(constituents),
            "ratio": round(ratio, 6),
            "change_pct": round(change_pct, 4),
        }
    else:
        # Not enough data - keep previous value
        return prev_value, {
            "method": "insufficient_data",
            "matched": matched_count,
            "total": len(constituents),
        }


def save_index_value(client, index_code: str, value_date: str, index_value: float,
                     n_constituents: int, market_cap: float = None) -> bool:
    """Save index value to database."""
    try:
        data = {
            "index_code": index_code,
            "value_date": value_date,
            "index_value": round(index_value, 4),
            "n_constituents": n_constituents,
        }
        if market_cap:
            data["total_market_cap"] = round(market_cap, 2)
        
        client.from_("index_values_daily").upsert(
            data, on_conflict="index_code,value_date"
        ).execute()
        return True
    except Exception as e:
        print(f"      ❌ Save error: {e}")
        return False


# =============================================================================
# REBALANCING
# =============================================================================

def get_cards_with_prices(client, price_date: str) -> list:
    """Get all eligible cards with prices for rebalancing (with pagination)."""
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
                    "liquidity_score": float(price_data.get("liquidity_score") or 0),
                    "nm_listings": int(price_data.get("nm_listings") or 0),
                    "lp_listings": int(price_data.get("lp_listings") or 0),
                    "mp_listings": int(price_data.get("mp_listings") or 0),
                    "hp_listings": int(price_data.get("hp_listings") or 0),
                    "dmg_listings": int(price_data.get("dmg_listings") or 0),
                })
    
    return result


def do_rebalancing(client, index_code: str, month: str, price_date: str) -> list:
    """Perform rebalancing for an index."""
    config = INDEX_CONFIG.get(index_code, {})
    
    # Get all cards with prices
    all_cards = get_cards_with_prices(client, price_date)
    
    # Filter rare cards
    cards = [c for c in all_cards if c.get("rarity") in RARE_RARITIES]
    
    # Filter outliers
    min_price = OUTLIER_RULES.get("min_price", 0.10)
    max_price = OUTLIER_RULES.get("max_price", 100000)
    cards = [c for c in cards if min_price <= c.get("price", 0) <= max_price]
    
    # Calculate liquidity and ranking
    for card in cards:
        smart_score, method = calculate_liquidity_smart(
            client, card["card_id"], price_date,
            nm_listings=card.get("nm_listings", 0),
            lp_listings=card.get("lp_listings", 0),
            mp_listings=card.get("mp_listings", 0),
            hp_listings=card.get("hp_listings", 0),
            dmg_listings=card.get("dmg_listings", 0),
        )
        card["liquidity_score"] = smart_score
        card["liquidity_method"] = method
        card["ranking_score"] = card["price"] * card["liquidity_score"]
    
    # Filter by liquidity threshold
    threshold = config.get("liquidity_threshold_entry", 0.40)
    eligible = [c for c in cards if c.get("liquidity_score", 0) >= threshold]
    
    # Sort by ranking score
    eligible.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)
    
    # Select top N
    size = config.get("size")
    if size:
        constituents = eligible[:size]
    else:
        constituents = eligible
    
    # Calculate weights
    total_price = sum(c.get("price", 0) for c in constituents)
    for c in constituents:
        c["weight"] = c.get("price", 0) / total_price if total_price > 0 else 0
    
    # Save constituents
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
    
    batch_upsert(client, "constituents_monthly", rows, on_conflict="index_code,month,item_id")
    
    return constituents


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default=None,
                        help="Start date (YYYY-MM-DD), default: day after last calculated")
    parser.add_argument("--end", type=str, default=None,
                        help="End date (YYYY-MM-DD), default: today")
    args = parser.parse_args()
    
    print_header("📈 Pokemon Market Indexes - Calculate History")
    print(f"📅 Inception: {INCEPTION_DATE}")
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
    run_id = log_run_start(client, "calculate_index_history")
    
    try:
        # Determine date range
        print_step(2, "Determining date range")
        
        # End date
        end_date = args.end if args.end else date.today().strftime("%Y-%m-%d")
        
        # Start date
        if args.start:
            start_date = args.start
        else:
            # Find last calculated date
            response = client.from_("index_values_daily") \
                .select("value_date") \
                .order("value_date", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data:
                last_date = datetime.strptime(response.data[0]["value_date"], "%Y-%m-%d").date()
                start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                # No data - start from inception + 1
                start_date = (datetime.strptime(INCEPTION_DATE, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"   Start date: {start_date}")
        print(f"   End date: {end_date}")
        
        if start_date > end_date:
            print_success("Index is up to date!")
            return
        
        # Get dates with price data
        print_step(3, "Finding dates with price data")
        price_dates = get_dates_with_prices(client, start_date, end_date)
        print_success(f"{len(price_dates)} dates with price data")
        
        if not price_dates:
            print("   No price data for this period.")
            return
        
        # Process each date
        print_step(4, "Calculating index values")
        
        processed = 0
        current_month = None
        
        for calc_date in price_dates:
            calc_date_obj = datetime.strptime(calc_date, "%Y-%m-%d").date()
            month = get_first_of_month(calc_date_obj)
            
            print(f"\n   📅 {calc_date}")
            
            # Check if new month (need rebalancing)
            is_new_month = (month != current_month)
            if is_new_month and calc_date != INCEPTION_DATE:
                print(f"      🔄 New month: {month} - Rebalancing...")
            
            current_month = month
            
            # Process each index
            for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
                # Get constituents for current month
                constituents = get_constituents_for_month(client, index_code, month)
                
                # If no constituents for this month, do rebalancing
                if not constituents and is_new_month:
                    constituents = do_rebalancing(client, index_code, month, calc_date)
                    print(f"      ✅ {index_code}: {len(constituents)} constituents rebalanced")
                
                if not constituents:
                    print(f"      ⚠️ {index_code}: No constituents")
                    continue
                
                # Get previous value
                prev_value, prev_date = get_previous_index_value(client, index_code, calc_date)
                
                if prev_value is None:
                    # No previous value - this should be handled by initialize_index.py
                    print(f"      ⚠️ {index_code}: No previous value (run initialize_index.py first)")
                    continue
                
                # Calculate new value
                new_value, details = calculate_laspeyres_value(
                    client, index_code, constituents,
                    prev_value, prev_date, calc_date
                )
                
                # Save
                market_cap = sum(c.get("price", 0) for c in constituents)
                save_index_value(client, index_code, calc_date, new_value, len(constituents), market_cap)
                
                # Display
                change_str = ""
                if details.get("change_pct") is not None:
                    change = details["change_pct"]
                    arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    change_str = f" {arrow} {change:+.2f}%"
                
                print(f"      {index_code}: {new_value:.2f}{change_str}")
            
            processed += 1
        
        # Final summary
        print_step(5, "Summary")
        
        response = client.from_("index_values_daily") \
            .select("*") \
            .order("value_date", desc=True) \
            .limit(9) \
            .execute()
        
        print("\n   📊 Latest values:")
        for row in response.data:
            print(f"      {row['index_code']:<10} | {row['value_date']} | {row['index_value']:>8.2f} | {row['n_constituents']} cards")
        
        # Log success
        log_run_end(client, run_id, "success", records_processed=processed)
        
        # Discord notification
        send_discord_notification(
            "✅ Index History Calculation - Success",
            f"Calculated {processed} days from {start_date} to {end_date}"
        )
        
        print()
        print_header("📊 CALCULATION COMPLETE")
        print(f"   Days processed: {processed}")
        print(f"   Date range: {start_date} to {end_date}")
        print()
        print_success("History calculation completed!")
        
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        log_run_end(client, run_id, "failed", error_message=str(e))
        raise


if __name__ == "__main__":
    main()