"""Test backfill for a single set to debug volume extraction."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from config.settings import PPT_API_KEY, CONDITION_WEIGHTS, RARE_RARITIES
from scripts.utils import get_db_client, batch_upsert

BASE_URL = "https://www.pokemonpricetracker.com/api/v2"
HEADERS = {"Authorization": f"Bearer {PPT_API_KEY}"}

SET_NAME = "SV: Prismatic Evolutions"
DAYS = 7

print(f"🔍 Testing backfill for: {SET_NAME}")
print(f"📅 Days: {DAYS}")
print()

# Fetch from API
print("📡 Fetching from API...")
response = requests.get(
    f"{BASE_URL}/cards",
    headers=HEADERS,
    params={
        "set": SET_NAME,
        "fetchAllInSet": "true",
        "includeHistory": "true",
        "days": DAYS
    },
    timeout=120
)

print(f"   Status: {response.status_code}")
print(f"   Credits remaining: {response.headers.get('X-Ratelimit-Daily-Remaining', '?')}")

data = response.json()
cards = data.get("data", [])
print(f"   Cards fetched: {len(cards)}")
print()

# Process cards
all_prices = []
cards_with_volume = 0

for card in cards:
    rarity = card.get("rarity", "")
    if rarity not in RARE_RARITIES:
        continue

    card_id = card.get("id")
    card_name = card.get("name")

    price_history = card.get("priceHistory", {})
    conditions_history = price_history.get("conditions", {})

    nm_history_data = conditions_history.get("Near Mint", {})
    nm_history = nm_history_data.get("history", [])

    if not nm_history:
        continue

    # Get other conditions history
    lp_history = conditions_history.get("Lightly Played", {}).get("history", [])
    mp_history = conditions_history.get("Moderately Played", {}).get("history", [])
    hp_history = conditions_history.get("Heavily Played", {}).get("history", [])
    dmg_history = conditions_history.get("Damaged", {}).get("history", [])

    # Index by date
    lp_by_date = {h.get("date", "")[:10]: h for h in lp_history if isinstance(h, dict)}
    mp_by_date = {h.get("date", "")[:10]: h for h in mp_history if isinstance(h, dict)}
    hp_by_date = {h.get("date", "")[:10]: h for h in hp_history if isinstance(h, dict)}
    dmg_by_date = {h.get("date", "")[:10]: h for h in dmg_history if isinstance(h, dict)}

    card_has_volume = False

    for entry in nm_history:
        if not isinstance(entry, dict):
            continue

        history_date = entry.get("date", "")
        if not history_date:
            continue

        price_date = history_date[:10]
        nm_price = entry.get("market")
        if not nm_price:
            continue

        # Get volumes
        nm_volume = entry.get("volume")
        lp_entry = lp_by_date.get(price_date, {})
        mp_entry = mp_by_date.get(price_date, {})
        hp_entry = hp_by_date.get(price_date, {})
        dmg_entry = dmg_by_date.get(price_date, {})

        lp_volume = lp_entry.get("volume") if lp_entry else None
        mp_volume = mp_entry.get("volume") if mp_entry else None
        hp_volume = hp_entry.get("volume") if hp_entry else None
        dmg_volume = dmg_entry.get("volume") if dmg_entry else None

        # Weighted volume
        weighted_volume = (
            (nm_volume or 0) * CONDITION_WEIGHTS.get("Near Mint", 1.0) +
            (lp_volume or 0) * CONDITION_WEIGHTS.get("Lightly Played", 0.8) +
            (mp_volume or 0) * CONDITION_WEIGHTS.get("Moderately Played", 0.6) +
            (hp_volume or 0) * CONDITION_WEIGHTS.get("Heavily Played", 0.4) +
            (dmg_volume or 0) * CONDITION_WEIGHTS.get("Damaged", 0.2)
        )

        daily_volume = round(weighted_volume) if weighted_volume > 0 else None

        if nm_volume is not None and nm_volume > 0:
            card_has_volume = True

        all_prices.append({
            "price_date": price_date,
            "card_id": card_id,
            "market_price": float(nm_price),
            "nm_price": float(nm_price),
            "nm_volume": nm_volume,
            "lp_volume": lp_volume,
            "mp_volume": mp_volume,
            "hp_volume": hp_volume,
            "dmg_volume": dmg_volume,
            "daily_volume": daily_volume,
        })

    if card_has_volume:
        cards_with_volume += 1

print(f"📊 Extraction results:")
print(f"   Total price records: {len(all_prices)}")
print(f"   Cards with volume: {cards_with_volume}")
print()

# Show sample data
print("📋 Sample records (first 5 with volume):")
samples_shown = 0
for p in all_prices:
    if p["nm_volume"] is not None and p["nm_volume"] > 0:
        print(f"   {p['price_date']} | nm_vol={p['nm_volume']} | daily_vol={p['daily_volume']}")
        samples_shown += 1
        if samples_shown >= 5:
            break

print()

# Save to DB
print("💾 Saving to database...")
client = get_db_client()

# Try inserting one by one to see the error
failed_examples = []
saved = 0
for i, record in enumerate(all_prices):
    try:
        client.from_("card_prices_daily").upsert(record, on_conflict="price_date,card_id").execute()
        saved += 1
    except Exception as e:
        if len(failed_examples) < 3:
            failed_examples.append((record, str(e)))

print(f"   Saved: {saved} records")
print(f"   Failed: {len(all_prices) - saved} records")

if failed_examples:
    print("\n❌ Sample errors:")
    for record, error in failed_examples:
        print(f"   Card: {record['card_id'][:20]}... Date: {record['price_date']}")
        print(f"   Error: {error[:200]}")
        print()
print()

# Verify
print("🔍 Verification query:")
print("""
SELECT price_date, COUNT(*) as total,
       COUNT(nm_volume) as with_nm_vol,
       SUM(nm_volume) as sum_nm_vol
FROM card_prices_daily
WHERE price_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY price_date ORDER BY price_date DESC;
""")
