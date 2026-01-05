"""
Pokemon Market Indexes - Sync TCGdex Set IDs
=============================================
Maps PPT sets to TCGdex set IDs for image URLs.

TCGdex image URL format:
https://assets.tcgdex.net/en/{tcgdex_set_id}/{card_number}/high.webp

Usage:
    python scripts/sync_tcgdex_sets.py
"""

import sys
import os
import requests
from difflib import SequenceMatcher

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_db_client, print_header, print_step, print_success, print_error, print_warning

# TCGdex API
TCGDEX_API_URL = "https://api.tcgdex.net/v2/en/sets"


def fetch_tcgdex_sets() -> list:
    """Fetch all sets from TCGdex API."""
    print("   Fetching sets from TCGdex API...")
    
    response = requests.get(TCGDEX_API_URL, timeout=30)
    response.raise_for_status()
    
    sets = response.json()
    print(f"   ✅ {len(sets)} sets retrieved from TCGdex")
    return sets


def fetch_db_sets(client) -> list:
    """Fetch all sets from database with pagination."""
    print("   Fetching sets from database...")
    
    all_sets = []
    offset = 0
    page_size = 1000
    
    while True:
        response = client.from_("sets").select("set_id, name, series, release_date, tcgdex_set_id").range(offset, offset + page_size - 1).execute()
        
        if not response.data:
            break
        
        all_sets.extend(response.data)
        
        if len(response.data) < page_size:
            break
        
        offset += page_size
    
    print(f"   ✅ {len(all_sets)} sets in database")
    return all_sets


def normalize_name(name: str) -> str:
    """Normalize set name for comparison."""
    if not name:
        return ""
    
    # Remove common prefixes
    prefixes = [
        "SV10:", "SV09:", "SV08:", "SV07:", "SV06:", "SV05:", "SV04:", "SV03:", "SV02:", "SV01:", "SV:",
        "SWSH12:", "SWSH11:", "SWSH10:", "SWSH09:", "SWSH08:", "SWSH07:", "SWSH06:", "SWSH05:", 
        "SWSH04:", "SWSH03:", "SWSH02:", "SWSH01:", "SWSH:",
        "SM -", "SM:", "XY -", "XY:", "BW -", "BW:",
        "ME02:", "ME01:", "ME:", "MEE:",
    ]
    
    normalized = name.strip()
    for prefix in prefixes:
        if normalized.upper().startswith(prefix.upper()):
            normalized = normalized[len(prefix):].strip()
            break
    
    # Clean up
    normalized = normalized.lower()
    normalized = normalized.replace("&", "and")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace(":", " ")
    normalized = normalized.replace("'", "")
    normalized = normalized.replace("–", " ")  # en-dash
    normalized = " ".join(normalized.split())
    
    return normalized


def similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def find_best_match(db_set: dict, tcgdex_sets: list) -> tuple:
    """Find the best TCGdex match for a database set."""
    db_name = db_set.get("name", "")
    db_normalized = normalize_name(db_name)
    
    if not db_normalized:
        return None, 0
    
    best_match = None
    best_score = 0
    
    for tcg_set in tcgdex_sets:
        tcg_name = tcg_set.get("name", "")
        tcg_normalized = normalize_name(tcg_name)
        
        if not tcg_normalized:
            continue
        
        # Calculate similarity
        score = similarity(db_normalized, tcg_normalized)
        
        # Bonus for exact containment
        if db_normalized in tcg_normalized or tcg_normalized in db_normalized:
            score += 0.2
        
        # Bonus for matching numbers (like "151", "200")
        db_numbers = set(c for c in db_name if c.isdigit())
        tcg_numbers = set(c for c in tcg_name if c.isdigit())
        if db_numbers and db_numbers == tcg_numbers:
            score += 0.15
        
        if score > best_score:
            best_score = score
            best_match = tcg_set
    
    return best_match, best_score


