"""
Quick backfill for volumes - No emojis to avoid encoding issues
"""
import sys
import os
import time
import requests
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_db_client, batch_upsert, fetch_all_paginated, log_run_start, log_run_end
from config.settings import PPT_API_KEY, CONDITION_WEIGHTS, RARE_RARITIES

BASE_URL = "https://www.pokemonpricetracker.com/api/v2"
HEADERS = {"Authorization": f"Bearer {PPT_API_KEY}"}


def api_request(endpoint, params=None):
    """Simple API request with retry"""
    for attempt in range(3):
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=120)
            credits = int(response.headers.get("X-Ratelimit-Daily-Remaining", -1))
            if response.status_code == 429:
                print("  [!] API credits exhausted!")
                return None, 0
            response.raise_for_status()
            return response.json(), credits
        except Exception as e:
            if attempt < 2:
                print(f"  [!] Error: {e}, retrying...")
                time.sleep(5)
            else:
                return None, -1
    return None, -1


def extract_prices(card_data, target_dates):
    """Extract historical prices with volume"""
    if not card_data:
        return []

    card_id = card_data.get("id")
    rarity = card_data.get("rarity", "")

    if not card_id or rarity not in RARE_RARITIES:
        return []

    price_history = card_data.get("priceHistory", {})
    if not price_history:
        return []

    conditions_history = price_history.get("conditions", {})
    nm_history = conditions_history.get("Near Mint", {}).get("history", [])

    if not nm_history:
        return []

    # Index other conditions by date
    lp_by_date = {h.get("date", "")[:10]: h for h in conditions_history.get("Lightly Played", {}).get("history", [])}
    mp_by_date = {h.get("date", "")[:10]: h for h in conditions_history.get("Moderately Played", {}).get("history", [])}
    hp_by_date = {h.get("date", "")[:10]: h for h in conditions_history.get("Heavily Played", {}).get("history", [])}
    dmg_by_date = {h.get("date", "")[:10]: h for h in conditions_history.get("Damaged", {}).get("history", [])}

    results = []
    for entry in nm_history:
        if not isinstance(entry, dict):
            continue

        price_date = entry.get("date", "")[:10]
        if price_date not in target_dates:
            continue

        nm_price = entry.get("market")
        if not nm_price:
            continue

        # Get volumes
        nm_volume = entry.get("volume")
        lp_volume = lp_by_date.get(price_date, {}).get("volume")
        mp_volume = mp_by_date.get(price_date, {}).get("volume")
        hp_volume = hp_by_date.get(price_date, {}).get("volume")
        dmg_volume = dmg_by_date.get(price_date, {}).get("volume")

        # Weighted volume
        weighted = (
            (nm_volume or 0) * 1.0 +
            (lp_volume or 0) * 0.8 +
            (mp_volume or 0) * 0.6 +
            (hp_volume or 0) * 0.4 +
            (dmg_volume or 0) * 0.2
        )
        daily_volume = round(weighted) if weighted > 0 else None

        results.append({
            "price_date": price_date,
            "card_id": card_id,
            "market_price": float(nm_price),
            "nm_price": float(nm_price),
            "nm_volume": nm_volume,
            "lp_price": lp_by_date.get(price_date, {}).get("market"),
            "lp_volume": lp_volume,
            "mp_price": mp_by_date.get(price_date, {}).get("market"),
            "mp_volume": mp_volume,
            "hp_price": hp_by_date.get(price_date, {}).get("market"),
            "hp_volume": hp_volume,
            "dmg_price": dmg_by_date.get(price_date, {}).get("market"),
            "dmg_volume": dmg_volume,
            "daily_volume": daily_volume,
        })

    return results


def main():
    days = 5  # Get 5 days to be safe
    today = date.today()
    yesterday = today - timedelta(days=1)
    start_date = yesterday - timedelta(days=days-1)

    target_dates = set()
    current = start_date
    while current <= yesterday:
        target_dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    print("=" * 60)
    print("Quick Backfill Volume")
    print("=" * 60)
    print(f"Target dates: {sorted(target_dates)}")
    print()

    client = get_db_client()
    print("[+] Connected to Supabase")

    run_id = log_run_start(client, "quick_backfill_volume")

    # Get sets
    sets = fetch_all_paginated(client, "sets", "set_id, name")
    print(f"[+] {len(sets)} sets to process")
    print()

    total_prices = 0
    total_with_volume = 0
    all_prices = []

    for i, set_data in enumerate(sets, 1):
        set_name = set_data.get("name")
        if not set_name:
            continue

        print(f"[{i}/{len(sets)}] {set_name}...", end=" ", flush=True)

        data, credits = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
            "includeHistory": "true",
            "days": days + 2,  # Extra buffer
        })

        if credits == 0:
            print("\n[!] Credits exhausted, stopping...")
            break

        if not data:
            print("no data")
            continue

        cards = data.get("data", [])
        if isinstance(cards, dict):
            cards = [cards]

        set_prices = []
        set_with_vol = 0

        for card in cards:
            prices = extract_prices(card, target_dates)
            for p in prices:
                set_prices.append(p)
                if p.get("daily_volume"):
                    set_with_vol += 1

        all_prices.extend(set_prices)
        total_with_volume += set_with_vol

        print(f"{len(set_prices)} prices, {set_with_vol} with volume")

        # Batch save
        if len(all_prices) >= 3000:
            result = batch_upsert(client, "card_prices_daily", all_prices, on_conflict="price_date,card_id")
            total_prices += result['saved']
            print(f"\n[+] Saved batch: {result['saved']} records\n")
            all_prices = []

        # Rate limit
        time.sleep(61)

    # Final batch
    if all_prices:
        result = batch_upsert(client, "card_prices_daily", all_prices, on_conflict="price_date,card_id")
        total_prices += result['saved']
        print(f"\n[+] Final batch: {result['saved']} records")

    log_run_end(client, run_id, "success", records_processed=total_prices)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total prices updated: {total_prices}")
    print(f"With volume: {total_with_volume}")
    print()

    # Verify
    print("Verification:")
    for d in sorted(target_dates):
        with_vol = client.from_("card_prices_daily").select("card_id", count="exact").eq("price_date", d).not_.is_("daily_volume", "null").execute()
        print(f"  {d}: {with_vol.count} cards with volume")


if __name__ == "__main__":
    main()
