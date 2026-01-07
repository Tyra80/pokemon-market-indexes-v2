"""
Pokemon Market Indexes v2 - Check Data Availability
====================================================
Checks price and volume data availability since December 1st, 2025.

Run this BEFORE initialize_index.py to ensure data is ready.

Usage:
    python scripts_oneshot/data_check.py
"""

import sys
import os
from datetime import datetime, date, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_db_client, print_header, print_step, print_success, print_error
from config.settings import INCEPTION_DATE

# =============================================================================
# CONFIGURATION
# =============================================================================

START_DATE = "2025-12-01"  # Start checking from this date (before inception)
END_DATE = date.today().strftime("%Y-%m-%d")


def main():
    print_header("🔍 Pokemon Market Indexes - Check Data Availability")
    print(f"📅 Checking from {START_DATE} to {END_DATE}")
    print()
    
    # Connection
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # ==========================================================================
    # CHECK 1: Dates with price data (with pagination)
    # ==========================================================================
    print_step(2, "Checking dates with price data")
    
    # Paginate to get ALL dates (Supabase limits to 1000 rows)
    all_price_dates = []
    offset = 0
    limit = 1000
    
    while True:
        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .gte("price_date", START_DATE) \
            .lte("price_date", END_DATE) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_price_dates.extend([row["price_date"] for row in response.data])
        
        if len(response.data) < limit:
            break
        
        offset += limit
        print(f"   ... fetched {offset} rows")
    
    # Get unique dates
    dates_with_prices = sorted(set(all_price_dates))
    
    print(f"   📊 {len(dates_with_prices)} dates with price data")
    
    if dates_with_prices:
        print(f"   📅 First date: {dates_with_prices[0]}")
        print(f"   📅 Last date: {dates_with_prices[-1]}")
    
    # ==========================================================================
    # CHECK 2: Cards per date
    # ==========================================================================
    print_step(3, "Checking cards per date")
    
    print("\n   Date         | Cards   | With NM  | With Volume | Avg Volume")
    print("   " + "-" * 65)
    
    dates_summary = []
    
    for price_date in dates_with_prices:
        # Total cards (use count to avoid pagination issues)
        response = client.from_("card_prices_daily") \
            .select("card_id", count="exact") \
            .eq("price_date", price_date) \
            .limit(1) \
            .execute()
        total_cards = response.count or 0
        
        # Cards with NM price
        response = client.from_("card_prices_daily") \
            .select("card_id", count="exact") \
            .eq("price_date", price_date) \
            .not_.is_("nm_price", "null") \
            .limit(1) \
            .execute()
        with_nm = response.count or 0
        
        # Cards with volume > 0
        response = client.from_("card_prices_daily") \
            .select("card_id", count="exact") \
            .eq("price_date", price_date) \
            .not_.is_("daily_volume", "null") \
            .gt("daily_volume", 0) \
            .limit(1) \
            .execute()
        with_volume = response.count or 0
        
        # Average volume (sample 1000 cards with volume)
        response = client.from_("card_prices_daily") \
            .select("daily_volume") \
            .eq("price_date", price_date) \
            .not_.is_("daily_volume", "null") \
            .gt("daily_volume", 0) \
            .limit(1000) \
            .execute()
        
        if response.data:
            volumes = [r["daily_volume"] for r in response.data if r["daily_volume"]]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
        else:
            avg_volume = 0
        
        dates_summary.append({
            "date": price_date,
            "total": total_cards,
            "with_nm": with_nm,
            "with_volume": with_volume,
            "avg_volume": avg_volume,
        })
        
        # Status indicator
        status = "✅" if with_nm > 1000 else "⚠️" if with_nm > 0 else "❌"
        
        print(f"   {status} {price_date} | {total_cards:>6} | {with_nm:>7} | {with_volume:>10} | {avg_volume:>10.1f}")
    
    # ==========================================================================
    # CHECK 3: Eligible cards (rarity >= Rare)
    # ==========================================================================
    print_step(4, "Checking eligible cards")
    
    response = client.from_("cards") \
        .select("card_id", count="exact") \
        .eq("is_eligible", True) \
        .execute()
    
    eligible_cards = response.count
    print(f"   🃏 Total eligible cards (>= Rare): {eligible_cards}")
    
    # Check for inception date specifically
    print_step(5, f"Checking inception date ({INCEPTION_DATE})")

    if INCEPTION_DATE in dates_with_prices:
        inception_data = next((d for d in dates_summary if d["date"] == INCEPTION_DATE), None)
        if inception_data:
            print(f"   ✅ Inception date has data:")
            print(f"      - Total cards: {inception_data['total']}")
            print(f"      - With NM price: {inception_data['with_nm']}")
            print(f"      - With volume: {inception_data['with_volume']}")

            if inception_data['with_nm'] >= 1000:
                print_success(f"Ready to initialize index!")
            else:
                print_error(f"Not enough cards with NM price (need >= 1000)")
    else:
        print_error(f"No data for inception date {INCEPTION_DATE}!")
    
    # ==========================================================================
    # CHECK 4: Missing dates
    # ==========================================================================
    print_step(6, "Checking for gaps")
    
    start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    end = datetime.strptime(END_DATE, "%Y-%m-%d").date()
    
    all_dates = set()
    current = start
    while current <= end:
        # Skip weekends (markets typically closed)
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            all_dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    dates_with_prices_set = set(dates_with_prices)
    missing_dates = sorted(all_dates - dates_with_prices_set)
    
    if missing_dates:
        print(f"   ⚠️ {len(missing_dates)} weekdays without data:")
        for d in missing_dates[:10]:
            print(f"      - {d}")
        if len(missing_dates) > 10:
            print(f"      ... and {len(missing_dates) - 10} more")
    else:
        print_success("No gaps in weekday data!")
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print()
    print_header("📊 SUMMARY")
    print(f"   Period: {START_DATE} to {END_DATE}")
    print(f"   Dates with data: {len(dates_with_prices)}")
    print(f"   Eligible cards: {eligible_cards}")
    
    if dates_summary:
        avg_cards = sum(d["with_nm"] for d in dates_summary) / len(dates_summary)
        avg_vol = sum(d["with_volume"] for d in dates_summary) / len(dates_summary)
        print(f"   Avg cards/day (NM): {avg_cards:.0f}")
        print(f"   Avg cards with volume/day: {avg_vol:.0f}")
    
    # Ready check
    print()
    ready = (
        INCEPTION_DATE in dates_with_prices and
        eligible_cards >= 100 and
        len(dates_with_prices) >= 1
    )

    if ready:
        print_success("✅ DATA IS READY! You can run:")
        print("   1. python scripts_oneshot/initialize_index.py")
        print("   2. python scripts_oneshot/calculate_index_history.py")
    else:
        print_error("❌ DATA NOT READY - Check issues above")


if __name__ == "__main__":
    main()