def main():
    print_header("🔄 Sync TCGdex Set IDs")
    
    # Connect to database
    print_step(1, "Connecting to database")
    try:
        client = get_db_client()
        print_success("Connected")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # Fetch sets
    print_step(2, "Fetching sets")
    try:
        tcgdex_sets = fetch_tcgdex_sets()
        db_sets = fetch_db_sets(client)
    except Exception as e:
        print_error(f"Failed to fetch sets: {e}")
        return
    
    # Find matches
    print_step(3, "Finding matches")
    
    matches = []
    no_matches = []
    already_mapped = []
    
    for db_set in db_sets:
        # Skip if already has tcgdex_set_id
        if db_set.get("tcgdex_set_id"):
            already_mapped.append(db_set)
            continue
        
        best_match, score = find_best_match(db_set, tcgdex_sets)
        
        if best_match and score >= 0.65:
            matches.append({
                "set_id": db_set["set_id"],
                "db_name": db_set["name"],
                "tcgdex_name": best_match["name"],
                "tcgdex_set_id": best_match["id"],
                "score": score
            })
        else:
            no_matches.append({
                "set_id": db_set["set_id"],
                "db_name": db_set["name"],
                "best_guess": best_match.get("name") if best_match else None,
                "best_id": best_match.get("id") if best_match else None,
                "score": score
            })
    
    # Display results
    print()
    print("=" * 70)
    print(f"📊 RESULTS")
    print("=" * 70)
    print(f"   Already mapped : {len(already_mapped)}")
    print(f"   New matches    : {len(matches)}")
    print(f"   No match found : {len(no_matches)}")
    print()
    
    # Show high-confidence matches
    print("✅ HIGH CONFIDENCE MATCHES (score >= 0.80):")
    print("-" * 70)
    high_conf = [m for m in matches if m["score"] >= 0.80]
    for m in sorted(high_conf, key=lambda x: -x["score"])[:15]:
        print(f"   {m['db_name'][:35]:<35} → {m['tcgdex_set_id']:<12} ({m['score']:.2f})")
    if len(high_conf) > 15:
        print(f"   ... and {len(high_conf) - 15} more")
    print()
    
    # Show medium-confidence matches
    print("⚠️  MEDIUM CONFIDENCE MATCHES (0.65 <= score < 0.80):")
    print("-" * 70)
    med_conf = [m for m in matches if 0.65 <= m["score"] < 0.80]
    for m in sorted(med_conf, key=lambda x: -x["score"])[:10]:
        print(f"   {m['db_name'][:35]:<35} → {m['tcgdex_set_id']:<12} ({m['score']:.2f})")
    if len(med_conf) > 10:
        print(f"   ... and {len(med_conf) - 10} more")
    print()
    
    # Show no matches
    if no_matches:
        print("❌ NO MATCH FOUND:")
        print("-" * 70)
        for m in no_matches[:10]:
            guess = f"→ {m['best_id']}? ({m['score']:.2f})" if m['best_guess'] else "No suggestion"
            print(f"   {m['db_name'][:40]:<40} {guess}")
        if len(no_matches) > 10:
            print(f"   ... and {len(no_matches) - 10} more")
        print()
    
    # Confirm update
    if not matches:
        print("No new matches to update.")
        return
    
    print("=" * 70)
    confirm = input(f"Update {len(matches)} sets in database? (y/n): ")
    
    if confirm.lower() != 'y':
        print("❌ Cancelled")
        return
    
    # Update database
    print_step(4, "Updating database")
    
    success = 0
    errors = 0
    
    for m in matches:
        try:
            client.from_("sets").update({
                "tcgdex_set_id": m["tcgdex_set_id"]
            }).eq("set_id", m["set_id"]).execute()
            success += 1
        except Exception as e:
            print_warning(f"Error updating {m['db_name']}: {e}")
            errors += 1
    
    print()
    print_success(f"Updated {success} sets, {errors} errors")
    
    # Generate SQL for manual fixes
    if no_matches:
        print()
        print("=" * 70)
        print("📋 MANUAL FIXES NEEDED")
        print("=" * 70)
        print("Run these SQL commands after verifying the mappings:\n")
        
        for m in no_matches:
            if m['best_id']:
                print(f"-- {m['db_name']} → {m['best_id']}?")
                print(f"UPDATE sets SET tcgdex_set_id = '{m['best_id']}' WHERE set_id = '{m['set_id']}';")
                print()


if __name__ == "__main__":
    main()