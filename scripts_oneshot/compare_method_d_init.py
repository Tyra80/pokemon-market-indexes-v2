"""
Compare Method D vs No Method D at Initialization
=================================================
Simulates the difference between:
1. WITH Method D: avg_volume >= 0.5 AND trading_days >= 3 (using 8 weekly data points)
2. WITHOUT Method D: just positive liquidity score

Uses inception date data (December 6th, 2025).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from scripts.utils import get_db_client, print_header, print_step, print_success, get_volume_stats_30d, calculate_liquidity_smart
from scripts.calculate_index import calculate_ranking_score
from config.settings import INCEPTION_DATE, INDEX_CONFIG, MIN_AVG_VOLUME_30D

# Weekly data configuration for initialization
WEEKLY_DATA_START = "2025-10-13"  # First weekly data point
WEEKLY_DATA_POINTS = 8            # Number of weekly snapshots
WEEKLY_MIN_DAYS_WITH_VOLUME = 3   # Minimum weeks with volume (equivalent to 10/30 days)


def get_eligible_cards_at_inception(client):
    """Get all eligible cards with prices at inception date."""
    print_step(1, f"Fetching eligible cards at inception ({INCEPTION_DATE})")

    # Get eligible cards (paginated - Supabase limits to 1000 per request)
    eligible_cards = {}
    offset = 0
    limit = 1000
    while True:
        response = client.from_("cards") \
            .select("card_id, name, set_id, rarity, is_eligible") \
            .eq("is_eligible", True) \
            .range(offset, offset + limit - 1) \
            .execute()

        if not response.data:
            break

        for c in response.data:
            eligible_cards[c["card_id"]] = c

        if len(response.data) < limit:
            break
        offset += limit

    print(f"   Found {len(eligible_cards)} eligible cards")

    # Get set names
    sets_response = client.from_("sets").select("set_id, name").execute()
    set_names = {s["set_id"]: s["name"] for s in sets_response.data}

    # Add set_name to cards
    for card in eligible_cards.values():
        card["set_name"] = set_names.get(card.get("set_id"), "Unknown")

    # Get prices at inception
    response = client.from_("card_prices_daily") \
        .select("card_id, nm_price, daily_volume, nm_listings, lp_listings, mp_listings, hp_listings, dmg_listings, total_listings") \
        .eq("price_date", INCEPTION_DATE) \
        .not_.is_("nm_price", "null") \
        .execute()

    print(f"   Found {len(response.data)} prices at inception")

    # Merge
    cards = []
    for price_data in response.data:
        card_id = price_data["card_id"]
        if card_id in eligible_cards:
            card = eligible_cards[card_id].copy()
            card["nm_price"] = price_data["nm_price"]
            card["daily_volume"] = price_data.get("daily_volume", 0) or 0
            card["nm_listings"] = price_data.get("nm_listings", 0) or 0
            card["total_listings"] = price_data.get("total_listings", 0) or 0
            cards.append(card)

    print(f"   {len(cards)} eligible cards with prices")
    return cards


def simulate_with_method_d(cards: list, client, index_size: int = 100):
    """Select constituents WITH Method D filtering."""
    print_step(2, "Simulating WITH Method D (8 weekly data points)")

    # Calculate liquidity for all cards
    for card in cards:
        smart_score, _ = calculate_liquidity_smart(
            client=client,
            card_id=card["card_id"],
            current_date=INCEPTION_DATE,
            nm_listings=card.get("nm_listings", 0),
        )
        card["liquidity_score"] = smart_score
        card["ranking_score"] = calculate_ranking_score(card)

    # Apply Method D filter using weekly data
    eligible = []
    filtered_out = []

    for card in cards:
        vol_stats = get_volume_stats_30d(
            client,
            card["card_id"],
            INCEPTION_DATE,
            lookback_start=WEEKLY_DATA_START,
            min_days=WEEKLY_MIN_DAYS_WITH_VOLUME,
            avg_divisor=WEEKLY_DATA_POINTS
        )

        avg_vol = vol_stats.get("avg_volume", 0)
        days_with_vol = vol_stats.get("days_with_volume", 0)

        has_sufficient_volume = avg_vol >= MIN_AVG_VOLUME_30D
        has_regular_trading = days_with_vol >= WEEKLY_MIN_DAYS_WITH_VOLUME

        card["avg_volume"] = avg_vol
        card["days_with_volume"] = days_with_vol
        card["method_d_pass"] = has_sufficient_volume and has_regular_trading

        if has_sufficient_volume and has_regular_trading:
            eligible.append(card)
        else:
            filtered_out.append(card)

    print(f"   Method D eligible: {len(eligible)}")
    print(f"   Method D filtered out: {len(filtered_out)}")

    # Sort and select top N
    eligible.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)
    selected = eligible[:index_size]

    return selected, filtered_out


def simulate_without_method_d(cards: list, client, index_size: int = 100):
    """Select constituents WITHOUT Method D (just positive liquidity)."""
    print_step(3, "Simulating WITHOUT Method D (just positive liquidity)")

    # Calculate liquidity for all cards
    for card in cards:
        smart_score, _ = calculate_liquidity_smart(
            client=client,
            card_id=card["card_id"],
            current_date=INCEPTION_DATE,
            nm_listings=card.get("nm_listings", 0),
        )
        card["liquidity_score"] = smart_score
        card["ranking_score"] = calculate_ranking_score(card)

    # Filter: just positive liquidity
    eligible = [c for c in cards if c.get("liquidity_score", 0) > 0]

    print(f"   Positive liquidity: {len(eligible)}")

    # Sort and select top N
    eligible.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)
    selected = eligible[:index_size]

    return selected


def compare_selections(with_method_d: list, without_method_d: list):
    """Compare two selections and show differences."""
    print_step(4, "Comparing selections")

    with_ids = {c["card_id"] for c in with_method_d}
    without_ids = {c["card_id"] for c in without_method_d}

    common = with_ids & without_ids
    only_with = with_ids - without_ids
    only_without = without_ids - with_ids

    print(f"\n   Common cards: {len(common)}")
    print(f"   Only in Method D selection: {len(only_with)}")
    print(f"   Only in no-filter selection: {len(only_without)}")

    # Create lookup dicts
    with_dict = {c["card_id"]: c for c in with_method_d}
    without_dict = {c["card_id"]: c for c in without_method_d}

    # Cards that would be ADDED without Method D (high value cards filtered by Method D)
    print("\n" + "=" * 80)
    print("CARDS ADDED WITHOUT METHOD D (would enter index if no Method D filter)")
    print("=" * 80)

    added_cards = [without_dict[cid] for cid in only_without]
    added_cards.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)

    for i, card in enumerate(added_cards[:20], 1):
        print(f"   {i:2}. ${card['nm_price']:>8.2f} | {card['name'][:35]:<35} | {card['set_name'][:25]:<25}")
        print(f"       Liquidity: {card.get('liquidity_score', 0):.3f} | Rank Score: {card.get('ranking_score', 0):.1f}")
        print(f"       Avg Vol: {card.get('avg_volume', 0):.2f} | Days w/ Vol: {card.get('days_with_volume', 0)}")
        print()

    if len(added_cards) > 20:
        print(f"   ... and {len(added_cards) - 20} more cards")

    # Cards that would be REMOVED without Method D
    print("\n" + "=" * 80)
    print("CARDS REMOVED WITHOUT METHOD D (would exit index if no Method D filter)")
    print("=" * 80)

    removed_cards = [with_dict[cid] for cid in only_with]
    removed_cards.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)

    for i, card in enumerate(removed_cards[:20], 1):
        print(f"   {i:2}. ${card['nm_price']:>8.2f} | {card['name'][:35]:<35} | {card['set_name'][:25]:<25}")
        print(f"       Liquidity: {card.get('liquidity_score', 0):.3f} | Rank Score: {card.get('ranking_score', 0):.1f}")
        print(f"       Avg Vol: {card.get('avg_volume', 0):.2f} | Days w/ Vol: {card.get('days_with_volume', 0)}")
        print()

    if len(removed_cards) > 20:
        print(f"   ... and {len(removed_cards) - 20} more cards")

    return {
        "common": len(common),
        "only_with_method_d": len(only_with),
        "only_without_method_d": len(only_without),
        "added_cards": added_cards,
        "removed_cards": removed_cards
    }


def print_summary(with_method_d: list, without_method_d: list, comparison: dict):
    """Print summary statistics."""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Price stats
    with_prices = [c["nm_price"] for c in with_method_d]
    without_prices = [c["nm_price"] for c in without_method_d]

    print(f"\n   WITH Method D:")
    print(f"      Price range: ${min(with_prices):.2f} - ${max(with_prices):.2f}")
    print(f"      Average price: ${sum(with_prices)/len(with_prices):.2f}")
    print(f"      Total value: ${sum(with_prices):,.2f}")

    print(f"\n   WITHOUT Method D:")
    print(f"      Price range: ${min(without_prices):.2f} - ${max(without_prices):.2f}")
    print(f"      Average price: ${sum(without_prices)/len(without_prices):.2f}")
    print(f"      Total value: ${sum(without_prices):,.2f}")

    print(f"\n   Overlap: {comparison['common']}/100 cards ({comparison['common']}%)")
    print(f"   Different cards: {comparison['only_with_method_d'] + comparison['only_without_method_d']}")

    # Top 10 comparison
    print("\n" + "-" * 80)
    print("TOP 10 COMPARISON")
    print("-" * 80)

    print(f"\n   {'WITH Method D':<40} | {'WITHOUT Method D':<40}")
    print(f"   {'-'*40} | {'-'*40}")

    for i in range(10):
        with_card = with_method_d[i]
        without_card = without_method_d[i]

        with_str = f"${with_card['nm_price']:.0f} {with_card['name'][:30]}"
        without_str = f"${without_card['nm_price']:.0f} {without_card['name'][:30]}"

        print(f"   {i+1:2}. {with_str:<37} | {i+1:2}. {without_str:<37}")


def main():
    print_header("Method D vs No Method D - Initialization Comparison")
    print(f"Inception Date: {INCEPTION_DATE}")
    print(f"Weekly Data: {WEEKLY_DATA_POINTS} points from {WEEKLY_DATA_START}")
    print(f"Method D criteria: avg_vol >= {MIN_AVG_VOLUME_30D}, days >= {WEEKLY_MIN_DAYS_WITH_VOLUME}")
    print()

    client = get_db_client()
    print_success("Connected to Supabase")
    print()

    # Get all eligible cards at inception
    cards = get_eligible_cards_at_inception(client)
    print()

    # Simulate with Method D
    with_method_d, filtered_out = simulate_with_method_d(cards.copy(), client, index_size=100)
    print()

    # Simulate without Method D
    without_method_d = simulate_without_method_d(cards.copy(), client, index_size=100)
    print()

    # Compare
    comparison = compare_selections(with_method_d, without_method_d)

    # Summary
    print_summary(with_method_d, without_method_d, comparison)

    print("\n" + "=" * 80)
    print_success("Comparison complete!")


if __name__ == "__main__":
    main()
