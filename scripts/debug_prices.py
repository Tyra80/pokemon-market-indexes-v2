"""
Debug script to check price data in database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import get_db_client, fetch_all_paginated

def main():
    db = get_db_client()

    # 1. Check distinct dates in card_prices_daily using RPC or aggregation
    print("=" * 60)
    print("1. DISTINCT DATES in card_prices_daily")
    print("=" * 60)

    # Get dates by querying with different strategies
    # Strategy: get one record per date by using a subquery approach
    all_dates = set()

    # Fetch in pages to get all unique dates
    offset = 0
    page_size = 1000
    while True:
        result = db.from_('card_prices_daily').select('price_date').order('price_date', desc=True).range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        for r in result.data:
            all_dates.add(r['price_date'])
        if len(result.data) < page_size:
            break
        offset += page_size
        # Stop after getting enough to find distinct dates
        if len(all_dates) >= 10:
            break

    dates = sorted(all_dates, reverse=True)[:10]
    print(f"  Found {len(all_dates)} distinct dates (showing last 10):")
    for d in dates:
        print(f"    - {d}")

    if len(dates) < 2:
        print("\n[WARNING] Only 1 date in database! 24H change cannot be calculated.")
        return

    latest_date = dates[0]
    previous_date = dates[1]
    print(f"\n  Latest: {latest_date}")
    print(f"  Previous: {previous_date}")

    # 2. Check a specific card (Umbreon ex - top card)
    print("\n" + "=" * 60)
    print("2. SAMPLE CARD: Umbreon ex (sv08-161)")
    print("=" * 60)

    # Find the card
    card_result = db.from_('cards').select('card_id, name').ilike('name', '%Umbreon%ex%').limit(5).execute()
    if card_result.data:
        for card in card_result.data:
            print(f"  Found: {card['card_id']} - {card['name']}")

            # Get prices for this card
            prices = db.from_('card_prices_daily').select('*').eq('card_id', card['card_id']).order('price_date', desc=True).limit(5).execute()
            if prices.data:
                print(f"  Prices:")
                for p in prices.data:
                    print(f"    {p['price_date']}: market=${p.get('market_price', 'N/A')}, nm=${p.get('nm_price', 'N/A')}, volume={p.get('daily_volume', 'N/A')}")
            else:
                print("  No prices found!")
    else:
        print("  Card not found!")

    # 3. Check price changes between dates
    print("\n" + "=" * 60)
    print("3. PRICE CHANGES between last 2 dates")
    print("=" * 60)

    # Get prices for both dates
    latest_prices = db.from_('card_prices_daily').select('card_id, market_price').eq('price_date', latest_date).limit(100).execute()
    prev_prices = db.from_('card_prices_daily').select('card_id, market_price').eq('price_date', previous_date).limit(100).execute()

    latest_map = {p['card_id']: float(p['market_price'] or 0) for p in latest_prices.data}
    prev_map = {p['card_id']: float(p['market_price'] or 0) for p in prev_prices.data}

    changes = []
    for card_id, latest_price in latest_map.items():
        if card_id in prev_map and prev_map[card_id] > 0:
            prev_price = prev_map[card_id]
            change = ((latest_price - prev_price) / prev_price) * 100
            if abs(change) > 0.01:  # More than 0.01%
                changes.append((card_id, prev_price, latest_price, change))

    if changes:
        print(f"  Found {len(changes)} cards with price changes > 0.01%:")
        for card_id, prev, curr, chg in sorted(changes, key=lambda x: abs(x[3]), reverse=True)[:10]:
            print(f"    {card_id}: ${prev:.2f} -> ${curr:.2f} ({chg:+.2f}%)")
    else:
        print("  ⚠️  NO price changes found between dates!")
        print("  This explains why 24H shows 0.00% everywhere.")

    # 4. Check daily_volume
    print("\n" + "=" * 60)
    print("4. DAILY VOLUME check")
    print("=" * 60)

    volumes = db.from_('card_prices_daily').select('card_id, daily_volume, price_date').gt('daily_volume', 0).order('daily_volume', desc=True).limit(20).execute()
    if volumes.data:
        print(f"  Cards with daily_volume > 0:")
        for v in volumes.data[:10]:
            print(f"    {v['card_id']}: {v['daily_volume']} sales on {v['price_date']}")
    else:
        print("  [WARNING] NO cards have daily_volume > 0!")
        print("  This explains why SALES/MO shows 0 everywhere.")

    # 5. Count total records
    print("\n" + "=" * 60)
    print("5. TOTAL RECORDS in card_prices_daily")
    print("=" * 60)

    # Count by fetching with pagination
    total = 0
    offset = 0
    while True:
        result = db.from_('card_prices_daily').select('card_id', count='exact').range(offset, offset + 999).execute()
        if result.count:
            total = result.count
            break
        if not result.data:
            break
        total += len(result.data)
        if len(result.data) < 1000:
            break
        offset += 1000

    print(f"  Total records: {total}")

if __name__ == "__main__":
    main()
