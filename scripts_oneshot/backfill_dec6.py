"""
Backfill prices for December 6th, 2025 only.
This date has incomplete data (890 cards instead of ~6500).

Uses the existing fetch_prices infrastructure.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import time
from scripts.utils import get_db_client, print_header, print_step, print_success
from config.settings import PPT_API_KEY, CONDITION_WEIGHTS, LIQUIDITY_CAP

TARGET_DATE = "2025-12-06"
BASE_URL = "https://www.pokemonpricetracker.com/api/v2"
HEADERS = {"Authorization": f"Bearer {PPT_API_KEY}"}


def api_request(endpoint: str, params: dict = None, max_retries: int = 3) -> dict:
    """Makes a request to the PPT API."""
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)
            if response.status_code == 429:
                wait_time = 10 * (attempt + 1)
                print(f"   Rate limit, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            print(f"   Error: {e}")
            return None
    return None


def extract_price_record(card_data: dict, card_id: str) -> dict:
    """Extract price record from API response."""
    prices = card_data.get("prices", {})
    if not prices:
        return None

    market_price = prices.get("market")
    if not market_price:
        return None

    conditions = prices.get("conditions", {})
    nm_data = conditions.get("Near Mint", {}) if conditions else {}
    lp_data = conditions.get("Lightly Played", {}) if conditions else {}
    mp_data = conditions.get("Moderately Played", {}) if conditions else {}
    hp_data = conditions.get("Heavily Played", {}) if conditions else {}
    dmg_data = conditions.get("Damaged", {}) if conditions else {}

    # Total listings
    total_listings = sum(
        cond.get("listings", 0) or 0
        for cond in conditions.values()
        if isinstance(cond, dict)
    )

    # Extract volume from history
    daily_volume = 0
    price_history = card_data.get("priceHistory", {})
    if price_history:
        conditions_history = price_history.get("conditions", {})
        for cond_history in conditions_history.values():
            if isinstance(cond_history, dict):
                for entry in cond_history.get("history", []):
                    if isinstance(entry, dict) and entry.get("date", "")[:10] == TARGET_DATE:
                        daily_volume += entry.get("volume") or 0

    # Calculate liquidity score
    weighted_listings = 0
    for cond_name, cond_data in conditions.items():
        if isinstance(cond_data, dict):
            listings = cond_data.get("listings", 0) or 0
            weight = CONDITION_WEIGHTS.get(cond_name, 0.5)
            weighted_listings += listings * weight
    liquidity_score = min(weighted_listings / LIQUIDITY_CAP, 1.0)

    return {
        "card_id": card_id,
        "price_date": TARGET_DATE,
        "market_price": market_price,
        "nm_price": nm_data.get("market"),
        "nm_listings": nm_data.get("listings") or 0,
        "lp_price": lp_data.get("market"),
        "lp_listings": lp_data.get("listings") or 0,
        "mp_price": mp_data.get("market"),
        "mp_listings": mp_data.get("listings") or 0,
        "hp_price": hp_data.get("market"),
        "hp_listings": hp_data.get("listings") or 0,
        "dmg_price": dmg_data.get("market"),
        "dmg_listings": dmg_data.get("listings") or 0,
        "total_listings": total_listings,
        "daily_volume": daily_volume,
        "liquidity_score": round(liquidity_score, 4),
    }


def main():
    print_header(f"Backfill prices for {TARGET_DATE}")

    client = get_db_client()
    print_success("Connected to Supabase")

    # Check current state
    print_step(1, "Checking current data")
    current = client.from_("card_prices_daily").select("card_id", count="exact").eq("price_date", TARGET_DATE).execute()
    print(f"   Current records for {TARGET_DATE}: {current.count}")

    # Get all sets with their cards
    print_step(2, "Loading sets and cards")
    sets_response = client.from_("sets").select("set_id, name").execute()
    sets_data = sets_response.data
    print(f"   Found {len(sets_data)} sets")

    # Delete existing data
    print_step(3, f"Deleting existing data for {TARGET_DATE}")
    client.from_("card_prices_daily").delete().eq("price_date", TARGET_DATE).execute()
    print(f"   Deleted {current.count} existing records")

    # Fetch prices for each set
    print_step(4, "Fetching prices from API")
    all_prices = []
    total_fetched = 0

    for i, s in enumerate(sets_data, 1):
        set_name = s["name"][:35]

        # Get cards mapping for this set
        cards_response = client.from_("cards").select("card_id, ppt_id").eq("set_id", s["set_id"]).not_.is_("ppt_id", "null").execute()
        cards = cards_response.data
        if not cards:
            continue

        ppt_to_card = {c["ppt_id"]: c["card_id"] for c in cards}

        # Fetch from API with history for Dec 6
        data = api_request("/cards", {
            "set": s["name"],
            "includeHistory": "true",
            "days": 1,
            "date": TARGET_DATE,
        })

        if not data or "data" not in data:
            print(f"[{i}/{len(sets_data)}] {set_name}... 0 prices")
            continue

        # Process cards
        set_count = 0
        for card in data["data"]:
            ppt_id = card.get("id")
            if ppt_id not in ppt_to_card:
                continue

            record = extract_price_record(card, ppt_to_card[ppt_id])
            if record and record.get("nm_price"):
                all_prices.append(record)
                set_count += 1

        total_fetched += set_count
        print(f"[{i}/{len(sets_data)}] {set_name}... {set_count} prices")

        # Save in batches
        if len(all_prices) >= 2000:
            client.from_("card_prices_daily").upsert(all_prices).execute()
            print(f"\n[+] Saved batch: {len(all_prices)} records\n")
            all_prices = []

        # Small delay to avoid rate limits
        time.sleep(0.2)

    # Save remaining
    if all_prices:
        client.from_("card_prices_daily").upsert(all_prices).execute()
        print(f"\n[+] Saved final batch: {len(all_prices)} records")

    # Verify
    print_step(5, "Verifying")
    final = client.from_("card_prices_daily").select("card_id", count="exact").eq("price_date", TARGET_DATE).execute()
    print(f"   Final records for {TARGET_DATE}: {final.count}")

    # Check Umbreon specifically
    umbreon_id = "68af81dfc4f780b5153e5cbe"
    umbreon_price = client.from_("card_prices_daily").select("nm_price, daily_volume").eq("card_id", umbreon_id).eq("price_date", TARGET_DATE).execute()
    if umbreon_price.data:
        p = umbreon_price.data[0]
        print(f"   Umbreon ex 161/131: ${p['nm_price']} (vol: {p['daily_volume']})")
    else:
        print(f"   Umbreon ex 161/131: NOT FOUND")

    print_success(f"Backfill complete! {total_fetched} prices fetched")


if __name__ == "__main__":
    main()
