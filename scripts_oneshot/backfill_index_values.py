"""
Pokemon Market Indexes v2 - Backfill Index Values
==================================================
One-time script to calculate index values from inception to a target date.

This script:
1. Starts from the day AFTER inception (inception = base 100, already set)
2. Calculates daily index values using Laspeyres chain-linking
3. Handles monthly rebalancing on the 1st of each month
4. Uses forward-fill for missing prices

Usage:
    python scripts_oneshot/backfill_index_values.py
    python scripts_oneshot/backfill_index_values.py --end-date 2026-01-06
"""

import sys
import os
from datetime import datetime, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    print_header, print_step, print_success, print_error,
)
from scripts.calculate_index import (
    get_cards_with_prices, filter_rare_cards, filter_outliers,
    filter_immature_cards, calculate_weights,
    save_constituents, save_index_value, calculate_index_laspeyres,
    get_prices_for_date
)
# Use batch functions from initialize_index for faster rebalancing
from scripts_oneshot.initialize_index import (
    select_constituents, batch_get_volume_stats, calculate_liquidity_batch
)
from config.settings import INDEX_CONFIG, INCEPTION_DATE, MIN_AVG_VOLUME_30D


def get_all_price_dates(client, start_date: str, end_date: str) -> list:
    """Get all distinct dates with price data in the range."""
    # Use a smarter query: check one record per day
    all_dates = []
    current = start_date

    while current <= end_date:
        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .eq("price_date", current) \
            .limit(1) \
            .execute()

        if response.data:
            all_dates.append(current)

        # Move to next day
        from datetime import datetime, timedelta
        current_dt = datetime.strptime(current, "%Y-%m-%d")
        current = (current_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    return all_dates


def calculate_for_date(client, price_date: str, force_rebalance: bool = False) -> dict:
    """
    Calculate index values for a specific date.

    Args:
        client: Supabase client
        price_date: Date to calculate for
        force_rebalance: If True, force rebalancing regardless of month

    Returns:
        dict: Results for each index
    """
    # Determine the month for this price date
    current_month = price_date[:8] + "01"  # e.g., "2025-12-01"

    # Load cards with prices
    all_cards = get_cards_with_prices(client, price_date)

    # Filter rare cards
    rare_cards = filter_rare_cards(all_cards)

    # Filter outliers
    rare_cards = filter_outliers(rare_cards)

    if not rare_cards:
        return {}

    # Check if we need to rebalance
    need_rebalance = force_rebalance

    if not need_rebalance:
        # Check if constituents exist for this month
        response = client.from_("constituents_monthly") \
            .select("index_code", count="exact") \
            .eq("month", current_month) \
            .limit(1) \
            .execute()

        if response.count == 0:
            need_rebalance = True

    results = {}

    for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
        # Rebalancing if needed
        if need_rebalance:
            # Filter immature cards
            mature_cards = filter_immature_cards(rare_cards.copy(), index_code, price_date)

            # Select constituents with smart liquidity
            constituents = select_constituents(
                mature_cards,
                index_code,
                client=client,
                price_date=price_date
            )

            if not constituents:
                continue

            # Calculate weights
            constituents = calculate_weights(constituents)

            # Save constituents
            save_constituents(client, index_code, current_month, constituents)
        else:
            # Load existing constituents
            response = client.from_("constituents_monthly") \
                .select("item_id, weight, composite_price, liquidity_score, ranking_score") \
                .eq("index_code", index_code) \
                .eq("month", current_month) \
                .order("rank") \
                .execute()

            constituents = []
            for row in response.data:
                card_info = next((c for c in all_cards if c["card_id"] == row["item_id"]), None)
                constituents.append({
                    "card_id": row["item_id"],
                    "name": card_info["name"] if card_info else "Unknown",
                    "weight": float(row["weight"]) if row["weight"] else 0,
                    "price": float(row["composite_price"]) if row["composite_price"] else 0,
                    "liquidity_score": float(row["liquidity_score"]) if row["liquidity_score"] else 0,
                    "ranking_score": float(row["ranking_score"]) if row["ranking_score"] else 0,
                })

        if not constituents:
            continue

        # Laspeyres calculation
        index_value, calc_details = calculate_index_laspeyres(
            client, index_code, constituents, price_date
        )

        # Market cap
        market_cap = sum(c.get("price", 0) for c in constituents)

        # Save value
        save_index_value(client, index_code, price_date, index_value,
                        len(constituents), market_cap, calc_details)

        results[index_code] = {
            "value": index_value,
            "constituents": len(constituents),
            "market_cap": market_cap,
            "method": calc_details.get("method"),
            "change_pct": calc_details.get("change_pct"),
            "forward_filled": calc_details.get("forward_filled", 0),
            "rebalanced": need_rebalance,
        }

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", default="2026-01-06", help="End date (YYYY-MM-DD)")
    parser.add_argument("--start-date", default=None, help="Start date (defaults to day after inception)")
    args = parser.parse_args()

    print_header("📊 Pokemon Market Indexes - BACKFILL")
    print(f"📅 Inception: {INCEPTION_DATE}")
    print(f"📅 End date: {args.end_date}")
    print()

    # Connect
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return

    # Determine start date (day after inception or user-specified)
    if args.start_date:
        start_date = args.start_date
    else:
        inception = datetime.strptime(INCEPTION_DATE, "%Y-%m-%d")
        start_date = (inception + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📅 Start date: {start_date}")

    # Get all dates to process
    print_step(2, "Finding dates to process")
    all_dates = get_all_price_dates(client, start_date, args.end_date)
    print_success(f"{len(all_dates)} dates found")

    if not all_dates:
        print_error("No dates to process!")
        return

    # Check which dates already have values
    existing_response = client.from_("index_values_daily") \
        .select("value_date, index_code") \
        .gte("value_date", start_date) \
        .lte("value_date", args.end_date) \
        .execute()

    existing_dates = set()
    for row in existing_response.data:
        existing_dates.add(row["value_date"])

    dates_to_process = [d for d in all_dates if d not in existing_dates]
    print(f"   Already calculated: {len(existing_dates)} dates")
    print(f"   To process: {len(dates_to_process)} dates")

    if not dates_to_process:
        print_success("All dates already calculated!")
        return

    # Process each date
    print_step(3, f"Calculating indexes for {len(dates_to_process)} dates")
    print()

    for i, price_date in enumerate(dates_to_process, 1):
        # Determine if this is a rebalancing date (1st of month)
        is_first_of_month = price_date.endswith("-01")
        current_month = price_date[:8] + "01"

        # Check if constituents exist for this month
        response = client.from_("constituents_monthly") \
            .select("index_code", count="exact") \
            .eq("month", current_month) \
            .limit(1) \
            .execute()

        need_rebalance = response.count == 0

        status = "🔄 REBALANCE" if need_rebalance else "📈"
        print(f"[{i}/{len(dates_to_process)}] {price_date} {status}")

        try:
            results = calculate_for_date(client, price_date, force_rebalance=False)

            if results:
                for code, data in results.items():
                    change_str = f" ({data['change_pct']:+.2f}%)" if data.get('change_pct') else ""
                    ff_str = f" [ff:{data['forward_filled']}]" if data.get('forward_filled', 0) > 0 else ""
                    rebal_str = " *REBAL*" if data.get('rebalanced') else ""
                    print(f"   {code}: {data['value']:.2f}{change_str}{ff_str}{rebal_str}")
            else:
                print(f"   ⚠️ No results")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Final summary
    print()
    print_step(4, "Final verification")

    response = client.from_("index_values_daily") \
        .select("index_code, value_date, index_value, change_1d, n_constituents") \
        .order("value_date", desc=True) \
        .order("index_code") \
        .limit(15) \
        .execute()

    print("\n   📊 Latest values:")
    for row in response.data:
        change = f"{row['change_1d']:+.2f}%" if row.get('change_1d') else "N/A"
        print(f"      {row['index_code']:<10} | {row['value_date']} | {row['index_value']:>8.2f} | {change:>8}")

    # Check rebalancing
    print("\n   📋 Monthly constituents:")
    response = client.from_("constituents_monthly") \
        .select("index_code, month, item_id", count="exact") \
        .execute()

    from collections import Counter
    month_counts = Counter()
    for row in response.data:
        month_counts[(row["month"], row["index_code"])] += 1

    for (month, index_code), count in sorted(month_counts.items()):
        print(f"      {month} | {index_code:<10} | {count} constituents")

    print()
    print_success("Backfill complete!")


if __name__ == "__main__":
    main()
