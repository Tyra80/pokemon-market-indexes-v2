"""
Pokemon Market Indexes v2 - Fetch Cards
=======================================
Fetches the card reference data from PokemonPriceTracker.

Based on the official API documentation:
- /sets : retrieves the list of sets (limit=500)
- /cards?set={name}&fetchAllInSet=true : retrieves all cards from a set

Usage:
    python scripts/fetch_cards.py
"""

import sys
import os
import time
import requests
from datetime import datetime

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import PPT_API_KEY, PPT_BASE_URL, PPT_RATE_LIMIT

# Authentication headers (as per API documentation)
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}


# Maximum backoff time in seconds to prevent excessive waits
MAX_BACKOFF_SECONDS = 60


def api_request(endpoint: str, params: dict = None, max_retries: int = 3) -> dict:
    """
    Makes a request to the PokemonPriceTracker API with automatic retry.
    Uses exponential backoff with a cap to prevent excessive wait times.
    """
    url = f"{PPT_BASE_URL}{endpoint}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)

            # If rate limited, wait and retry with capped exponential backoff
            if response.status_code == 429:
                # Exponential backoff: 5s, 10s, 20s, 40s... capped at MAX_BACKOFF_SECONDS
                wait_time = min(5 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⏳ Rate limit reached, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            print(f"   ❌ HTTP Error {response.status_code}: {str(e)[:100]}")
            if attempt < max_retries - 1:
                wait_time = min(5 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⏳ Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Request error: {str(e)[:100]}")
            if attempt < max_retries - 1:
                wait_time = min(5 * (2 ** attempt), MAX_BACKOFF_SECONDS)
                print(f"   ⏳ Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            return None

    return None


def fetch_all_sets() -> list:
    """
    Fetches all sets from /sets.
    Uses limit=500 (max allowed by the API).
    """
    print("   Fetching sets...")
    
    all_sets = []
    offset = 0
    limit = 500  # Max allowed by API
    
    while True:
        try:
            data = api_request("/sets", {
                "limit": limit,
                "offset": offset,
                "sortBy": "releaseDate",
                "sortOrder": "desc"
            })
            
            # If the request failed
            if data is None:
                print(f"   ⚠️ Request failed at offset {offset}, continuing...")
                break
            
            sets = data.get("data", [])
            metadata = data.get("metadata", {})
            
            if not sets:
                break
            
            # Filter out None values
            valid_sets = [s for s in sets if s and isinstance(s, dict) and s.get("name")]
            all_sets.extend(valid_sets)

            print(f"   ... {len(all_sets)} sets loaded")

            # Check if there's more data
            if not metadata.get("hasMore", False):
                break
            
            if len(sets) < limit:
                break
            
            offset += limit
            time.sleep(PPT_RATE_LIMIT["delay_between_requests"])
            
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            break

    return all_sets


def fetch_cards_for_set(set_name: str) -> list:
    """
    Fetches all cards from a set via /cards?set={name}&fetchAllInSet=true.
    """
    try:
        data = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
        })
        
        # If the request failed (returns None after retries)
        if data is None:
            return []

        cards = data.get("data", [])

        # If data is a dict (single card), put it in a list
        if isinstance(cards, dict):
            cards = [cards]

        # Filter out None values
        valid_cards = [c for c in cards if c and isinstance(c, dict)]

        return valid_cards

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return []


def transform_set_to_db(set_data: dict) -> dict:
    """Transforms an API set to DB format."""
    if not set_data:
        return None

    # Use the API ID or create a slug from the name
    set_id = set_data.get("id") or set_data.get("tcgPlayerId")
    if not set_id:
        set_id = set_data.get("name", "unknown").lower().replace(" ", "-").replace(":", "")[:50]

    release_date = set_data.get("releaseDate")
    if release_date:
        release_date = release_date.replace("/", "-")[:10]  # Keep only YYYY-MM-DD
    
    return {
        "set_id": str(set_id),
        "name": set_data.get("name"),
        "series": set_data.get("series"),
        "release_date": release_date if release_date else None,
        "total_cards": set_data.get("cardCount"),
    }


def transform_card_to_db(card_data: dict) -> dict:
    """Transforms an API card to DB format."""
    if not card_data:
        return None

    # Unique ID: priority to internal ID, then tcgPlayerId
    ppt_id = card_data.get("id")
    tcgplayer_id = card_data.get("tcgPlayerId")

    if ppt_id:
        card_id = str(ppt_id)
    elif tcgplayer_id:
        card_id = f"tcg-{tcgplayer_id}"
    else:
        card_id = f"{card_data.get('setName', 'unknown')}-{card_data.get('cardNumber', 'unknown')}"

    # set_id: use setId from API or create a slug
    set_id = card_data.get("setId")
    if not set_id:
        set_name = card_data.get("setName", "unknown")
        set_id = set_name.lower().replace(" ", "-").replace(":", "")[:50]
    
    return {
        "card_id": card_id,
        "ppt_id": ppt_id,
        "tcgplayer_id": str(tcgplayer_id) if tcgplayer_id else None,
        "name": card_data.get("name"),
        "set_id": str(set_id),
        "card_number": card_data.get("cardNumber"),
        "rarity": card_data.get("rarity"),
        "variant": "normal",
        "card_type": card_data.get("cardType"),
        "hp": card_data.get("hp"),
        "artist": card_data.get("artist"),
        "is_eligible": True,
    }


def main():
    print_header("🃏 Pokemon Market Indexes - Fetch Cards (v6)")
    print(f"📅 Date: {get_today()}")
    print()
    print("⚠️  This script may take 15-30 minutes.")
    print("   You can interrupt it with Ctrl+C.")

    # Connection
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # Log the run
    run_id = log_run_start(client, "fetch_cards")

    total_sets = 0
    total_cards = 0

    try:
        # Fetch sets
        print_step(2, "Fetching sets")
        sets = fetch_all_sets()
        print_success(f"{len(sets)} sets found")

        if len(sets) == 0:
            print_error("No sets found! Check the API key.")
            return

        # Save sets
        print_step(3, "Saving sets")
        sets_db = [transform_set_to_db(s) for s in sets]
        sets_db = [s for s in sets_db if s is not None]

        result = batch_upsert(client, "sets", sets_db, on_conflict="set_id")
        print_success(f"{result['saved']} sets saved")
        total_sets = result['saved']

        # Fetch cards by set
        print_step(4, "Fetching cards")
        
        all_cards_db = []
        sets_with_cards = 0
        sets_without_cards = 0
        
        for i, set_data in enumerate(sets, 1):
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            cards = fetch_cards_for_set(set_name)
            
            if cards:
                cards_db = [transform_card_to_db(c) for c in cards]
                cards_db = [c for c in cards_db if c is not None]
                all_cards_db.extend(cards_db)
                print(f"   ✅ {len(cards)} cards")
                sets_with_cards += 1
            else:
                print(f"   ⚠️ No cards")
                sets_without_cards += 1

            # Save in batches of 2000 cards
            if len(all_cards_db) >= 2000:
                result = batch_upsert(client, "cards", all_cards_db, on_conflict="card_id")
                print(f"\n   💾 Batch saved: {result['saved']} cards")
                total_cards += result['saved']
                all_cards_db = []

            # Pause to respect rate limit (200 calls/min = 0.3s minimum)
            time.sleep(0.35)

        # Save the last batch
        if all_cards_db:
            result = batch_upsert(client, "cards", all_cards_db, on_conflict="card_id")
            print(f"\n   💾 Last batch: {result['saved']} cards")
            total_cards += result['saved']

        # Verification
        print_step(5, "Verification")

        response = client.from_("sets").select("*", count="exact").execute()
        print(f"   Sets in database: {response.count}")

        response = client.from_("cards").select("*", count="exact").execute()
        print(f"   Cards in database: {response.count}")

        # Log success
        log_run_end(client, run_id, "success", 
                    records_processed=total_cards,
                    details={
                        "sets": total_sets, 
                        "cards": total_cards,
                        "sets_with_cards": sets_with_cards,
                        "sets_without_cards": sets_without_cards
                    })
        
        # Discord notification
        send_discord_notification(
            "✅ Fetch Cards - Success",
            f"{total_sets} sets, {total_cards} cards loaded."
        )

        print()
        print_header("📊 SUMMARY")
        print(f"   Sets processed    : {total_sets}")
        print(f"   Sets with cards   : {sets_with_cards}")
        print(f"   Sets without cards: {sets_without_cards}")
        print(f"   Total cards       : {total_cards}")
        print()
        print_success("Script completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupt detected (Ctrl+C)")
        print("   Already saved data is preserved.")
        log_run_end(client, run_id, "interrupted", records_processed=total_cards)

    except Exception as e:
        print_error(f"Error: {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Fetch Cards - Failed",
            f"Error: {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()