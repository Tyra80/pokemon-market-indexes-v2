"""
Pokemon Market Indexes v2 - Fetch PSA 10 Prices
================================================
Fetches PSA 10 graded card prices from eBay via PokemonPriceTracker API.

Strategy:
- Uses RARE_500 constituents as candidate list
- Fetches eBay sales data with includeEbay=true
- Stores PSA 10 specific metrics (median, avg, volume)
- Cost: 2 credits per card (with eBay data)

Usage:
    python scripts/fetch_psa10_prices.py
    python scripts/fetch_psa10_prices.py --limit 50  # Test with 50 cards
    python scripts/fetch_psa10_prices.py --dry-run   # Don't save to DB
"""

import sys
import os
import time
import argparse
import requests
from datetime import datetime, date, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification,
    print_header, print_step, print_success, print_error, print_warning,
    print_progress
)
from config.settings import PPT_API_KEY

# API Configuration
BASE_URL = "https://www.pokemonpricetracker.com/api/v2"
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}

# Batch size for API requests (max 20 with includeEbay)
API_BATCH_SIZE = 20


def api_request(endpoint: str, params: dict = None, max_retries: int = 5) -> tuple:
    """
    Makes a request to the API with automatic retry.

    Returns:
        tuple: (data_dict, credits_remaining) or (None, 0) on failure
    """
    url = f"{BASE_URL}{endpoint}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)
            credits_remaining = int(response.headers.get("X-Ratelimit-Daily-Remaining", -1))

            if response.status_code == 429:
                if credits_remaining == 0:
                    print(f"   API credits exhausted!")
                    return None, 0
                wait_time = 10 * (attempt + 1)
                print(f"   Rate limit, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json(), credits_remaining

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            if attempt < max_retries - 1:
                print(f"   HTTP Error {response.status_code}, retrying...")
                time.sleep(5)
                continue
            print(f"   Failed after {max_retries} attempts: {e}")
            return None, 0

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   Error: {e}, retrying...")
                time.sleep(5)
                continue
            print(f"   Failed after {max_retries} attempts: {e}")
            return None, 0

    return None, 0


def check_api_credits() -> int:
    """Check available API credits."""
    try:
        response = requests.get(
            f"{BASE_URL}/cards",
            headers=HEADERS,
            params={"set": "Base Set", "limit": 1},
            timeout=30
        )
        return int(response.headers.get("X-Ratelimit-Daily-Remaining", -1))
    except Exception as e:
        print(f"   Could not check credits: {e}")
        return -1


def extract_psa10_data(card_data: dict, price_date: str) -> dict | None:
    """
    Extracts PSA 10 data from eBay sales.

    Structure: card.ebay.salesByGrade.psa10
    """
    if not card_data:
        return None

    card_id = card_data.get("id")
    if not card_id:
        return None

    # Get eBay data
    ebay = card_data.get("ebay", {})
    if not ebay:
        return None

    sales_by_grade = ebay.get("salesByGrade", {})
    if not sales_by_grade:
        return None

    psa10 = sales_by_grade.get("psa10", {})
    if not psa10:
        return None

    # Check if there's any data
    total_sales = psa10.get("count", 0)
    if total_sales == 0:
        return None

    # Extract metrics
    avg_price = psa10.get("averagePrice")
    median_price = psa10.get("medianPrice")
    min_price = psa10.get("minPrice")
    max_price = psa10.get("maxPrice")
    daily_volume_7d = psa10.get("dailyVolume7Day")
    confidence = psa10.get("confidence")
    days_of_data = psa10.get("daysUsed")

    # Skip if no meaningful price data
    if not median_price and not avg_price:
        return None

    # Calculate liquidity score based on volume and confidence
    # Simple formula: daily_volume_7d / 2 (cap at 1.0)
    # A card selling 2+/day on eBay PSA 10 is very liquid
    liquidity_score = 0.0
    if daily_volume_7d:
        liquidity_score = min(daily_volume_7d / 2.0, 1.0)
    elif total_sales:
        # Fallback: estimate from total sales (assume 90-day window)
        estimated_daily = total_sales / 90.0
        liquidity_score = min(estimated_daily / 2.0, 1.0)

    # Boost for high confidence
    if confidence == "high":
        liquidity_score = min(liquidity_score * 1.1, 1.0)
    elif confidence == "low":
        liquidity_score *= 0.8

    return {
        "price_date": price_date,
        "card_id": card_id,
        "avg_price": avg_price,
        "median_price": median_price,
        "min_price": min_price,
        "max_price": max_price,
        "total_sales": total_sales,
        "daily_volume_7d": daily_volume_7d,
        "confidence": confidence,
        "days_of_data": days_of_data,
        "liquidity_score": round(liquidity_score, 4),
        "last_updated_api": datetime.utcnow().isoformat(),
    }


def fetch_psa10_for_set(set_name: str, price_date: str, constituent_ids: set[str]) -> tuple[list[dict], dict, int]:
    """
    Fetches PSA 10 data for all cards in a set.

    Args:
        set_name: Set name to fetch
        price_date: Date for the price record
        constituent_ids: Set of card IDs that are RARE_500 constituents (to filter)

    Returns:
        tuple: (psa10_data_list, stats_dict, credits_remaining)
    """
    data, credits = api_request("/cards", {
        "set": set_name,
        "fetchAllInSet": "true",
        "includeEbay": "true",
    })

    stats = {"total": 0, "with_psa10": 0, "constituents_matched": 0}

    if data is None:
        return [], stats, credits

    cards = data.get("data", [])
    if isinstance(cards, dict):
        cards = [cards]

    stats["total"] = len(cards)

    results = []
    for card in cards:
        card_id = card.get("id")
        if not card_id:
            continue

        # Only process cards that are in our RARE_500 constituents
        if card_id not in constituent_ids:
            continue

        stats["constituents_matched"] += 1

        psa10_data = extract_psa10_data(card, price_date)
        if psa10_data:
            results.append(psa10_data)
            stats["with_psa10"] += 1

    return results, stats, credits


def get_rare500_constituents(client) -> set[str]:
    """
    Gets card IDs from current RARE_500 constituents.
    Returns a set for O(1) lookup.
    """
    current_month = date.today().replace(day=1).strftime("%Y-%m-%d")

    response = client.from_("constituents_monthly") \
        .select("item_id") \
        .eq("index_code", "RARE_500") \
        .eq("month", current_month) \
        .execute()

    if not response.data:
        # Try previous month if current month not yet populated
        prev_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        response = client.from_("constituents_monthly") \
            .select("item_id") \
            .eq("index_code", "RARE_500") \
            .eq("month", prev_month.strftime("%Y-%m-%d")) \
            .execute()

    return {row["item_id"] for row in response.data} if response.data else set()


def get_sets_for_constituents(client, constituent_ids: set[str]) -> list[str]:
    """
    Gets the unique set names for the given constituent card IDs.
    """
    # Get set_ids for constituents
    response = client.from_("cards") \
        .select("set_id") \
        .in_("card_id", list(constituent_ids)) \
        .execute()

    if not response.data:
        return []

    set_ids = list({row["set_id"] for row in response.data if row.get("set_id")})

    # Get set names
    response = client.from_("sets") \
        .select("name") \
        .in_("set_id", set_ids) \
        .execute()

    return [row["name"] for row in response.data] if response.data else []


def ensure_psa_tables_exist(client) -> bool:
    """
    Checks if PSA tables exist. Returns False if they don't.
    """
    try:
        # Try to query psa10_prices_daily
        client.from_("psa10_prices_daily").select("card_id").limit(1).execute()
        return True
    except Exception as e:
        if "does not exist" in str(e).lower() or "relation" in str(e).lower():
            return False
        # Other error - tables might exist
        return True


def main():
    parser = argparse.ArgumentParser(description="Fetch PSA 10 prices from eBay")
    parser.add_argument("--limit-sets", type=int, help="Limit number of sets to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to database")
    args = parser.parse_args()

    # Use J-2 strategy like raw prices
    price_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")

    print_header("Pokemon Market Indexes - Fetch PSA 10 Prices")
    print(f"Target date: {price_date}")
    print(f"API cost: 2 credits/card (with eBay data)")
    if args.limit_sets:
        print(f"Limit: {args.limit_sets} sets")
    if args.dry_run:
        print("DRY RUN: No data will be saved")
    print()

    # Check credits
    print_step(1, "Checking API credits")
    initial_credits = check_api_credits()
    if initial_credits >= 0:
        print_success(f"API credits available: {initial_credits:,}")
    else:
        print_warning("Could not verify credits, proceeding anyway...")

    # Connect to database
    print_step(2, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return

    # Check if PSA tables exist
    print_step(3, "Checking PSA tables")
    if not ensure_psa_tables_exist(client):
        print_error("PSA tables not found!")
        print("Run the SQL from docs/SETUP_PSA.md first:")
        print("  1. Go to Supabase SQL Editor")
        print("  2. Copy/paste the CREATE TABLE statements")
        print("  3. Execute the SQL")
        return
    print_success("PSA tables exist")

    # Get RARE_500 constituents
    print_step(4, "Loading RARE_500 constituents")
    constituent_ids = get_rare500_constituents(client)
    if not constituent_ids:
        print_error("No RARE_500 constituents found!")
        return
    print_success(f"Found {len(constituent_ids)} constituents")

    # Get sets that contain our constituents
    print_step(5, "Finding sets with constituents")
    set_names = get_sets_for_constituents(client, constituent_ids)
    if not set_names:
        print_error("No sets found for constituents!")
        return
    print_success(f"Found {len(set_names)} sets containing constituents")

    # Apply limit if specified
    if args.limit_sets:
        set_names = set_names[:args.limit_sets]
        print(f"   Limited to {len(set_names)} sets for testing")

    # Log run
    run_id = log_run_start(client, "fetch_psa10_prices") if not args.dry_run else None

    # Fetch PSA 10 data by set
    print_step(6, f"Fetching PSA 10 data ({len(set_names)} sets)")

    all_psa10_data = []
    total_with_data = 0
    total_constituents_matched = 0
    last_credits = initial_credits
    credits_exhausted = False

    for i, set_name in enumerate(set_names, 1):
        print(f"\n   [{i}/{len(set_names)}] {set_name}")

        psa10_data, stats, credits = fetch_psa10_for_set(set_name, price_date, constituent_ids)

        if credits == 0:
            print_error("API credits exhausted!")
            credits_exhausted = True
            break

        if credits > 0:
            last_credits = credits

        all_psa10_data.extend(psa10_data)
        total_with_data += stats["with_psa10"]
        total_constituents_matched += stats["constituents_matched"]

        if stats["constituents_matched"] > 0:
            print(f"      Constituents: {stats['constituents_matched']}, PSA 10 data: {stats['with_psa10']}")

        # Rate limit pause
        time.sleep(0.5)

    # Summary of fetch
    print()
    print(f"   Sets processed: {len(set_names)}")
    print(f"   Constituents matched: {total_constituents_matched}/{len(constituent_ids)}")
    print(f"   Cards with PSA 10 data: {total_with_data}")
    if total_constituents_matched > 0:
        print(f"   PSA 10 coverage: {total_with_data * 100 / total_constituents_matched:.1f}%")
    print(f"   Credits remaining: {last_credits:,}")

    # Save to database
    if not args.dry_run and all_psa10_data:
        print_step(7, "Saving to database")

        # First, ensure psa_cards entries exist
        psa_cards_data = [
            {
                "card_id": row["card_id"],
                "has_psa10_data": True,
                "last_psa_fetch": datetime.utcnow().isoformat(),
                "psa_eligible": row.get("liquidity_score", 0) >= 0.1,  # Basic eligibility
            }
            for row in all_psa10_data
        ]

        result = batch_upsert(client, "psa_cards", psa_cards_data, on_conflict="card_id")
        print(f"   psa_cards: {result['saved']} saved")

        # Save prices
        result = batch_upsert(client, "psa10_prices_daily", all_psa10_data,
                              on_conflict="price_date,card_id")
        print_success(f"psa10_prices_daily: {result['saved']} saved")

        # Log run end
        log_run_end(client, run_id, "success" if not credits_exhausted else "partial",
                    records_processed=result['saved'],
                    details={
                        "sets_processed": len(set_names),
                        "constituents_matched": total_constituents_matched,
                        "cards_with_data": total_with_data,
                        "credits_remaining": last_credits,
                    })
    elif args.dry_run:
        print_step(7, "Dry run - skipping database save")

    # Show top cards by PSA 10 liquidity
    print_step(8, "Top PSA 10 cards by liquidity")
    top_cards = sorted(all_psa10_data, key=lambda x: x.get("liquidity_score", 0), reverse=True)[:10]

    for i, card in enumerate(top_cards, 1):
        # Get card name
        try:
            card_resp = client.from_("cards").select("name").eq("card_id", card["card_id"]).execute()
            name = card_resp.data[0]["name"][:30] if card_resp.data else card["card_id"][:30]
        except Exception:
            name = card["card_id"][:30]

        median = card.get("median_price") or 0
        volume = card.get("daily_volume_7d") or 0
        conf = card.get("confidence", "?")
        liq = card.get("liquidity_score", 0)
        print(f"   {i:2}. {name:<30} ${median:>8.2f} | vol={volume:.2f}/d | {conf:<6} | liq={liq:.2f}")

    # Show cards without PSA 10 data
    cards_without_data = total_constituents_matched - total_with_data
    if cards_without_data > 0:
        print()
        print_warning(f"{cards_without_data} constituents have no PSA 10 sales data")
        print("   These cards likely have low PSA 10 market activity")

    print()
    print_header("SUMMARY")
    print(f"   Source: RARE_500 constituents")
    print(f"   Sets processed: {len(set_names)}")
    print(f"   Constituents matched: {total_constituents_matched}/{len(constituent_ids)}")
    print(f"   Cards with PSA 10 data: {total_with_data}")
    if total_constituents_matched > 0:
        print(f"   PSA 10 coverage: {total_with_data * 100 / total_constituents_matched:.1f}%")
    print(f"   Credits remaining: {last_credits:,}")
    print()

    if credits_exhausted:
        print_warning("Script completed with partial data (credits exhausted)")
    else:
        print_success("Script completed successfully!")


if __name__ == "__main__":
    main()
