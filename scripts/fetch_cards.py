"""
Pokemon Market Indexes v2 - Fetch Cards
=======================================
Fetches the card reference data from TCGdex API (free, unlimited).

TCGdex API:
- Base URL: https://api.tcgdex.net/v2/en
- Endpoints: /sets, /cards/{set_id}
- No authentication required
- Unlimited requests

Usage:
    python scripts/fetch_cards.py
"""

import sys
import os
import time
import requests
from datetime import datetime

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import RARE_RARITIES

# TCGdex API Base URL
TCGDEX_URL = "https://api.tcgdex.net/v2/en"


def fetch_sets() -> list:
    """
    Fetches all Pokemon TCG sets from TCGdex.
    
    Returns:
        list: List of sets with {id, name, releaseDate, ...}
    """
    url = f"{TCGDEX_URL}/sets"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_cards_for_set(set_id: str) -> list:
    """
    Fetches all cards from a set.
    
    Args:
        set_id: Set ID (e.g., "swsh1")
    
    Returns:
        list: List of cards
    """
    url = f"{TCGDEX_URL}/sets/{set_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("cards", [])


def transform_set(set_data: dict) -> dict:
    """Transform TCGdex set data to our format."""
    return {
        "set_id": set_data.get("id"),
        "name": set_data.get("name"),
        "series": set_data.get("serie", {}).get("name") if isinstance(set_data.get("serie"), dict) else set_data.get("serie"),
        "release_date": set_data.get("releaseDate"),
        "total_cards": set_data.get("cardCount", {}).get("total") if isinstance(set_data.get("cardCount"), dict) else None,
        "logo_url": set_data.get("logo"),
        "symbol_url": set_data.get("symbol"),
    }


def transform_card(card_data: dict, set_id: str, set_name: str = None, release_date: str = None) -> dict:
    """Transform TCGdex card data to our format."""
    # Extract rarity
    rarity = card_data.get("rarity")
    if isinstance(rarity, dict):
        rarity = rarity.get("name", "Unknown")
    
    # Check eligibility (rarity >= Rare)
    is_eligible = rarity in RARE_RARITIES if rarity else False
    
    # Build card ID (TCGdex format: set_id-local_id)
    local_id = card_data.get("localId") or card_data.get("id", "").split("-")[-1]
    card_id = f"{set_id}-{local_id}"
    
    return {
        "card_id": card_id,
        "name": card_data.get("name"),
        "set_id": set_id,
        "set_name": set_name,
        "number": local_id,
        "rarity": rarity,
        "release_date": release_date,
        "category": card_data.get("category"),
        "hp": card_data.get("hp"),
        "types": card_data.get("types"),
        "image_url": card_data.get("image"),
        "is_eligible": is_eligible,
    }


def main():
    print_header("🃏 Pokemon Market Indexes - Fetch Cards")
    print(f"📅 Date: {get_today()}")
    print(f"🌐 Source: TCGdex API (free)")
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
    run_id = log_run_start(client, "fetch_cards")
    
    total_sets = 0
    total_cards = 0
    eligible_cards = 0
    
    try:
        # Fetch sets
        print_step(2, "Fetching sets from TCGdex")
        sets = fetch_sets()
        print_success(f"{len(sets)} sets found")
        
        # Transform and save sets
        print_step(3, "Saving sets")
        sets_to_save = []
        for s in sets:
            transformed = transform_set(s)
            if transformed.get("set_id"):
                sets_to_save.append(transformed)
        
        result = batch_upsert(client, "sets", sets_to_save, on_conflict="set_id")
        print_success(f"{result['saved']} sets saved")
        total_sets = result['saved']
        
        # Fetch cards for each set
        print_step(4, "Fetching cards by set")
        
        all_cards = []
        
        for i, set_data in enumerate(sets, 1):
            set_id = set_data.get("id")
            set_name = set_data.get("name")
            release_date = set_data.get("releaseDate")
            
            if not set_id:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name} ({set_id})")
            
            try:
                cards = fetch_cards_for_set(set_id)
                
                for card in cards:
                    transformed = transform_card(card, set_id, set_name, release_date)
                    if transformed.get("card_id"):
                        all_cards.append(transformed)
                        if transformed.get("is_eligible"):
                            eligible_cards += 1
                
                print(f"   ✅ {len(cards)} cards")
                
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
            
            # Save in batches of 2000
            if len(all_cards) >= 2000:
                result = batch_upsert(client, "cards", all_cards, on_conflict="card_id")
                print(f"\n   💾 Batch saved: {result['saved']} cards")
                total_cards += result['saved']
                all_cards = []
            
            # Small pause to be nice to the API
            time.sleep(0.1)
        
        # Save remaining cards
        if all_cards:
            result = batch_upsert(client, "cards", all_cards, on_conflict="card_id")
            print(f"\n   💾 Last batch: {result['saved']} cards")
            total_cards += result['saved']
        
        # Verification
        print_step(5, "Verification")
        
        response = client.from_("sets").select("*", count="exact").execute()
        print(f"   Sets in database: {response.count}")
        
        response = client.from_("cards").select("*", count="exact").execute()
        print(f"   Cards in database: {response.count}")
        
        response = client.from_("cards").select("*", count="exact").eq("is_eligible", True).execute()
        print(f"   Eligible cards (>= Rare): {response.count}")
        
        # Rarity distribution
        print("\n   📊 Rarity distribution (Top 10):")
        response = client.from_("cards").select("rarity").execute()
        rarity_counts = {}
        for row in response.data:
            rarity = row.get("rarity") or "(Empty)"
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
        
        for rarity, count in sorted(rarity_counts.items(), key=lambda x: -x[1])[:10]:
            eligible_marker = "✓" if rarity in RARE_RARITIES else "✗"
            print(f"      {eligible_marker} {rarity:<30} : {count:>5}")
        
        # Log success
        log_run_end(client, run_id, "success",
                    records_processed=total_cards,
                    details={"sets": total_sets, "cards": total_cards, "eligible": eligible_cards})
        
        # Discord notification
        send_discord_notification(
            "✅ Fetch Cards - Success",
            f"{total_cards} cards fetched from {total_sets} sets.\n"
            f"📊 {eligible_cards} eligible cards (>= Rare)"
        )
        
        # Summary
        print()
        print_header("📊 SUMMARY")
        print(f"   Sets processed     : {total_sets}")
        print(f"   Cards fetched      : {total_cards}")
        print(f"   Eligible cards     : {eligible_cards}")
        print()
        print_success("Script completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupt detected (Ctrl+C)")
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
